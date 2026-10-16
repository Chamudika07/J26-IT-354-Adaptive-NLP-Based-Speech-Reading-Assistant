"""Pydantic schemas for reading-session ingestion, canonical hashing, and reporting.

These schemas enforce validation, boundary invariants, and serialization rules
without embedding clinical, diagnostic, or database persistence logic.
"""

import hashlib
import json
from datetime import UTC
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import (
    AwareDatetime,
    Field,
    model_validator,
)

from app.core.schemas import Schema, VersionedReadSchema
from app.modules.learner_modelling.analytics import (
    CompletionStatus,
    DifficultyTier,
    SessionTelemetry,
    SupportMode,
    TaskType,
)
from app.modules.learner_modelling.models import ReadingSession

CANONICAL_DIGEST_VERSION: str = "v1"

NON_CLINICAL_DISCLAIMER: str = (
    "Experimental educational research heuristic only; "
    "does not measure or infer clinical, psychological, or attentional states."
)


class ReadingSessionIngest(Schema):
    """Validated input payload for reading-session ingestion.

    Rejects naive datetimes, unexpected fields, and out-of-order bounds.
    Missing nullable telemetry counters are preserved as None.
    """

    learner_id: UUID
    client_session_id: UUID
    document_id: UUID | None = None

    session_start_time: AwareDatetime
    session_end_time: AwareDatetime

    task_type: TaskType = "independent_reading"
    difficulty_tier: DifficultyTier = "intermediate"
    support_mode: SupportMode = "adaptive"
    completion_status: CompletionStatus = "completed"

    words_attempted: int = Field(ge=0)
    words_correct: int = Field(ge=0)
    target_word_count: int = Field(ge=0)
    active_duration_ms: int = Field(ge=0)
    total_duration_ms: int = Field(ge=0)

    hesitation_count: int | None = Field(default=None, ge=0)
    total_pause_duration_ms: int | None = Field(default=None, ge=0)
    pause_count: int | None = Field(default=None, ge=0)
    replay_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_invariants(self) -> "ReadingSessionIngest":
        if self.words_correct > self.words_attempted:
            raise ValueError(
                f"words_correct ({self.words_correct}) cannot exceed "
                f"words_attempted ({self.words_attempted})"
            )
        if self.active_duration_ms > self.total_duration_ms:
            raise ValueError(
                f"active_duration_ms ({self.active_duration_ms}) cannot exceed "
                f"total_duration_ms ({self.total_duration_ms})"
            )
        if (
            self.total_pause_duration_ms is not None
            and self.total_pause_duration_ms > self.total_duration_ms
        ):
            raise ValueError(
                f"total_pause_duration_ms ({self.total_pause_duration_ms}) cannot exceed "
                f"total_duration_ms ({self.total_duration_ms})"
            )
        if self.session_end_time < self.session_start_time:
            raise ValueError(
                f"session_end_time ({self.session_end_time}) cannot be earlier than "
                f"session_start_time ({self.session_start_time})"
            )
        return self

    def to_session_telemetry(self, session_id: str | None = None) -> SessionTelemetry:
        """Convert validated ingestion schema into an immutable SessionTelemetry dataclass."""
        return SessionTelemetry(
            session_start_time=self.session_start_time,
            words_attempted=self.words_attempted,
            words_correct=self.words_correct,
            target_word_count=self.target_word_count,
            active_duration_ms=self.active_duration_ms,
            total_duration_ms=self.total_duration_ms,
            hesitation_count=self.hesitation_count,
            total_pause_duration_ms=self.total_pause_duration_ms,
            pause_count=self.pause_count,
            completion_status=self.completion_status,
            session_id=session_id if session_id is not None else str(self.client_session_id),
            task_type=self.task_type,
            difficulty_tier=self.difficulty_tier,
            support_mode=self.support_mode,
        )

    def to_orm_model(
        self,
        request_digest: str,
        calculated_accuracy: Decimal | None = None,
        calculated_wpm: Decimal | None = None,
        calculated_hesitation_rate: Decimal | None = None,
        calculated_engagement_score: Decimal | None = None,
        engagement_formula_version: str | None = None,
        id: UUID | None = None,
    ) -> ReadingSession:
        """Instantiate a ReadingSession ORM instance without committing."""
        orm_kwargs: dict[str, Any] = {
            "learner_id": self.learner_id,
            "client_session_id": self.client_session_id,
            "request_digest": request_digest,
            "session_start_time": self.session_start_time,
            "session_end_time": self.session_end_time,
            "task_type": self.task_type,
            "difficulty_tier": self.difficulty_tier,
            "support_mode": self.support_mode,
            "completion_status": self.completion_status,
            "document_id": self.document_id,
            "words_attempted": self.words_attempted,
            "words_correct": self.words_correct,
            "target_word_count": self.target_word_count,
            "active_duration_ms": self.active_duration_ms,
            "total_duration_ms": self.total_duration_ms,
            "hesitation_count": self.hesitation_count,
            "total_pause_duration_ms": self.total_pause_duration_ms,
            "pause_count": self.pause_count,
            "replay_count": self.replay_count,
            "calculated_accuracy": calculated_accuracy,
            "calculated_wpm": calculated_wpm,
            "calculated_hesitation_rate": calculated_hesitation_rate,
            "calculated_engagement_score": calculated_engagement_score,
            "engagement_formula_version": engagement_formula_version,
        }
        if id is not None:
            orm_kwargs["id"] = id
        return ReadingSession(**orm_kwargs)


def build_canonical_payload(session: ReadingSessionIngest) -> dict[str, Any]:
    """Construct deterministic payload mapping for canonical hashing.

    Format version: v1
    All timestamps are normalized to UTC ISO 8601 strings.
    UUIDs are formatted as lowercase hyphenated strings.
    Missing/omitted nullable telemetry fields are consistently normalized to None.
    """
    return {
        "canonical_version": CANONICAL_DIGEST_VERSION,
        "learner_id": str(session.learner_id).lower(),
        "client_session_id": str(session.client_session_id).lower(),
        "document_id": (
            str(session.document_id).lower() if session.document_id is not None else None
        ),
        "session_start_time": session.session_start_time.astimezone(UTC).isoformat(),
        "session_end_time": session.session_end_time.astimezone(UTC).isoformat(),
        "task_type": session.task_type,
        "difficulty_tier": session.difficulty_tier,
        "support_mode": session.support_mode,
        "completion_status": session.completion_status,
        "words_attempted": session.words_attempted,
        "words_correct": session.words_correct,
        "target_word_count": session.target_word_count,
        "active_duration_ms": session.active_duration_ms,
        "total_duration_ms": session.total_duration_ms,
        "hesitation_count": session.hesitation_count,
        "total_pause_duration_ms": session.total_pause_duration_ms,
        "pause_count": session.pause_count,
        "replay_count": session.replay_count,
    }


def compute_canonical_session_digest(session: ReadingSessionIngest) -> str:
    """Compute deterministic SHA-256 digest of canonical session payload.

    Produces a 64-character lowercase hex string matching the
    `ck_reading_sessions_request_digest_format` database constraint.
    """
    payload = build_canonical_payload(session)
    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class CalculatedMetricsResponse(Schema):
    """Factual, non-diagnostic reading session metrics and research disclaimer."""

    calculated_accuracy: Decimal | None = None
    calculated_wpm: Decimal | None = None
    calculated_hesitation_rate: Decimal | None = None
    calculated_engagement_score: Decimal | None = None
    engagement_formula_version: str | None = None
    disclaimer: str = NON_CLINICAL_DISCLAIMER


class ReadingSessionResponse(VersionedReadSchema):
    """Full read schema for stored reading session, compatible with ReadingSession ORM."""

    learner_id: UUID
    client_session_id: UUID
    request_digest: str

    session_start_time: AwareDatetime
    session_end_time: AwareDatetime

    task_type: TaskType
    difficulty_tier: DifficultyTier
    support_mode: SupportMode
    completion_status: CompletionStatus

    document_id: UUID | None

    words_attempted: int
    words_correct: int
    target_word_count: int
    active_duration_ms: int
    total_duration_ms: int
    hesitation_count: int | None
    total_pause_duration_ms: int | None
    pause_count: int | None
    replay_count: int | None

    calculated_accuracy: Decimal | None = None
    calculated_wpm: Decimal | None = None
    calculated_hesitation_rate: Decimal | None = None
    calculated_engagement_score: Decimal | None = None
    engagement_formula_version: str | None = None
    disclaimer: str = NON_CLINICAL_DISCLAIMER

    @property
    def metrics(self) -> CalculatedMetricsResponse:
        """Extract calculated metrics into an isolated CalculatedMetricsResponse bundle."""
        return CalculatedMetricsResponse(
            calculated_accuracy=self.calculated_accuracy,
            calculated_wpm=self.calculated_wpm,
            calculated_hesitation_rate=self.calculated_hesitation_rate,
            calculated_engagement_score=self.calculated_engagement_score,
            engagement_formula_version=self.engagement_formula_version,
            disclaimer=self.disclaimer,
        )
