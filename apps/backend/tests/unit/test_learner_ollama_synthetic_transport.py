"""Synthetic-only Ollama tests. Every HTTP response is mocked; no local daemon is used."""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import socket
import sys
from collections.abc import Awaitable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from app.modules.learner_modelling import ollama_report_smoke as smoke
from app.modules.learner_modelling.report_contracts import NarrativeDraft, NarrativeRequest
from app.modules.learner_modelling.report_evidence import build_structured_report
from app.modules.learner_modelling.report_narrative import (
    NarrativeUnavailable,
    ReportGenerationLimits,
    generate_progress_report,
)


@pytest.fixture(autouse=True)
def isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[Mock]:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("READBUDDY_SYNTHETIC_OLLAMA_ENABLED", "1")
    for name in ("OLLAMA_REPORT_MODEL", "OLLAMA_REPORT_BASE_URL", "OLLAMA_REPORT_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    # A proxy or cloud key must never be used by the local provider.
    monkeypatch.setenv("HTTP_PROXY", "http://remote.example.test:8080")
    monkeypatch.setenv("OLLAMA_HOST", "https://ollama.com")
    monkeypatch.setenv("OPENAI_API_KEY", "PRIVATE-synthetic-key-not-for-ollama")
    connection = Mock(side_effect=AssertionError("Real sockets, including loopback, forbidden"))
    original_connect, original_pair = socket.socket.connect, socket.socketpair
    making_pair = False

    def connect(sock: socket.socket, address: Any) -> Any:
        return original_connect(sock, address) if making_pair else connection(address)

    def pair(*args: Any, **kwargs: Any) -> Any:
        # Only Windows asyncio's internal wake-up pair may use local IPC sockets.
        nonlocal making_pair
        making_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            making_pair = False

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connection)
    monkeypatch.setattr(socket, "socketpair", pair)
    monkeypatch.setattr(socket, "create_connection", connection)
    yield connection
    connection.assert_not_called()


def _draft(request: httpx.Request) -> str:
    evidence = NarrativeRequest.model_validate_json(
        json.loads(request.content)["messages"][1]["content"]
    )
    return NarrativeDraft(
        schema_version="report-narrative-v1",
        report_fingerprint=evidence.report_fingerprint,
        statements=evidence.approved_statements,
    ).model_dump_json()


def _envelope(text: str, model: str = "qwen3:4b") -> dict[str, Any]:
    return {
        "model": model,
        "done": True,
        "done_reason": "stop",
        "message": {"role": "assistant", "content": text},
    }


def test_valid_local_structured_output_preserves_facts_without_logging_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        assert request.method == "POST"
        assert "authorization" not in request.headers
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3:4b"
        assert payload["format"] == NarrativeDraft.model_json_schema()
        assert payload["format"]["additionalProperties"] is False
        assert payload["think"] is False
        assert payload["stream"] is False
        assert payload["options"]["temperature"] == 0
        assert payload["options"]["num_predict"] == 2048
        assert payload["options"]["num_ctx"] == 8192
        assert payload["messages"][0] == {"role": "system", "content": smoke._INSTRUCTIONS}
        assert "additionalProperties" not in payload["messages"][0]["content"]
        assert "$defs" not in payload["messages"][0]["content"]
        expected = build_structured_report(smoke.build_synthetic_projection()).narrative_request
        assert payload["messages"][1] == {
            "role": "user",
            "content": expected.model_dump_json(),
        }
        assert len(expected.approved_statements) == 14
        assert "tools" not in payload
        assert "session_id" not in payload["messages"][1]["content"]
        assert "metric_calculation_version" not in payload["messages"][1]["content"]
        assert request.extensions["timeout"]["read"] == 30.0
        return httpx.Response(200, json=_envelope(_draft(request)))

    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.status == "validated_narrative"
    assert result.factual_report.role == "learner"
    assert result.factual_report.projection == smoke.build_synthetic_projection()
    assert result.narrative is not None
    assert len(calls) == 1
    assert "report_fingerprint" not in caplog.text
    assert "PRIVATE" not in caplog.text
    assert "first 0.6500" not in caplog.text


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434/api/chat"),
        ("http://localhost:11434/", "http://127.0.0.1:11434/api/chat"),
        ("http://[::1]:11434", "http://[::1]:11434/api/chat"),
        ("http://127.0.0.2:12500", "http://127.0.0.2:12500/api/chat"),
    ],
)
def test_only_canonical_numeric_loopback_targets_are_sent(
    url: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_REPORT_BASE_URL", url)

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == expected
        return httpx.Response(200, json=_envelope(_draft(request)))

    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.status == "validated_narrative"


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.1:11434",
        "http://10.0.0.1:11434",
        "http://0.0.0.0:11434",
        "http://8.8.8.8",
        "http://ollama.com",
        "http://localhost.evil.test",
        "http://127.0.0.1.evil.test",
        "http://[::]",
        "http://[2001:db8::1]:11434",
        "http://[::ffff:127.0.0.1]:11434",
        "https://127.0.0.1:11434",
        "http://user:password@127.0.0.1:11434",
        "http://127.0.0.1:11434@evil.test",
        "http://127.0.0.1:11434/other",
        "http://127.0.0.1:11434/?redirect=remote",
        "http://127.0.0.1:11434/#secret",
        "http://%31%32%37.0.0.1:11434",
        "http://127.1:11434",
        "http://2130706433:11434",
        "file:///etc/passwd",
        " http://127.0.0.1:11434",
        "http://127.0.0.1:99999",
        "http://127.0.0.1:0",
        "http://[::1%25zone]:11434",
        "http://localhost\\evil.test",
        "",
    ],
)
def test_invalid_remote_or_ambiguous_host_configuration_is_blocked_before_transport(
    url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_REPORT_BASE_URL", url)
    handler = Mock(side_effect=AssertionError("Invalid endpoint must never be contacted"))
    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.unavailable_reason == "configuration_required"
    assert result.narrative is None
    handler.assert_not_called()


@pytest.mark.parametrize(
    "variable,value,reason",
    [
        ("READBUDDY_SYNTHETIC_OLLAMA_ENABLED", None, "disabled"),
        ("READBUDDY_SYNTHETIC_OLLAMA_ENABLED", "true", "disabled"),
        ("APP_ENV", None, "configuration_required"),
        ("APP_ENV", "production", "configuration_required"),
        ("APP_ENV", "staging", "configuration_required"),
        ("OLLAMA_REPORT_MODEL", "qwen3:4b-cloud", "configuration_required"),
        ("OLLAMA_REPORT_MODEL", "model:cloud", "configuration_required"),
        ("OLLAMA_REPORT_TIMEOUT_SECONDS", "nan", "configuration_required"),
        ("OLLAMA_REPORT_TIMEOUT_SECONDS", "121", "configuration_required"),
        ("OLLAMA_REPORT_TIMEOUT_SECONDS", "bad", "configuration_required"),
    ],
)
def test_disabled_and_invalid_development_configuration_never_sends(
    variable: str,
    value: str | None,
    reason: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if value is None:
        monkeypatch.delenv(variable, raising=False)
    else:
        monkeypatch.setenv(variable, value)
    handler = Mock(side_effect=AssertionError("No local request should be made"))
    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.unavailable_reason == reason
    handler.assert_not_called()


def test_explicit_authorization_flag_is_required_even_with_environment_enablement() -> None:
    handler = Mock(side_effect=AssertionError("No local request should be made"))
    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(_transport=httpx.MockTransport(handler))
    )
    assert result.unavailable_reason == "disabled"
    handler.assert_not_called()


def test_model_and_shorter_deadline_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_REPORT_MODEL", "qwen3:4b-q8_0")
    monkeypatch.setenv("OLLAMA_REPORT_TIMEOUT_SECONDS", "10")

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["model"] == "qwen3:4b-q8_0"
        assert request.extensions["timeout"]["read"] == 10.0
        return httpx.Response(200, json=_envelope(_draft(request), "qwen3:4b-q8_0"))

    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.status == "validated_narrative"


@pytest.mark.parametrize("seconds", [100.0, 120.0])
def test_long_development_override_reaches_orchestrator_transport_and_total_deadline(
    seconds: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_REPORT_TIMEOUT_SECONDS", str(seconds))
    original_wait_for, original_timeout = asyncio.wait_for, asyncio.timeout
    outer_deadlines: list[float | None] = []
    transport_deadlines: list[float | None] = []

    async def recording_wait_for(awaitable: Awaitable[Any], timeout: float | None) -> Any:
        outer_deadlines.append(timeout)
        return await original_wait_for(awaitable, timeout=timeout)

    def recording_timeout(delay: float | None) -> asyncio.Timeout:
        transport_deadlines.append(delay)
        return original_timeout(delay)

    monkeypatch.setattr(asyncio, "wait_for", recording_wait_for)
    monkeypatch.setattr(asyncio, "timeout", recording_timeout)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert set(request.extensions["timeout"].values()) == {seconds}
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        return httpx.Response(200, json=_envelope(_draft(request)))

    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.status == "validated_narrative"
    assert outer_deadlines == [seconds]
    assert transport_deadlines == [seconds]
    assert len(calls) == 1


@pytest.mark.parametrize("seconds", ["120.001", "121", "0", "-1", "inf", "-inf", "nan"])
def test_out_of_bounds_override_fails_before_transport(
    seconds: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_REPORT_TIMEOUT_SECONDS", seconds)
    handler = Mock(side_effect=AssertionError("Invalid deadline must not reach Ollama"))
    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.unavailable_reason == "configuration_required"
    assert result.narrative is None
    handler.assert_not_called()


def test_long_environment_override_does_not_raise_a_direct_callers_shorter_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_REPORT_TIMEOUT_SECONDS", "120")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.extensions["timeout"]["read"] == 1.0
        return httpx.Response(200, json=_envelope(_draft(request)))

    provider = smoke.SyntheticOllamaNarrativeProvider(
        authorized=True,
        transport=httpx.MockTransport(handler),
    )
    request = build_structured_report(smoke.build_synthetic_projection()).narrative_request
    output = asyncio.run(provider.generate(request, timeout_seconds=1.0, max_output_chars=16000))
    assert (
        NarrativeDraft.model_validate_json(output).report_fingerprint == request.report_fingerprint
    )


@pytest.mark.parametrize("gate", ["authorization", "enablement", "environment"])
def test_long_override_does_not_bypass_development_gates(
    gate: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_REPORT_TIMEOUT_SECONDS", "120")
    if gate == "enablement":
        monkeypatch.delenv("READBUDDY_SYNTHETIC_OLLAMA_ENABLED")
    elif gate == "environment":
        monkeypatch.setenv("APP_ENV", "production")
    handler = Mock(side_effect=AssertionError("Development gate must prevent transport"))
    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=gate != "authorization",
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.unavailable_reason == (
        "configuration_required" if gate == "environment" else "disabled"
    )
    handler.assert_not_called()


def test_shared_provider_limits_and_inactive_defaults_are_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_REPORT_TIMEOUT_SECONDS", "120")
    shared = ReportGenerationLimits()
    local = smoke._OllamaSmokeLimits()
    assert shared.timeout_seconds == 5.0
    assert local.timeout_seconds == 30.0
    assert local.max_output_chars == shared.max_output_chars
    assert local.max_input_bytes == shared.max_input_bytes
    with pytest.raises(ValidationError):
        ReportGenerationLimits(timeout_seconds=120.0)
    result = asyncio.run(generate_progress_report(smoke.build_synthetic_projection()))
    assert result.unavailable_reason == "disabled"
    assert result.narrative is None


@pytest.mark.parametrize("status", [301, 307, 400, 404, 429, 500, 503])
def test_unavailable_server_missing_model_and_http_errors_are_sanitized_without_retry(
    status: int,
) -> None:
    handler = Mock(
        return_value=httpx.Response(
            status,
            json={"error": "PRIVATE raw server response"},
            headers={"location": "https://remote.example.test"},
        )
    )
    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.unavailable_reason == "provider_error"
    assert result.narrative is None
    assert "PRIVATE" not in repr(result)
    assert handler.call_count == 1


@pytest.mark.parametrize(
    "error,reason",
    [
        (httpx.ConnectError("PRIVATE missing Ollama server"), "provider_error"),
        (httpx.ReadTimeout("PRIVATE local timeout"), "provider_timeout"),
    ],
)
def test_transport_errors_do_not_escape_or_trigger_fallback(error: Exception, reason: str) -> None:
    handler = Mock(side_effect=error)
    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.unavailable_reason == reason
    assert result.narrative is None
    assert handler.call_count == 1
    assert "PRIVATE" not in repr(result)


def test_total_deadline_cancels_a_slow_local_model() -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json={})

    provider = smoke.SyntheticOllamaNarrativeProvider(
        authorized=True, transport=httpx.MockTransport(slow)
    )
    evidence = build_structured_report(smoke.build_synthetic_projection()).narrative_request
    with pytest.raises(NarrativeUnavailable) as caught:
        asyncio.run(provider.generate(evidence, timeout_seconds=0.01, max_output_chars=16000))
    assert caught.value.reason == "provider_timeout"


@pytest.mark.parametrize(
    "mutation",
    [
        "malformed_envelope",
        "malformed_content",
        "incomplete",
        "truncated",
        "wrong_model",
        "unknown_reference",
        "fabricated_score",
        "unsupported_improvement",
        "cross_role",
        "extra_field",
        "tool_call",
        "duplicate_json_key",
        "omitted_limitation",
    ],
)
def test_invalid_json_unverifiable_claims_and_cross_role_disclosures_are_rejected(
    mutation: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if mutation == "malformed_envelope":
            return httpx.Response(200, content=b"not JSON")
        if mutation == "duplicate_json_key":
            return httpx.Response(200, content=b'{"done":true,"done":false}')
        draft = json.loads(_draft(request))
        if mutation == "unknown_reference":
            draft["statements"][0]["evidence_ref"] = "e9999"
        elif mutation == "fabricated_score":
            draft["statements"][0]["text"] = "Accuracy is 999%."
        elif mutation == "unsupported_improvement":
            draft["statements"][0]["text"] = "This proves improvement in reading ability."
        elif mutation == "cross_role":
            draft["report_fingerprint"] = "0" * 64
        elif mutation == "extra_field":
            draft["guardian_details"] = "Unauthorized evidence"
        elif mutation == "omitted_limitation":
            draft["statements"].pop(2)
        body = _envelope("not JSON" if mutation == "malformed_content" else json.dumps(draft))
        if mutation == "incomplete":
            body["done"] = False
        elif mutation == "truncated":
            body["done_reason"] = "length"
        elif mutation == "wrong_model":
            body["model"] = "model:cloud"
        elif mutation == "tool_call":
            body["message"]["tool_calls"] = [{"function": {"name": "lookup_learner"}}]
        return httpx.Response(200, json=body)

    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
        )
    )
    assert result.unavailable_reason == "invalid_narrative"
    assert result.narrative is None


def test_bounded_response_envelope_and_narrative_size() -> None:
    oversized = Mock(return_value=httpx.Response(200, content=b"x" * 160000))
    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(oversized),
        )
    )
    assert result.unavailable_reason == "output_limit_exceeded"
    provider = smoke.SyntheticOllamaNarrativeProvider(
        authorized=True,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=_envelope(_draft(request)))
        ),
    )
    evidence = build_structured_report(smoke.build_synthetic_projection()).narrative_request
    with pytest.raises(NarrativeUnavailable) as caught:
        asyncio.run(provider.generate(evidence, timeout_seconds=1.0, max_output_chars=256))
    assert caught.value.reason == "output_limit_exceeded"


def test_cross_role_caller_evidence_never_reaches_the_local_server() -> None:
    handler = Mock(side_effect=AssertionError("External evidence must not be forwarded"))
    provider = smoke.SyntheticOllamaNarrativeProvider(
        authorized=True, transport=httpx.MockTransport(handler)
    )
    evidence = build_structured_report(smoke.build_synthetic_projection()).narrative_request
    with pytest.raises(NarrativeUnavailable) as caught:
        asyncio.run(
            provider.generate(
                evidence.model_copy(update={"role": "educator"}),
                timeout_seconds=1.0,
                max_output_chars=16000,
            )
        )
    assert caught.value.reason == "invalid_narrative"
    handler.assert_not_called()


def test_no_database_dependencies_or_production_importers() -> None:
    path = Path(smoke.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        item.name for node in ast.walk(tree) if isinstance(node, ast.Import) for item in node.names
    }
    assert not any(
        value.startswith(
            (
                "sqlalchemy",
                "psycopg",
                "fastapi",
                "app.db",
                "app.core.config",
                "app.modules.auth",
                "app.modules.consent",
                "app.modules.learners",
                "app.modules.learner_modelling.service",
                "app.modules.learner_modelling.repository",
            )
        )
        for value in imports
    )
    for other in path.parents[2].rglob("*.py"):
        # The explicitly invoked offline exporter is the only additional dev entry point.
        if other not in (path, path.with_name("local_report_snapshot.py")):
            assert "ollama_report_smoke" not in other.read_text(encoding="utf-8")


def test_cli_is_disabled_without_explicit_authorization_and_prints_status_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["ollama_report_smoke"])
    assert smoke.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "synthetic_only": True,
        "local_only": True,
        "status": "unavailable",
        "reason": "disabled",
    }


def test_diagnostic_success_records_phases_and_only_allowlisted_numeric_counters() -> None:
    diagnostic = smoke.SmokeDiagnostics()

    async def handler(request: httpx.Request) -> httpx.Response:
        trace = request.extensions["trace"]
        await trace("connection.connect_tcp.started", {"secret": "PRIVATE"})
        await asyncio.sleep(0.001)
        await trace("connection.connect_tcp.complete", {"secret": "PRIVATE"})
        body = _envelope(_draft(request))
        body.update(
            load_duration=123,
            eval_duration=456,
            eval_count=42,
            prompt_eval_count="PRIVATE",
            total_duration=-1,
            secret="PRIVATE",
            prompt_eval_duration=True,
        )
        return httpx.Response(200, json=body)

    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
            diagnostics=diagnostic,
        )
    )
    assert result.status == "validated_narrative"
    snapshot = diagnostic.snapshot()
    assert snapshot["last_stage"] == "provider_complete"
    assert set(snapshot["timings_ms"]) == {
        "connection",
        "waiting_for_headers",
        "response_body",
        "parsing",
        "validation",
        "provider_complete",
        "total",
    }
    assert all(value >= 0 for value in snapshot["timings_ms"].values())
    assert snapshot["server_counters"] == {
        "load_duration": 123,
        "eval_duration": 456,
        "eval_count": 42,
    }
    assert "PRIVATE" not in json.dumps(snapshot)
    assert "report_fingerprint" not in json.dumps(snapshot)


@pytest.mark.parametrize("outer", [False, True])
def test_diagnostics_survive_transport_and_outer_timeout(
    outer: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostic = smoke.SmokeDiagnostics()
    monkeypatch.setenv("OLLAMA_REPORT_TIMEOUT_SECONDS", "0.01")
    if outer:
        original_wait_for = asyncio.wait_for

        async def shorter(awaitable: Awaitable[Any], timeout: float | None) -> Any:
            return await original_wait_for(awaitable, timeout=0.005)

        monkeypatch.setattr(asyncio, "wait_for", shorter)

    async def handler(request: httpx.Request) -> httpx.Response:
        if not outer:
            raise httpx.ReadTimeout("PRIVATE")
        await asyncio.sleep(1)
        return httpx.Response(200, json={})

    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
            diagnostics=diagnostic,
        )
    )
    assert result.unavailable_reason == "provider_timeout"
    snapshot = diagnostic.snapshot()
    assert snapshot["last_stage"] == "waiting_for_headers"
    assert snapshot["server_counters"] == {}
    assert snapshot["timings_ms"]["waiting_for_headers"] >= 0
    assert "PRIVATE" not in json.dumps(snapshot)


@pytest.mark.parametrize("invalid", ["envelope", "facts"])
def test_diagnostics_distinguish_parse_and_validation_failure(invalid: str) -> None:
    diagnostic = smoke.SmokeDiagnostics()

    def handler(request: httpx.Request) -> httpx.Response:
        if invalid == "envelope":
            return httpx.Response(200, content=b"PRIVATE invalid JSON")
        draft = json.loads(_draft(request))
        draft["statements"][0]["text"] = "PRIVATE fabricated 999 score"
        return httpx.Response(200, json=_envelope(json.dumps(draft)))

    result = asyncio.run(
        smoke.run_synthetic_ollama_smoke_test(
            authorized=True,
            _transport=httpx.MockTransport(handler),
            diagnostics=diagnostic,
        )
    )
    assert result.unavailable_reason == "invalid_narrative"
    snapshot = diagnostic.snapshot()
    assert snapshot["last_stage"] == ("parsing" if invalid == "envelope" else "validation")
    assert "PRIVATE" not in json.dumps(snapshot)


def test_diagnostic_cli_disabled_gate_has_no_request_timing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["ollama_report_smoke", "--diagnostics"])
    assert smoke.main() == 1
    output = json.loads(capsys.readouterr().out)
    assert output["reason"] == "disabled"
    assert output["diagnostics"]["last_stage"] == "not_started"
    assert set(output["diagnostics"]["timings_ms"]) == {"total"}
    assert output["diagnostics"]["server_counters"] == {}
