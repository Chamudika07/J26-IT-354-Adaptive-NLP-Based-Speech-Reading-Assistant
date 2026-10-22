"""Shared pure fictional-evidence calculator. No I/O or production ingestion."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.modules.learner_modelling.adaptation_mapping import CompletedSessionEvidence
from app.modules.learner_modelling.analytics import (
    CompletionStatus,
    DifficultyTier,
    PartitionKey,
    SupportMode,
    TaskType,
    calculate_experimental_engagement,
    calculate_hesitation_frequency,
    calculate_reading_accuracy,
    calculate_words_per_minute,
)
from app.modules.learner_modelling.dashboard_projections import (
    DisplayTrend,
    project_learner_progress,
)
from app.modules.learner_modelling.longitudinal import LongitudinalObservation, LongitudinalWindow
from app.modules.learner_modelling.recommendation_composition import _compose_recommendation
from app.modules.learner_modelling.recommendation_mobile import (
    MobileRecommendation,
    _mobile_recommendation,
)
from app.modules.learner_modelling.recommendation_snapshot import _synthetic_inputs
from app.modules.learner_modelling.report_evidence import build_structured_report
from app.modules.learner_modelling.schemas import ReadingSessionIngest, SupportSettingsRead

Count = Annotated[StrictInt, Field(ge=0, le=1_000_000_000)]
_SYNTHETIC_LEARNER = UUID("00000000-0000-4000-8000-000000000000")


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SampleSession(Closed):
    id: UUID
    start: AwareDatetime
    end: AwareDatetime
    task: TaskType
    tier: DifficultyTier
    mode: SupportMode
    attempted: Count
    correct: Count
    target: Count
    activeMs: Count
    totalMs: Count
    hesitations: Count | None
    pauseCount: Count | None
    pauseMs: Count | None
    replayCount: Count | None
    completion: CompletionStatus

    def ingest(self) -> ReadingSessionIngest:
        return ReadingSessionIngest(
            learner_id=_SYNTHETIC_LEARNER,
            client_session_id=self.id,
            session_start_time=self.start,
            session_end_time=self.end,
            task_type=self.task,
            difficulty_tier=self.tier,
            support_mode=self.mode,
            completion_status=self.completion,
            words_attempted=self.attempted,
            words_correct=self.correct,
            target_word_count=self.target,
            active_duration_ms=self.activeMs,
            total_duration_ms=self.totalMs,
            hesitation_count=self.hesitations,
            pause_count=self.pauseCount,
            total_pause_duration_ms=self.pauseMs,
            replay_count=self.replayCount,
        )


class SampleFile(Closed):
    version: Literal[2]
    synthetic: Literal[True]
    verifiedTelemetry: Literal[False]
    records: Annotated[tuple[SampleSession, ...], Field(max_length=100)]

    @model_validator(mode="after")
    def validate_records(self) -> "SampleFile":
        if len({r.id for r in self.records}) != len(self.records):
            raise ValueError("Duplicate synthetic identities")
        for record in self.records:
            record.ingest()  # Existing relational/count/duration/completion contract.
        return self


class DemoContext(Closed):
    task: TaskType
    tier: DifficultyTier
    mode: SupportMode


class SampleHistoryItem(Closed):
    sequence: Annotated[int, Field(ge=1, le=100)]
    recordedAt: AwareDatetime
    accuracy: Decimal | None
    wpm: Decimal | None
    hesitation: Decimal | None
    experimentalEngagement: Decimal | None


class ConnectedPreview(Closed):
    schemaVersion: Literal["connected-synthetic-v2"] = "connected-synthetic-v2"
    synthetic: Literal[True] = True
    verifiedTelemetry: Literal[False] = False
    role: Literal["learner"] = "learner"
    source: Literal["component4-offline-backend"] = "component4-offline-backend"
    sourceDigest: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    generatedAt: AwareDatetime
    reportingStartUtc: AwareDatetime
    reportingEndUtc: AwareDatetime
    context: DemoContext
    settingsSource: Literal["approved-synthetic-settings-scenario"] = (
        "approved-synthetic-settings-scenario"
    )
    includedSessionCount: Annotated[int, Field(ge=0, le=100)]
    excludedSessionCount: Annotated[int, Field(ge=0, le=100)]
    metrics: Annotated[tuple[DisplayTrend, ...], Field(max_length=3)]
    history: Annotated[tuple[SampleHistoryItem, ...], Field(max_length=100)]
    reportStatements: tuple[str, ...]
    recommendation: MobileRecommendation | None
    recommendationExplanation: tuple[str, ...]
    disclaimer: str


def build_connected_preview(
    raw: str,
    window: LongitudinalWindow,
    context: DemoContext,
    *,
    generated_at: datetime | None = None,
) -> ConnectedPreview:
    if len(raw.encode("utf-8")) > 100_000:
        raise ValueError("Synthetic input exceeds size limit")
    envelope = json.loads(raw)
    if (
        not isinstance(envelope, dict)
        or envelope.get("synthetic") is not True
        or envelope.get("verifiedTelemetry") is not False
        or type(envelope.get("version")) is not int
    ):
        raise ValueError("Invalid synthetic envelope")
    samples = SampleFile.model_validate_json(raw)
    # This fixed learner-free simulator envelope cannot select a real learner.
    selected = [
        r
        for r in samples.records
        if r.completion == "completed"
        and window.start_at_utc <= r.start < window.end_at_utc
        and (r.task, r.tier, r.mode) == (context.task, context.tier, context.mode)
    ]
    evidence = CompletedSessionEvidence.from_observations(
        [
            LongitudinalObservation.from_telemetry(
                r.ingest().to_session_telemetry(session_id=str(r.id))
            )
            for r in selected
        ],
        window,
    )
    projection = project_learner_progress(evidence.report)
    recommendation = None
    explanations: tuple[str, ...] = (
        "Recommendation unavailable: no eligible completed sample sessions "
        "in the selected context/window.",
    )
    if selected:
        # Reuse approved synthetic preferences, explicitly configured for this demo context.
        settings = SupportSettingsRead.model_validate(
            _synthetic_inputs()[0].model_dump()
            | {"default_difficulty_tier": context.tier, "support_mode": context.mode}
        )
        key = PartitionKey(
            task_type=context.task, difficulty_tier=context.tier, support_mode=context.mode
        )
        decision = _compose_recommendation(settings, evidence, key)
        view = _mobile_recommendation(settings, decision, evidence=evidence, partition=key)
        explanations = view.reasons
        if view.evidence_state == "sufficient":
            recommendation = view
        else:
            explanations = (
                "Recommendation unavailable: insufficient comparable completed-session evidence.",
                *view.reasons,
            )
    history = []
    for index, record in enumerate(sorted(selected, key=lambda r: (r.start, str(r.id))), start=1):
        telemetry = record.ingest().to_session_telemetry()
        hesitation = calculate_hesitation_frequency(
            record.hesitations, record.attempted, record.activeMs
        )

        def number(value: float | None) -> Decimal | None:
            return Decimal(str(value)) if value is not None else None

        history.append(
            SampleHistoryItem(
                sequence=index,
                recordedAt=record.start,
                accuracy=number(calculate_reading_accuracy(record.attempted, record.correct)),
                wpm=number(calculate_words_per_minute(record.attempted, record.activeMs)),
                hesitation=number(hesitation.rate_per_word if hesitation else None),
                experimentalEngagement=number(calculate_experimental_engagement(telemetry).score),
            )
        )
    prepared = build_structured_report(projection)
    result = ConnectedPreview(
        sourceDigest=hashlib.sha256(samples.model_dump_json().encode()).hexdigest(),
        generatedAt=generated_at or datetime.now(UTC),
        reportingStartUtc=window.start_at_utc,
        reportingEndUtc=window.end_at_utc,
        context=context,
        includedSessionCount=len(selected),
        excludedSessionCount=len(samples.records) - len(selected),
        metrics=projection.contexts[0].metrics if projection.contexts else (),
        history=tuple(history),
        reportStatements=tuple(
            item.text for item in prepared.narrative_request.approved_statements
        ),
        recommendation=recommendation,
        recommendationExplanation=explanations,
        disclaimer=projection.disclaimer,
    )
    return ConnectedPreview.model_validate_json(result.model_dump_json())


def build_connected_replay(
    raw: str, window: LongitudinalWindow, context: DemoContext, *, generated_at: datetime
) -> tuple[ConnectedPreview, ...]:
    # Validate the full envelope before excluding any record. Prefixes simulate only
    # the explicitly identified input fixture, never arbitrary phone-side calculation.
    full = build_connected_preview(raw, window, context, generated_at=generated_at)
    samples = SampleFile.model_validate_json(raw)
    selected = sorted(
        (
            r
            for r in samples.records
            if r.completion == "completed"
            and window.start_at_utc <= r.start < window.end_at_utc
            and (r.task, r.tier, r.mode) == (context.task, context.tier, context.mode)
        ),
        key=lambda r: (r.start, str(r.id)),
    )
    steps = []
    for count in range(len(selected) + 1):
        prefix = SampleFile(
            version=2, synthetic=True, verifiedTelemetry=False, records=tuple(selected[:count])
        )
        steps.append(
            build_connected_preview(
                prefix.model_dump_json(), window, context, generated_at=full.generatedAt
            )
        )
    return tuple(steps)
