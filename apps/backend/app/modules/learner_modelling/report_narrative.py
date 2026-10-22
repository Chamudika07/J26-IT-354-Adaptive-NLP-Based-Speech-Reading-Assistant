"""Offline narrative boundary and deterministic validation, not a production workflow.

No routes, database, environment secrets, network transport, retries, or logging.
The caller must first enforce authorization, consent, third-party processing policy,
and cost controls. A candidate's fluent wording is never evidence: this initial
contract accepts only exact approved statements with complete claim references.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Annotated, Literal, Protocol

from pydantic import Field, SecretStr, ValidationError

from app.modules.learner_modelling.report_contracts import (
    NarrativeDraft,
    NarrativeRequest,
    ReportContract,
)
from app.modules.learner_modelling.report_evidence import (
    Projection,
    StructuredEvidenceReport,
    build_structured_report,
)

UnavailableReason = Literal[
    "disabled",
    "configuration_required",
    "adapter_not_integrated",
    "provider_timeout",
    "provider_error",
    "invalid_narrative",
    "output_limit_exceeded",
    "input_limit_exceeded",
]
_UNAVAILABLE_REASONS = frozenset(
    {
        "disabled",
        "configuration_required",
        "adapter_not_integrated",
        "provider_timeout",
        "provider_error",
        "invalid_narrative",
        "output_limit_exceeded",
        "input_limit_exceeded",
    }
)


class NarrativeUnavailable(Exception):
    def __init__(self, reason: UnavailableReason) -> None:
        super().__init__("AI report generation is unavailable.")
        self.reason = reason


class ReportGenerationLimits(ReportContract):
    timeout_seconds: Annotated[float, Field(ge=0.001, le=30)] = 5.0
    max_output_chars: Annotated[int, Field(ge=256, le=65536)] = 16000
    max_input_bytes: Annotated[int, Field(ge=256, le=131072)] = 65536


class NarrativeProvider(Protocol):
    async def generate(
        self, request: NarrativeRequest, *, timeout_seconds: float, max_output_chars: int
    ) -> str:
        """Return untrusted schema-shaped JSON, never an authoritative report."""
        ...


class InactiveNarrativeProvider:
    async def generate(
        self, request: NarrativeRequest, *, timeout_seconds: float, max_output_chars: int
    ) -> str:
        raise NarrativeUnavailable("disabled")


class OpenAIReportConfiguration(ReportContract):
    """Future server-only config. No defaults read keys from environment or clients."""

    enabled: bool = False
    model: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    server_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    max_retries: Literal[0] = 0
    store: Literal[False] = False


@dataclass(frozen=True, slots=True)
class OpenAINarrativeProvider:
    """Inactive SDK integration boundary, even with explicit configuration.

    OpenAI is not a declared production dependency. A separately approved SDK and
    transport implementation must enforce the supplied timeout, strict JSON schema,
    output budget, disabled retries, server-managed key and retention policy. This
    class deliberately cannot issue requests and cannot activate by a config flag.
    """

    configuration: OpenAIReportConfiguration = field(
        default_factory=OpenAIReportConfiguration, repr=False
    )

    async def generate(
        self, request: NarrativeRequest, *, timeout_seconds: float, max_output_chars: int
    ) -> str:
        if not self.configuration.enabled:
            raise NarrativeUnavailable("disabled")
        if (
            not self.configuration.model
            or self.configuration.server_api_key is None
            or not self.configuration.server_api_key.get_secret_value().strip()
        ):
            raise NarrativeUnavailable("configuration_required")
        raise NarrativeUnavailable("adapter_not_integrated")


@dataclass(frozen=True, slots=True)
class ReportGenerationResult:
    factual_report: StructuredEvidenceReport
    status: Literal["validated_narrative", "unavailable"]
    narrative: NarrativeDraft | None
    unavailable_reason: UnavailableReason | None
    disclosure: str = (
        "Advisory educational report only. Narrative statements are checked against supplied "
        "evidence; fluency does not prove factual correctness. No settings are changed."
    )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def validate_narrative(
    request: NarrativeRequest, raw_output: str, *, max_output_chars: int = 16000
) -> NarrativeDraft:
    """No paraphrase is accepted without a future independently reviewed verifier.

    Every approved statement is mandatory, including limited evidence and missingness.
    Reject stale/cross-role fingerprints, omissions, duplicates, unknown references,
    numeric changes, diagnoses, classifications, instructions and arbitrary additions.
    """
    if type(raw_output) is not str:
        raise NarrativeUnavailable("invalid_narrative")
    if len(raw_output) > max_output_chars:
        raise NarrativeUnavailable("output_limit_exceeded")
    try:
        json.loads(raw_output, object_pairs_hook=_unique_json_object)
        draft = NarrativeDraft.model_validate_json(raw_output)
        approved = {item.evidence_ref: item.text for item in request.approved_statements}
        proposed = {item.evidence_ref: item.text for item in draft.statements}
        if (
            draft.report_fingerprint != request.report_fingerprint
            or len(draft.statements) != len(proposed)
            or proposed != approved
        ):
            raise ValueError("Unverifiable narrative")
        return draft
    except (ValidationError, ValueError, TypeError, RecursionError):
        raise NarrativeUnavailable("invalid_narrative") from None


async def generate_progress_report(
    projection: Projection,
    *,
    provider: NarrativeProvider | None = None,
    limits: ReportGenerationLimits | None = None,
) -> ReportGenerationResult:
    """Build authoritative facts first, then make at most one bounded provider attempt.

    Failure retains the factual report and explicitly reports narrative unavailability.
    It never substitutes a fake narrative, another role, or synthetic source facts.
    """
    factual = build_structured_report(projection)
    request = factual.narrative_request
    budget = limits if limits is not None else ReportGenerationLimits()
    selected = provider if provider is not None else InactiveNarrativeProvider()
    try:
        if len(request.model_dump_json().encode("utf-8")) > budget.max_input_bytes:
            raise NarrativeUnavailable("input_limit_exceeded")
        output = await asyncio.wait_for(
            selected.generate(
                request,
                timeout_seconds=budget.timeout_seconds,
                max_output_chars=budget.max_output_chars,
            ),
            timeout=budget.timeout_seconds,
        )
        narrative = validate_narrative(request, output, max_output_chars=budget.max_output_chars)
    except TimeoutError:
        reason: UnavailableReason = "provider_timeout"
    except NarrativeUnavailable as error:
        reason = (
            error.reason
            if type(error.reason) is str and error.reason in _UNAVAILABLE_REASONS
            else "provider_error"
        )
    except Exception:
        # No exception text, prompt, configuration, provider response or credentials leave here.
        reason = "provider_error"
    else:
        return ReportGenerationResult(factual, "validated_narrative", narrative, None)
    return ReportGenerationResult(factual, "unavailable", None, reason)
