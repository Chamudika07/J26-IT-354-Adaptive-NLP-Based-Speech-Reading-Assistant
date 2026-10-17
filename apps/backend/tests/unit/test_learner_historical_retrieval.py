"""Synthetic unit tests for private bounded historical-session retrieval."""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

import app.modules.learner_modelling.historical as historical_module
import app.modules.learner_modelling.repository as repository_module
from app.modules.learner_modelling.analytics import ENGAGEMENT_FORMULA_VERSION
from app.modules.learner_modelling.dashboard_projections import project_learner_progress
from app.modules.learner_modelling.historical import (
    CANDIDATE_MAX_HISTORICAL_SESSIONS,
    CANDIDATE_MAX_REPORTING_WINDOW,
    HistoricalDataIntegrityError,
    HistoricalQueryBounds,
    HistoricalQueryValidationError,
    HistoricalResultLimitExceeded,
    HistoricalSessionQuery,
    HistoricalSessionRecord,
    historical_record_to_observation,
    historical_records_to_observations,
)
from app.modules.learner_modelling.longitudinal import (
    LongitudinalWindow,
    calculate_longitudinal_progress,
)
from app.modules.learner_modelling.repository import get_bounded_learner_session_history


def _utc(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


def _bounds(maximum_sessions: int = 1000, days: int = 90) -> HistoricalQueryBounds:
    return HistoricalQueryBounds(
        maximum_sessions=maximum_sessions,
        maximum_window=timedelta(days=days),
    )


def _query(
    *,
    learner_id: UUID | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    session_limit: int = 1000,
    bounds: HistoricalQueryBounds | None = None,
) -> HistoricalSessionQuery:
    return HistoricalSessionQuery(
        learner_id=learner_id or uuid4(),
        start_at_utc=start_at or _utc(1, 0),
        end_at_utc=end_at or _utc(31, 0),
        session_limit=session_limit,
        bounds=bounds or _bounds(),
    )


def _record(
    *,
    record_id: UUID | None = None,
    observed_at: datetime | None = None,
    task_type: str = "independent_reading",
    difficulty_tier: str = "intermediate",
    support_mode: str = "adaptive",
    completion_status: str = "completed",
    words_attempted: int = 100,
    words_correct: int = 80,
    target_word_count: int = 100,
    active_duration_ms: int = 60000,
    total_duration_ms: int = 70000,
    hesitation_count: int | None = 8,
    total_pause_duration_ms: int | None = 10000,
) -> HistoricalSessionRecord:
    return HistoricalSessionRecord(
        id=record_id or uuid4(),
        session_start_time=observed_at or _utc(2),
        task_type=task_type,
        difficulty_tier=difficulty_tier,
        support_mode=support_mode,
        completion_status=completion_status,
        words_attempted=words_attempted,
        words_correct=words_correct,
        target_word_count=target_word_count,
        active_duration_ms=active_duration_ms,
        total_duration_ms=total_duration_ms,
        hesitation_count=hesitation_count,
        total_pause_duration_ms=total_pause_duration_ms,
    )


def _row(record: HistoricalSessionRecord) -> tuple[object, ...]:
    return (
        record.id,
        record.session_start_time,
        record.task_type,
        record.difficulty_tier,
        record.support_mode,
        record.completion_status,
        record.words_attempted,
        record.words_correct,
        record.target_word_count,
        record.active_duration_ms,
        record.total_duration_ms,
        record.hesitation_count,
        record.total_pause_duration_ms,
    )


def _database(rows: list[tuple[object, ...]]) -> MagicMock:
    db = MagicMock(spec=Session)
    db.execute.return_value.tuples.return_value.all.return_value = rows
    return db


def _captured_statement(db: MagicMock) -> object:
    return db.execute.call_args.args[0]


def _compiled(statement: object) -> str:
    return str(
        statement.compile(  # type: ignore[attr-defined]
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )


def test_candidate_defaults_are_explicit_and_query_is_frozen() -> None:
    query = HistoricalSessionQuery(
        learner_id=uuid4(),
        start_at_utc=_utc(1),
        end_at_utc=_utc(2),
    )

    assert CANDIDATE_MAX_HISTORICAL_SESSIONS == 1000
    assert CANDIDATE_MAX_REPORTING_WINDOW == timedelta(days=90)
    assert query.session_limit == 1000
    with pytest.raises(FrozenInstanceError):
        query.session_limit = 5  # type: ignore[misc]


def test_valid_window_normalizes_equivalent_aware_offsets_to_utc() -> None:
    offset = timezone(timedelta(hours=5, minutes=30))
    query = _query(
        start_at=datetime(2026, 1, 1, 5, 30, tzinfo=offset),
        end_at=datetime(2026, 1, 2, 5, 30, tzinfo=offset),
    )

    assert query.start_at_utc == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert query.end_at_utc == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    assert query.start_at_utc.tzinfo is UTC
    assert query.end_at_utc.tzinfo is UTC


@pytest.mark.parametrize(
    ("start_at", "end_at", "message"),
    [
        (datetime(2026, 1, 1), _utc(2), "start_at_utc must be timezone-aware"),
        (_utc(1), datetime(2026, 1, 2), "end_at_utc must be timezone-aware"),
        (_utc(2), _utc(2), "start_at_utc must be earlier"),
        (_utc(3), _utc(2), "start_at_utc must be earlier"),
    ],
)
def test_invalid_windows_are_rejected(start_at: datetime, end_at: datetime, message: str) -> None:
    with pytest.raises(HistoricalQueryValidationError, match=message):
        _query(start_at=start_at, end_at=end_at)


def test_candidate_maximum_window_is_inclusive_and_can_be_tightened() -> None:
    exact = _query(start_at=_utc(1), end_at=_utc(1) + timedelta(days=90))
    assert exact.end_at_utc - exact.start_at_utc == timedelta(days=90)

    with pytest.raises(HistoricalQueryValidationError, match="historical-window maximum"):
        _query(start_at=_utc(1), end_at=_utc(1) + timedelta(days=90, seconds=1))
    with pytest.raises(HistoricalQueryValidationError, match="historical-window maximum"):
        _query(start_at=_utc(1), end_at=_utc(9), bounds=_bounds(days=7))


@pytest.mark.parametrize("limit", [0, -1, True, 1001])
def test_session_limit_must_be_positive_strict_and_within_trusted_bound(
    limit: int,
) -> None:
    with pytest.raises(HistoricalQueryValidationError):
        _query(session_limit=limit)


def test_query_selects_only_minimal_columns_and_mandatory_learner_scope() -> None:
    learner_id = UUID("00000000-0000-0000-0000-000000000123")
    query = _query(learner_id=learner_id)
    db = _database([])

    assert get_bounded_learner_session_history(db, query) == ()
    statement = _captured_statement(db)
    assert tuple(statement.selected_columns.keys()) == (  # type: ignore[attr-defined]
        "id",
        "session_start_time",
        "task_type",
        "difficulty_tier",
        "support_mode",
        "completion_status",
        "words_attempted",
        "words_correct",
        "target_word_count",
        "active_duration_ms",
        "total_duration_ms",
        "hesitation_count",
        "total_pause_duration_ms",
    )
    sql = _compiled(statement)
    assert "reading_sessions.learner_id = '00000000-0000-0000-0000-000000000123'" in sql
    for forbidden in (
        "document_id",
        "client_session_id",
        "request_digest",
        "calculated_engagement_score",
        "engagement_formula_version",
        "learner_profiles",
        "consent_records",
        "auth_sessions",
    ):
        assert forbidden not in sql


def test_query_uses_half_open_window_stable_order_and_limit_plus_one() -> None:
    query = _query(session_limit=7)
    db = _database([])

    get_bounded_learner_session_history(db, query)
    sql = " ".join(_compiled(_captured_statement(db)).split())

    assert "reading_sessions.session_start_time >=" in sql
    assert "reading_sessions.session_start_time <" in sql
    assert "ORDER BY reading_sessions.session_start_time ASC, reading_sessions.id ASC" in sql
    assert "LIMIT 8" in sql


def test_learner_scope_is_required_and_not_returned_in_records() -> None:
    with pytest.raises(HistoricalQueryValidationError, match="learner_id"):
        HistoricalSessionQuery(
            learner_id="00000000-0000-0000-0000-000000000123",  # type: ignore[arg-type]
            start_at_utc=_utc(1),
            end_at_utc=_utc(2),
        )

    source = _record()
    db = _database([_row(source)])
    result = get_bounded_learner_session_history(db, _query())
    assert result == (source,)
    assert not hasattr(result[0], "learner_id")


def test_equal_timestamp_tie_breaker_and_database_order_are_explicit() -> None:
    first = _record(record_id=UUID("00000000-0000-0000-0000-000000000001"), observed_at=_utc(4))
    second = _record(record_id=UUID("00000000-0000-0000-0000-000000000002"), observed_at=_utc(4))
    db = _database([_row(first), _row(second)])

    result = get_bounded_learner_session_history(db, _query())

    assert result == (first, second)
    assert "reading_sessions.id ASC" in _compiled(_captured_statement(db))


def test_exactly_at_limit_returns_complete_result() -> None:
    records = [_record(record_id=uuid4()) for _ in range(2)]
    db = _database([_row(record) for record in records])
    query = _query(session_limit=2, bounds=_bounds(maximum_sessions=2))

    assert get_bounded_learner_session_history(db, query) == tuple(records)


def test_one_over_limit_raises_without_returning_truncated_data() -> None:
    records = [_record(record_id=uuid4()) for _ in range(3)]
    db = _database([_row(record) for record in records])
    query = _query(session_limit=2, bounds=_bounds(maximum_sessions=2))

    with pytest.raises(HistoricalResultLimitExceeded) as exc_info:
        get_bounded_learner_session_history(db, query)

    assert str(exc_info.value) == ("Historical reading-session result exceeds the configured limit")
    assert all(str(record.id) not in str(exc_info.value) for record in records)


def test_mapping_preserves_missing_telemetry_and_formula_version() -> None:
    record = _record(hesitation_count=None, total_pause_duration_ms=None)

    observation = historical_record_to_observation(record)

    assert observation.telemetry.hesitation_count is None
    assert observation.telemetry.total_pause_duration_ms is None
    assert observation.engagement_score is None
    assert observation.engagement_formula_version == ENGAGEMENT_FORMULA_VERSION


def test_zero_duration_session_maps_without_fabricating_values() -> None:
    record = _record(
        words_attempted=0,
        words_correct=0,
        target_word_count=0,
        active_duration_ms=0,
        total_duration_ms=0,
        hesitation_count=None,
        total_pause_duration_ms=None,
    )

    observation = historical_record_to_observation(record)

    assert observation.telemetry.active_duration_ms == 0
    assert observation.telemetry.total_duration_ms == 0
    assert observation.telemetry.hesitation_count is None
    assert observation.engagement_score is None


def test_mapping_preserves_context_and_uses_row_id_only_for_internal_ordering() -> None:
    record_id = UUID("123e4567-e89b-12d3-a456-426614174000")
    record = _record(
        record_id=record_id,
        task_type="guided_echo_reading",
        difficulty_tier="advanced",
        support_mode="manual_override",
    )
    observation = historical_record_to_observation(record)

    assert observation.telemetry.session_id == str(record_id)
    assert observation.telemetry.task_type == "guided_echo_reading"
    assert observation.telemetry.difficulty_tier == "advanced"
    assert observation.telemetry.support_mode == "manual_override"

    report = calculate_longitudinal_progress(
        [observation],
        LongitudinalWindow(start_at_utc=_utc(1, 0), end_at_utc=_utc(5, 0)),
    )
    projection = project_learner_progress(report)
    assert str(record_id) not in json.dumps(projection.model_dump(mode="json"))


def test_valid_mapping_feeds_existing_metric_derivation_without_recalculation_here() -> None:
    observation = historical_record_to_observation(_record())
    report = calculate_longitudinal_progress(
        [observation],
        LongitudinalWindow(start_at_utc=_utc(1, 0), end_at_utc=_utc(5, 0)),
    )
    metrics = {metric.metric_name: metric for metric in report.partitions[0].metrics}

    assert metrics["reading_accuracy"].first_value == Decimal("0.8000")
    assert metrics["reading_fluency_wpm"].first_value == Decimal("100.00")
    assert metrics["hesitation_rate_per_word"].first_value == Decimal("0.0800")
    assert metrics["engagement_score"].first_value is not None
    assert metrics["engagement_score"].metric_calculation_version == ENGAGEMENT_FORMULA_VERSION


@pytest.mark.parametrize(
    "record",
    [
        _record(words_attempted=10, words_correct=11),
        _record(active_duration_ms=70001, total_duration_ms=70000),
        _record(task_type="unsupported_task"),
        _record(completion_status="unknown"),
        _record(observed_at=datetime(2026, 1, 2)),
    ],
)
def test_invalid_persisted_records_raise_one_sanitized_integrity_failure(
    record: HistoricalSessionRecord,
) -> None:
    with pytest.raises(HistoricalDataIntegrityError) as exc_info:
        historical_record_to_observation(record)

    assert str(exc_info.value) == "Stored reading-session data is invalid"
    assert str(record.id) not in str(exc_info.value)
    assert record.task_type not in str(exc_info.value)


def test_batch_mapping_does_not_silently_drop_an_invalid_record() -> None:
    records = (_record(), _record(words_attempted=5, words_correct=6), _record())

    with pytest.raises(HistoricalDataIntegrityError):
        historical_records_to_observations(records)


def test_query_and_mapping_modules_have_no_consent_http_or_cross_module_access() -> None:
    sources = (
        inspect.getsource(historical_module),
        inspect.getsource(repository_module),
    )
    imports: set[str] = set()
    for source in sources:
        tree = ast.parse(source)
        imports |= {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports |= {
            node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        }

    forbidden_prefixes = (
        "fastapi",
        "requests",
        "httpx",
        "socket",
        "urllib",
        "app.modules.auth",
        "app.modules.learners",
    )
    assert not any(name.startswith(forbidden_prefixes) for name in imports)
    assert "consent_records" not in "".join(sources)
    assert "learner_profiles" not in "".join(sources)
    assert "document_id" not in "".join(sources)


def test_repository_query_is_documented_as_non_authorizing() -> None:
    documentation = inspect.getdoc(get_bounded_learner_session_history)

    assert documentation is not None
    assert "not an authorization or consent boundary" in documentation
    assert "learning_support" in documentation
