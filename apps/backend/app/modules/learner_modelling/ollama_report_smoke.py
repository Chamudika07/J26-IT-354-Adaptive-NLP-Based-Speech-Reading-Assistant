"""Development-only, synthetic-only local Ollama report transport and smoke harness.

No production imports, external projections, database, identity lookup or storage.
HTTPX is an existing development dependency. No Ollama SDK, cloud service or model
download is used. Runtime environment (never loads .env or shared app Settings):
    APP_ENV=development
    READBUDDY_SYNTHETIC_OLLAMA_ENABLED=1
    OLLAMA_REPORT_MODEL=qwen3:4b                 (default; local 4B tags only)
    OLLAMA_REPORT_BASE_URL=http://127.0.0.1:11434 (default; loopback only)
    OLLAMA_REPORT_TIMEOUT_SECONDS=30            (optional; maximum 120)

After explicit human authorization, from apps/backend:
    uv run --frozen python -m app.modules.learner_modelling.ollama_report_smoke \
        --allow-ollama-request

The CLI prints status only, never a prompt, narrative or raw model response.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
from dataclasses import dataclass, field
from time import perf_counter
from typing import Annotated, Any
from urllib.parse import urlsplit

import httpx
from pydantic import Field, ValidationError

from app.modules.learner_modelling.report_contracts import NarrativeDraft, NarrativeRequest
from app.modules.learner_modelling.report_evidence import build_structured_report
from app.modules.learner_modelling.report_narrative import (
    NarrativeUnavailable,
    ReportGenerationLimits,
    ReportGenerationResult,
    _unique_json_object,
    generate_progress_report,
    validate_narrative,
)
from app.modules.learner_modelling.report_synthetic import build_synthetic_projection

_DEFAULT_URL = "http://127.0.0.1:11434"
# Configurable local Qwen3 4B quantizations; cloud and arbitrary model IDs are rejected.
_LOCAL_MODELS = frozenset({"qwen3:4b", "qwen3:4b-q4_K_M", "qwen3:4b-q8_0", "qwen3:4b-fp16"})
_INSTRUCTIONS = (
    "Return compact JSON matching the format schema. Copy schema_version and "
    "report_fingerprint; copy all approved_statements into statements exactly once, "
    "preserving every evidence_ref and text, including limitations. Use only the supplied "
    "role's synthetic evidence. Add nothing."
)
# Fixed synthetic fixture: 14 statements, ~1,849 compact JSON characters.
# 2,048 output tokens leaves room for this copy task without a 4,096-token runaway.
# This is a ceiling, not a target or a measured tokenizer count. Truncation still fails.
_OUTPUT_TOKENS = 2048
# Retain context headroom for the format grammar, chat template, evidence and output.
# Without local tokenizer/usage evidence, shrinking context risks prompt truncation.
_CONTEXT_TOKENS = 8192


@dataclass
class SmokeDiagnostics:
    """Content-free, opt-in timing. Missing counters mean unknown, not zero.

    With stream=False, header wait includes queueing, loading and generation.
    HTTPX connection traces are available only with the real HTTP transport.
    """

    stage: str = "not_started"
    timings_ms: dict[str, float] = field(default_factory=dict)
    server_counters: dict[str, int] = field(default_factory=dict)
    _started: float = field(default_factory=perf_counter, repr=False)
    _phase_started: float = field(default_factory=perf_counter, repr=False)
    _connect_started: float | None = field(default=None, repr=False)

    def phase(self, stage: str) -> None:
        now = perf_counter()
        if self.stage != "not_started":
            self.timings_ms[self.stage] = round((now - self._phase_started) * 1000, 3)
        self.stage, self._phase_started = stage, now

    async def trace(self, event: str, info: dict[str, Any]) -> None:
        # Never retain trace info: it can contain headers, content or exceptions.
        if event == "connection.connect_tcp.started":
            self._connect_started = perf_counter()
        elif event in ("connection.connect_tcp.complete", "connection.connect_tcp.failed"):
            if self._connect_started is not None:
                self.timings_ms["connection"] = round(
                    (perf_counter() - self._connect_started) * 1000, 3
                )

    def snapshot(self) -> dict[str, Any]:
        now = perf_counter()
        timings = dict(self.timings_ms)
        if self.stage != "not_started":
            timings[self.stage] = round((now - self._phase_started) * 1000, 3)
        timings["total"] = round((now - self._started) * 1000, 3)
        return {
            "last_stage": self.stage,
            "timings_ms": timings,
            "server_counters": dict(self.server_counters),
        }

    def counters(self, body: bytes) -> None:
        data = json.loads(body, object_pairs_hook=_unique_json_object)
        for key in (
            "total_duration",
            "load_duration",
            "prompt_eval_duration",
            "eval_duration",
            "prompt_eval_count",
            "eval_count",
        ):
            value = data.get(key)
            if type(value) is int and 0 <= value <= 10**15:
                self.server_counters[key] = value


class _OllamaSmokeLimits(ReportGenerationLimits):
    """Longer deadlines apply only to the gated synthetic Ollama workflow.

    Shared provider defaults, input/output size limits and other transports retain
    their existing limits. The default here remains 30 seconds unless overridden.
    """

    timeout_seconds: Annotated[float, Field(ge=0.001, le=120)] = 30.0


def _configured_smoke_limits() -> _OllamaSmokeLimits:
    try:
        return _OllamaSmokeLimits(
            timeout_seconds=float(os.environ.get("OLLAMA_REPORT_TIMEOUT_SECONDS", "30"))
        )
    except (ValueError, ValidationError):
        raise NarrativeUnavailable("configuration_required") from None


def _loopback_endpoint(value: str) -> str:
    """Canonicalize a numeric loopback URL; localhost never uses DNS resolution."""
    try:
        if (
            not value.isascii()
            or any(ord(char) <= 32 for char in value)
            or any(char in value for char in ("%", "\\"))
        ):
            raise ValueError()
        parts = urlsplit(value)
        if (
            parts.scheme != "http"
            or parts.username is not None
            or parts.password is not None
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
        ):
            raise ValueError()
        host = parts.hostname
        if host == "localhost":
            host = "127.0.0.1"
        address = ipaddress.ip_address(host or "")
        if not address.is_loopback or (
            isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None
        ):
            raise ValueError()
        port = parts.port if parts.port is not None else 11434
        if not 1 <= port <= 65535:
            raise ValueError()
        literal = f"[{address}]" if address.version == 6 else str(address)
        return f"http://{literal}:{port}/api/chat"
    except (ValueError, TypeError):
        raise NarrativeUnavailable("configuration_required") from None


def _output_text(body: bytes, model: str) -> str:
    try:
        data = json.loads(body, object_pairs_hook=_unique_json_object)
        if (
            not isinstance(data, dict)
            or data.get("done") is not True
            or data.get("done_reason") != "stop"
            or data.get("error") is not None
            or data.get("model") != model
        ):
            raise ValueError()
        message = data.get("message")
        if (
            not isinstance(message, dict)
            or message.get("role") != "assistant"
            or message.get("tool_calls")
            or message.get("refusal")
            or not isinstance(message.get("content"), str)
        ):
            raise ValueError()
        return str(message["content"])
    except (ValueError, TypeError, KeyError, RecursionError):
        raise NarrativeUnavailable("invalid_narrative") from None


class SyntheticOllamaNarrativeProvider:
    """Implements NarrativeProvider, but is bound to this harness's fixed fixture.

    This is not an auth/consent boundary and cannot be enabled in live learner paths.
    No external request is forwarded: the wire payload is always rebuilt locally.
    """

    def __init__(
        self,
        *,
        authorized: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
        diagnostics: SmokeDiagnostics | None = None,
    ) -> None:
        self._authorized = authorized
        self._diagnostics = diagnostics
        self._transport = transport
        self._request = build_structured_report(build_synthetic_projection()).narrative_request

    async def generate(
        self, request: NarrativeRequest, *, timeout_seconds: float, max_output_chars: int
    ) -> str:
        if (
            self._authorized is not True
            or os.environ.get("READBUDDY_SYNTHETIC_OLLAMA_ENABLED") != "1"
        ):
            raise NarrativeUnavailable("disabled")
        if os.environ.get("APP_ENV") != "development":
            raise NarrativeUnavailable("configuration_required")
        endpoint = _loopback_endpoint(os.environ.get("OLLAMA_REPORT_BASE_URL", _DEFAULT_URL))
        model = os.environ.get("OLLAMA_REPORT_MODEL", "qwen3:4b")
        if model not in _LOCAL_MODELS:
            raise NarrativeUnavailable("configuration_required")
        if type(request) is not NarrativeRequest or request != self._request:
            raise NarrativeUnavailable("invalid_narrative")
        try:
            budget = _OllamaSmokeLimits(
                timeout_seconds=timeout_seconds, max_output_chars=max_output_chars
            )
            configured = _configured_smoke_limits()
            budget = budget.model_copy(
                update={"timeout_seconds": min(budget.timeout_seconds, configured.timeout_seconds)}
            )
        except (ValueError, ValidationError):
            raise NarrativeUnavailable("configuration_required") from None
        evidence = self._request.model_dump_json()
        if len(evidence.encode()) > budget.max_input_bytes:
            raise NarrativeUnavailable("input_limit_exceeded")
        schema = NarrativeDraft.model_json_schema()
        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "think": False,
            "keep_alive": 0,
            "format": schema,
            "messages": [
                {"role": "system", "content": _INSTRUCTIONS},
                {"role": "user", "content": evidence},
            ],
            "options": {
                "temperature": 0,
                "seed": 0,
                "num_predict": _OUTPUT_TOKENS,
                "num_ctx": _CONTEXT_TOKENS,
            },
        }
        diagnostic = self._diagnostics
        if diagnostic is not None:
            diagnostic.phase("waiting_for_headers")
        try:
            async with asyncio.timeout(budget.timeout_seconds):
                async with httpx.AsyncClient(
                    transport=self._transport
                    if self._transport is not None
                    else httpx.AsyncHTTPTransport(retries=0, trust_env=False),
                    timeout=httpx.Timeout(budget.timeout_seconds),
                    trust_env=False,
                    follow_redirects=False,
                ) as client:
                    async with client.stream(
                        "POST",
                        endpoint,
                        json=payload,
                        extensions={"trace": diagnostic.trace} if diagnostic is not None else {},
                    ) as response:
                        if diagnostic is not None:
                            diagnostic.phase("response_body")
                        if response.status_code != 200:
                            raise NarrativeUnavailable("provider_error")
                        data = bytearray()
                        envelope_limit = min(262144, budget.max_output_chars * 8 + 16384)
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            if len(data) + len(chunk) > envelope_limit:
                                raise NarrativeUnavailable("output_limit_exceeded")
                            data.extend(chunk)
            if diagnostic is not None:
                diagnostic.phase("parsing")
            output = _output_text(bytes(data), model)
            if diagnostic is not None:
                diagnostic.counters(bytes(data))
                diagnostic.phase("validation")
            validate_narrative(self._request, output, max_output_chars=budget.max_output_chars)
            if diagnostic is not None:
                diagnostic.phase("provider_complete")
            return output
        except (TimeoutError, httpx.TimeoutException):
            raise NarrativeUnavailable("provider_timeout") from None
        except NarrativeUnavailable:
            raise
        except Exception:
            raise NarrativeUnavailable("provider_error") from None


async def run_synthetic_ollama_smoke_test(
    *,
    authorized: bool = False,
    _transport: httpx.AsyncBaseTransport | None = None,
    diagnostics: SmokeDiagnostics | None = None,
) -> ReportGenerationResult:
    """One local attempt; callers cannot supply learner evidence or identity."""
    projection = build_synthetic_projection()
    limits = _OllamaSmokeLimits()
    if (
        authorized is True
        and os.environ.get("READBUDDY_SYNTHETIC_OLLAMA_ENABLED") == "1"
        and os.environ.get("APP_ENV") == "development"
    ):
        try:
            limits = _configured_smoke_limits()
        except NarrativeUnavailable:
            return ReportGenerationResult(
                build_structured_report(projection), "unavailable", None, "configuration_required"
            )
    return await generate_progress_report(
        projection,
        provider=SyntheticOllamaNarrativeProvider(
            authorized=authorized, transport=_transport, diagnostics=diagnostics
        ),
        limits=limits,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic-only loopback Ollama smoke test")
    parser.add_argument(
        "--allow-ollama-request",
        action="store_true",
        help="Use only after explicit authorization for one local synthetic call",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print content-free phase timings and allowlisted server counters",
    )
    args = parser.parse_args()
    diagnostic = SmokeDiagnostics() if args.diagnostics else None
    result = asyncio.run(
        run_synthetic_ollama_smoke_test(
            authorized=args.allow_ollama_request, diagnostics=diagnostic
        )
    )
    print(
        json.dumps(
            {
                "synthetic_only": True,
                "local_only": True,
                "status": result.status,
                "reason": result.unavailable_reason,
                **({"diagnostics": diagnostic.snapshot()} if diagnostic is not None else {}),
            }
        )
    )
    return 0 if result.status == "validated_narrative" else 1


if __name__ == "__main__":
    raise SystemExit(main())
