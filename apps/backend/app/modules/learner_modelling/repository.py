"""Repository queries and writes for tables owned by learner_modelling.

All operations execute within the caller-provided SQLAlchemy session.
This repository never commits, never queries other modules' tables, and never
collects or stores unnecessary personal learner data.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.learner_modelling.historical import (
    HistoricalResultLimitExceeded,
    HistoricalSessionQuery,
    HistoricalSessionRecord,
)
from app.modules.learner_modelling.models import LearnerReadingSupportSettings, ReadingSession


def get_support_settings(db: Session, learner_id: UUID) -> LearnerReadingSupportSettings | None:
    """Private learner-scoped lookup; caller must already authorize and evaluate consent.

    No defaults, locks, writes or transaction ownership. Suppress implicit flushing
    of unrelated pending changes when SQLAlchemy executes the read.
    """
    statement = select(LearnerReadingSupportSettings).where(
        LearnerReadingSupportSettings.learner_id == learner_id
    )
    with db.no_autoflush:
        return db.scalars(statement).one_or_none()


def get_session_by_client_id(
    db: Session,
    learner_id: UUID,
    client_session_id: UUID,
    *,
    lock: bool = False,
) -> ReadingSession | None:
    """Fetch reading session by learner_id and client_session_id with optional row lock."""
    stmt = select(ReadingSession).where(
        ReadingSession.learner_id == learner_id,
        ReadingSession.client_session_id == client_session_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).one_or_none()


def insert_reading_session(
    db: Session,
    session: ReadingSession,
) -> ReadingSession:
    """Add a validated ReadingSession to the session and flush without committing."""
    db.add(session)
    db.flush()
    return session


def get_bounded_learner_session_history(
    db: Session,
    query: HistoricalSessionQuery,
) -> tuple[HistoricalSessionRecord, ...]:
    """Return one complete, minimal, deterministically ordered learner history.

    This repository function is not an authorization or consent boundary.  Its caller
    must authorize the exact learner and access path and evaluate active
    ``learning_support`` consent before invoking it.  The mandatory learner predicate
    must never be replaced by a client-controlled filter.

    The query fetches one row beyond the requested complete-result limit.  Overflow
    raises instead of returning a partial dataset that could produce a misleading
    longitudinal trend.
    """
    statement = (
        select(
            ReadingSession.id,
            ReadingSession.session_start_time,
            ReadingSession.task_type,
            ReadingSession.difficulty_tier,
            ReadingSession.support_mode,
            ReadingSession.completion_status,
            ReadingSession.words_attempted,
            ReadingSession.words_correct,
            ReadingSession.target_word_count,
            ReadingSession.active_duration_ms,
            ReadingSession.total_duration_ms,
            ReadingSession.hesitation_count,
            ReadingSession.total_pause_duration_ms,
        )
        .where(
            ReadingSession.learner_id == query.learner_id,
            ReadingSession.session_start_time >= query.start_at_utc,
            ReadingSession.session_start_time < query.end_at_utc,
        )
        .order_by(ReadingSession.session_start_time.asc(), ReadingSession.id.asc())
        .limit(query.session_limit + 1)
    )
    rows = db.execute(statement).tuples().all()
    if len(rows) > query.session_limit:
        raise HistoricalResultLimitExceeded(
            "Historical reading-session result exceeds the configured limit"
        )
    return tuple(HistoricalSessionRecord(*row) for row in rows)
