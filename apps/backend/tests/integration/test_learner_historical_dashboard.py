"""PostgreSQL integration coverage for private Component 4 history and dashboards.

The shared fixtures guard an explicitly configured disposable ``*_test`` database.
Consent remains a synthetic callback because no production consent policy is approved.
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.auth.models import User
from app.modules.learner_modelling import repository as repo
from app.modules.learner_modelling import service
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    LearnerProgressProjection,
)
from app.modules.learner_modelling.historical import (
    HistoricalQueryBounds,
    HistoricalResultLimitExceeded,
    HistoricalSessionQuery,
    HistoricalSessionRecord,
    historical_record_to_observation,
)
from app.modules.learner_modelling.models import ReadingSession
from app.modules.learners import service as learner_service
from app.modules.learners.models import LearnerProfile
from app.modules.learners.service import LearnerAction, LearnerAuthorization

pytestmark = pytest.mark.integration


def _utc(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


def _reading_session(
    learner_id: UUID,
    observed_at: datetime,
    *,
    session_id: UUID | None = None,
    words_attempted: int = 100,
    words_correct: int = 80,
    hesitation_count: int | None = 8,
    total_pause_duration_ms: int | None = 10_000,
) -> ReadingSession:
    identity = session_id or uuid4()
    return ReadingSession(
        id=identity,
        learner_id=learner_id,
        client_session_id=uuid4(),
        request_digest=identity.hex * 2,
        session_start_time=observed_at,
        session_end_time=observed_at + timedelta(minutes=1),
        task_type="independent_reading",
        difficulty_tier="intermediate",
        support_mode="adaptive",
        completion_status="completed",
        document_id=None,
        words_attempted=words_attempted,
        words_correct=words_correct,
        target_word_count=100,
        active_duration_ms=60_000,
        total_duration_ms=70_000,
        hesitation_count=hesitation_count,
        total_pause_duration_ms=total_pause_duration_ms,
        pause_count=None,
        replay_count=None,
        calculated_accuracy=None,
        calculated_wpm=None,
        calculated_hesitation_rate=None,
        calculated_engagement_score=None,
        engagement_formula_version=None,
    )


@pytest.fixture
def learner_context(
    db_session: Session,
    active_user: User,
) -> tuple[LearnerProfile, LearnerProfile, Principal]:
    learner = LearnerProfile(
        learner_user_id=active_user.id,
        display_name="Synthetic Component Four Learner",
        created_by_user_id=active_user.id,
    )
    other_learner = LearnerProfile(
        display_name="Other Synthetic Component Four Learner",
        created_by_user_id=active_user.id,
    )
    db_session.add_all((learner, other_learner))
    db_session.flush()

    assert active_user.login_handle is not None
    now = _utc(1)
    principal = Principal(
        user_id=active_user.id,
        login_handle=active_user.login_handle,
        roles=frozenset({"learner"}),
        session_id=uuid4(),
        authenticated_at=now,
        token_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    return learner, other_learner, principal


def _query(
    learner_id: UUID,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    session_limit: int = 1000,
    maximum_sessions: int = 1000,
) -> HistoricalSessionQuery:
    return HistoricalSessionQuery(
        learner_id=learner_id,
        start_at_utc=start_at or _utc(1),
        end_at_utc=end_at or _utc(3),
        session_limit=session_limit,
        bounds=HistoricalQueryBounds(
            maximum_sessions=maximum_sessions,
            maximum_window=timedelta(days=90),
        ),
    )


def test_history_is_learner_scoped_half_open_and_stably_ordered(
    db_session: Session,
    learner_context: tuple[LearnerProfile, LearnerProfile, Principal],
) -> None:
    learner, other_learner, _principal = learner_context
    start_id = UUID("00000000-0000-0000-0000-000000000020")
    first_equal_id = UUID("00000000-0000-0000-0000-000000000001")
    second_equal_id = UUID("00000000-0000-0000-0000-000000000002")
    start = _utc(1)
    end = _utc(2)
    equal_time = start + timedelta(hours=12)

    db_session.add_all(
        (
            _reading_session(learner.id, start - timedelta(seconds=1)),
            _reading_session(learner.id, start, session_id=start_id),
            _reading_session(learner.id, equal_time, session_id=second_equal_id),
            _reading_session(learner.id, equal_time, session_id=first_equal_id),
            _reading_session(learner.id, end),
            _reading_session(other_learner.id, start + timedelta(hours=1)),
        )
    )
    db_session.flush()

    sri_lanka = timezone(timedelta(hours=5, minutes=30))
    query = _query(
        learner.id,
        start_at=datetime(2026, 1, 1, 5, 30, tzinfo=sri_lanka),
        end_at=datetime(2026, 1, 2, 5, 30, tzinfo=sri_lanka),
    )
    records = repo.get_bounded_learner_session_history(db_session, query)

    assert query.start_at_utc == start
    assert query.end_at_utc == end
    assert [record.id for record in records] == [
        start_id,
        first_equal_id,
        second_equal_id,
    ]
    assert all(not hasattr(record, "learner_id") for record in records)
    assert tuple(field.name for field in fields(HistoricalSessionRecord)) == (
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


def test_history_overflow_refuses_partial_result(
    db_session: Session,
    learner_context: tuple[LearnerProfile, LearnerProfile, Principal],
) -> None:
    learner, _other_learner, _principal = learner_context
    session_ids = (
        UUID("00000000-0000-0000-0000-000000000101"),
        UUID("00000000-0000-0000-0000-000000000102"),
        UUID("00000000-0000-0000-0000-000000000103"),
    )
    db_session.add_all(
        _reading_session(
            learner.id,
            _utc(1, index + 1),
            session_id=session_id,
        )
        for index, session_id in enumerate(session_ids)
    )
    db_session.flush()

    exact = repo.get_bounded_learner_session_history(
        db_session,
        _query(learner.id, session_limit=3, maximum_sessions=3),
    )
    assert tuple(record.id for record in exact) == session_ids

    with pytest.raises(HistoricalResultLimitExceeded) as exc_info:
        repo.get_bounded_learner_session_history(
            db_session,
            _query(learner.id, session_limit=2, maximum_sessions=3),
        )

    assert str(exc_info.value) == ("Historical reading-session result exceeds the configured limit")
    assert all(str(session_id) not in str(exc_info.value) for session_id in session_ids)


def test_history_round_trips_nullable_measurements(
    db_session: Session,
    learner_context: tuple[LearnerProfile, LearnerProfile, Principal],
) -> None:
    learner, _other_learner, _principal = learner_context
    row = _reading_session(
        learner.id,
        _utc(1, 4),
        hesitation_count=None,
        total_pause_duration_ms=None,
    )
    db_session.add(row)
    db_session.flush()

    records = repo.get_bounded_learner_session_history(db_session, _query(learner.id))

    assert len(records) == 1
    assert records[0].hesitation_count is None
    assert records[0].total_pause_duration_ms is None
    observation = historical_record_to_observation(records[0])
    assert observation.telemetry.hesitation_count is None
    assert observation.telemetry.total_pause_duration_ms is None
    assert observation.engagement_score is None


def test_postgresql_constraints_reject_invalid_session_telemetry(
    db_session: Session,
    learner_context: tuple[LearnerProfile, LearnerProfile, Principal],
) -> None:
    learner, _other_learner, _principal = learner_context
    invalid = _reading_session(
        learner.id,
        _utc(1, 5),
        words_attempted=10,
        words_correct=11,
    )

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(invalid)
        db_session.flush()

    persisted_id = db_session.scalar(
        select(ReadingSession.id).where(ReadingSession.id == invalid.id)
    )
    assert persisted_id is None


def test_dashboard_fails_closed_without_approved_consent(
    db_session: Session,
    learner_context: tuple[LearnerProfile, LearnerProfile, Principal],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learner, _other_learner, principal = learner_context
    query = _query(learner.id)
    history = MagicMock()
    monkeypatch.setattr(repo, "get_bounded_learner_session_history", history)

    with pytest.raises(SecurityError) as missing_error:
        service.read_learner_progress(db_session, principal, query)
    assert (missing_error.value.status, missing_error.value.code) == (403, "consent_required")

    def deny_synthetic_consent(_db: Session, _learner_id: UUID, _purpose: str) -> None:
        raise SecurityError(403, "consent_required", "Consent required")

    with pytest.raises(SecurityError) as denied_error:
        service.read_learner_progress(
            db_session,
            principal,
            query,
            consent_checker=deny_synthetic_consent,
        )
    assert (denied_error.value.status, denied_error.value.code) == (403, "consent_required")
    history.assert_not_called()


def test_dashboard_reads_postgresql_with_synthetic_approved_consent(
    db_session: Session,
    learner_context: tuple[LearnerProfile, LearnerProfile, Principal],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learner, other_learner, principal = learner_context
    session_ids = (uuid4(), uuid4())
    db_session.add_all(
        (
            _reading_session(learner.id, _utc(1, 8), session_id=session_ids[0]),
            _reading_session(learner.id, _utc(1, 9), session_id=session_ids[1]),
            _reading_session(other_learner.id, _utc(1, 10)),
        )
    )
    db_session.flush()

    grants: list[LearnerAuthorization] = []

    def record_authorization(
        db: Session,
        actor: Principal,
        learner_id: UUID,
        action: LearnerAction,
    ) -> LearnerAuthorization:
        grant = learner_service.authorize_learner_action(db, actor, learner_id, action)
        grants.append(grant)
        return grant

    monkeypatch.setattr(service, "authorize_learner_action", record_authorization)

    consent_calls: list[tuple[UUID, str]] = []

    def allow_synthetic_consent(db: Session, learner_id: UUID, purpose: str) -> None:
        assert db is db_session
        consent_calls.append((learner_id, purpose))

    statements: list[str] = []

    def capture_statement(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        statements.append(statement.lower())

    connection = db_session.connection()
    event.listen(connection, "before_cursor_execute", capture_statement)
    try:
        result = service.read_learner_progress(
            db_session,
            principal,
            _query(learner.id),
            consent_checker=allow_synthetic_consent,
        )
    finally:
        event.remove(connection, "before_cursor_execute", capture_statement)

    assert type(result) is LearnerProgressProjection
    assert not isinstance(result, (GuardianSummaryProjection, EducatorAnalyticsProjection))
    assert result.included_session_count == 2
    assert consent_calls == [(learner.id, "learning_support")]
    assert len(grants) == 1
    assert grants[0].action is LearnerAction.READ_EDUCATIONAL_SUMMARY
    assert grants[0].access_path == "self"
    assert any("reading_sessions" in statement for statement in statements)
    assert all("consent_records" not in statement for statement in statements)
    assert all("consent_notice_versions" not in statement for statement in statements)

    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert str(learner.id) not in serialized
    assert str(other_learner.id) not in serialized
    assert all(str(session_id) not in serialized for session_id in session_ids)
