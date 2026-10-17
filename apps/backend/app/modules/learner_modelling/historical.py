"""Private contracts for complete, bounded historical reading-session retrieval.

These contracts are not authorization or consent boundaries.  A future service must
authenticate the principal, authorize the exact learner and access path, evaluate
active ``learning_support`` consent, and only then invoke the repository query for
that learner.  The resulting observations must be passed through one fixed role
projection before any response is returned.

The default limits are candidate safety bounds, not approved product policy.  Only
trusted backend configuration may replace them; request data must never define these
bounds directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.modules.learner_modelling.analytics import SessionTelemetry
from app.modules.learner_modelling.longitudinal import LongitudinalObservation

CANDIDATE_MAX_HISTORICAL_SESSIONS = 1000
CANDIDATE_MAX_REPORTING_WINDOW = timedelta(days=90)


class HistoricalRetrievalError(Exception):
    """Base for sanitized internal historical-retrieval failures."""


class HistoricalQueryValidationError(HistoricalRetrievalError, ValueError):
    """The trusted caller supplied invalid or out-of-bounds query parameters."""


class HistoricalResultLimitExceeded(HistoricalRetrievalError):
    """The complete result cannot be returned within the configured hard limit."""


class HistoricalDataIntegrityError(HistoricalRetrievalError):
    """Persisted telemetry cannot be safely represented by the analytics contracts."""


@dataclass(frozen=True, slots=True)
class HistoricalQueryBounds:
    """Trusted backend limits; never populate these values from request data."""

    maximum_sessions: int = CANDIDATE_MAX_HISTORICAL_SESSIONS
    maximum_window: timedelta = CANDIDATE_MAX_REPORTING_WINDOW

    def __post_init__(self) -> None:
        if type(self.maximum_sessions) is not int or self.maximum_sessions < 1:
            raise HistoricalQueryValidationError("maximum_sessions must be a positive integer")
        if not isinstance(self.maximum_window, timedelta) or self.maximum_window <= timedelta(0):
            raise HistoricalQueryValidationError("maximum_window must be a positive duration")


DEFAULT_HISTORICAL_QUERY_BOUNDS = HistoricalQueryBounds()


@dataclass(frozen=True, slots=True)
class HistoricalSessionQuery:
    """Validated learner-scoped UTC half-open query and complete-result limit."""

    learner_id: UUID
    start_at_utc: datetime
    end_at_utc: datetime
    session_limit: int = CANDIDATE_MAX_HISTORICAL_SESSIONS
    bounds: HistoricalQueryBounds = DEFAULT_HISTORICAL_QUERY_BOUNDS

    def __post_init__(self) -> None:
        if not isinstance(self.learner_id, UUID):
            raise HistoricalQueryValidationError("learner_id must be a UUID")
        if not isinstance(self.bounds, HistoricalQueryBounds):
            raise HistoricalQueryValidationError("bounds must be trusted historical query bounds")
        if type(self.session_limit) is not int or self.session_limit < 1:
            raise HistoricalQueryValidationError("session_limit must be a positive integer")
        if self.session_limit > self.bounds.maximum_sessions:
            raise HistoricalQueryValidationError(
                "session_limit exceeds the configured historical-session maximum"
            )

        start = _require_aware_utc(self.start_at_utc, "start_at_utc")
        end = _require_aware_utc(self.end_at_utc, "end_at_utc")
        if start >= end:
            raise HistoricalQueryValidationError("start_at_utc must be earlier than end_at_utc")
        if end - start > self.bounds.maximum_window:
            raise HistoricalQueryValidationError(
                "reporting interval exceeds the configured historical-window maximum"
            )
        object.__setattr__(self, "start_at_utc", start)
        object.__setattr__(self, "end_at_utc", end)


@dataclass(frozen=True, slots=True)
class HistoricalSessionRecord:
    """Minimal selected values required by existing longitudinal analytics."""

    id: UUID
    session_start_time: datetime
    task_type: str
    difficulty_tier: str
    support_mode: str
    completion_status: str
    words_attempted: int
    words_correct: int
    target_word_count: int
    active_duration_ms: int
    total_duration_ms: int
    hesitation_count: int | None
    total_pause_duration_ms: int | None


def historical_record_to_observation(
    record: HistoricalSessionRecord,
) -> LongitudinalObservation:
    """Map one minimal row to a validated, versioned longitudinal observation.

    The database row UUID is used only as the stable internal ordering identifier.
    Engagement is recalculated through the existing analytics contract, which carries
    the exact formula version used by this mapping operation.  Invalid persisted data
    fails as one sanitized internal error and is never silently omitted or coerced.
    """
    try:
        _validate_record_types(record)
        telemetry = SessionTelemetry(
            session_start_time=_require_aware_utc(record.session_start_time, "session_start_time"),
            session_id=str(record.id),
            words_attempted=record.words_attempted,
            words_correct=record.words_correct,
            target_word_count=record.target_word_count,
            active_duration_ms=record.active_duration_ms,
            total_duration_ms=record.total_duration_ms,
            hesitation_count=record.hesitation_count,
            total_pause_duration_ms=record.total_pause_duration_ms,
            pause_count=None,
            completion_status=record.completion_status,  # type: ignore[arg-type]
            task_type=record.task_type,
            difficulty_tier=record.difficulty_tier,
            support_mode=record.support_mode,
        )
        return LongitudinalObservation.from_telemetry(telemetry)
    except (HistoricalQueryValidationError, TypeError, ValueError, OverflowError) as exc:
        raise HistoricalDataIntegrityError("Stored reading-session data is invalid") from exc


def historical_records_to_observations(
    records: tuple[HistoricalSessionRecord, ...],
) -> tuple[LongitudinalObservation, ...]:
    """Map a complete ordered result without dropping any invalid record."""
    return tuple(historical_record_to_observation(record) for record in records)


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise HistoricalQueryValidationError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise HistoricalQueryValidationError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _validate_record_types(record: HistoricalSessionRecord) -> None:
    if not isinstance(record, HistoricalSessionRecord):
        raise TypeError("record must be a HistoricalSessionRecord")
    if not isinstance(record.id, UUID):
        raise TypeError("stored id must be a UUID")
    for field_name in (
        "task_type",
        "difficulty_tier",
        "support_mode",
        "completion_status",
    ):
        if not isinstance(getattr(record, field_name), str):
            raise TypeError(f"stored {field_name} must be text")
    for field_name in (
        "words_attempted",
        "words_correct",
        "target_word_count",
        "active_duration_ms",
        "total_duration_ms",
    ):
        if type(getattr(record, field_name)) is not int:
            raise TypeError(f"stored {field_name} must be an integer")
    for field_name in ("hesitation_count", "total_pause_duration_ms"):
        value = getattr(record, field_name)
        if value is not None and type(value) is not int:
            raise TypeError(f"stored {field_name} must be an integer or null")
