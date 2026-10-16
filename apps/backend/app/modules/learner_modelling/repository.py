"""Repository queries and writes for tables owned by learner_modelling.

All operations execute within the caller-provided SQLAlchemy session.
This repository never commits, never queries other modules' tables, and never
collects or stores unnecessary personal learner data.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.learner_modelling.models import ReadingSession


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
