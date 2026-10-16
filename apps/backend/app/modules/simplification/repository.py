"""Queries and writes for tables owned by the simplification module.

Rules enforced here:
- No business logic or authorization decisions.
- Every learner-scoped query filters explicitly by learner_id.
- Feedback is append-only; no update or delete methods are provided.
- source_text is never set by default; callers must pass it explicitly when
  explicit retention consent has been granted.
- Raw SQLAlchemy errors are never re-raised directly to callers; the shared
  database_exception_handler in app.core.exceptions handles SQLAlchemyError
  at the API boundary, so repository functions let exceptions propagate
  naturally without broad swallowing.
"""

from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.simplification.models import (
    SimplificationFeedback,
    SimplificationSession,
    SimplificationVocabulary,
)

# ── Clock ──────────────────────────────────────────────────────────────────────


def current_time(db: Session) -> datetime:
    """Return the current database clock timestamp (timezone-aware UTC)."""
    return cast(datetime, db.execute(select(func.clock_timestamp())).scalar_one())


# ── SimplificationSession ─────────────────────────────────────────────────────


def create_session(
    db: Session,
    *,
    learner_id: UUID,
    actor_user_id: UUID,
    source_text_sha256: str,
    source_length: int,
    strategy_applied: str,
    target_reading_level: str,
    adaptation_attempt: int,
    simplified_text: str,
    output_length: int,
    ai_provider: str,
    ai_latency_ms: int,
    validation_warnings: list[str] | None = None,
    document_id: UUID | None = None,
    source_text: str | None = None,
    source_difficulty: Decimal | None = None,
    output_difficulty: Decimal | None = None,
    concepts_preserved: bool | None = None,
) -> SimplificationSession:
    """Persist a new simplification session and flush to obtain the generated PK.

    source_text must be passed only when explicit retention consent has been
    granted; it defaults to None and callers must opt in explicitly.
    """
    row = SimplificationSession(
        learner_id=learner_id,
        actor_user_id=actor_user_id,
        source_text_sha256=source_text_sha256,
        source_length=source_length,
        strategy_applied=strategy_applied,
        target_reading_level=target_reading_level,
        adaptation_attempt=adaptation_attempt,
        simplified_text=simplified_text,
        output_length=output_length,
        ai_provider=ai_provider,
        ai_latency_ms=ai_latency_ms,
        validation_warnings=validation_warnings if validation_warnings is not None else [],
        document_id=document_id,
        source_text=source_text,  # None by default; set only with retention consent
        source_difficulty=source_difficulty,
        output_difficulty=output_difficulty,
        concepts_preserved=concepts_preserved,
    )
    db.add(row)
    db.flush()
    return row


def get_session(
    db: Session,
    *,
    session_id: UUID,
    learner_id: UUID,
) -> SimplificationSession | None:
    """Return the session if it belongs to the given learner; otherwise None.

    The learner_id filter is always applied; callers must not omit it.
    """
    return db.scalar(
        select(SimplificationSession).where(
            SimplificationSession.id == session_id,
            SimplificationSession.learner_id == learner_id,
        )
    )


def list_sessions_for_learner(
    db: Session,
    *,
    learner_id: UUID,
    limit: int,
    offset: int = 0,
) -> list[SimplificationSession]:
    """Return a page of sessions for the given learner, newest first."""
    return list(
        db.scalars(
            select(SimplificationSession)
            .where(SimplificationSession.learner_id == learner_id)
            .order_by(SimplificationSession.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


# ── SimplificationVocabulary ──────────────────────────────────────────────────


def create_vocabulary(
    db: Session,
    *,
    term: str,
    simplified_definition: str,
    source: str,
    language_tag: str,
    session_id: UUID | None = None,
    example_sentence: str | None = None,
    synonyms: list[str] | None = None,
) -> SimplificationVocabulary:
    """Persist a vocabulary entry; session_id is nullable by design."""
    row = SimplificationVocabulary(
        session_id=session_id,
        term=term,
        simplified_definition=simplified_definition,
        source=source,
        language_tag=language_tag,
        example_sentence=example_sentence,
        synonyms=synonyms if synonyms is not None else [],
    )
    db.add(row)
    db.flush()
    return row


def get_vocabulary_for_session(
    db: Session,
    *,
    session_id: UUID,
) -> list[SimplificationVocabulary]:
    """Return all vocabulary entries linked to a session, ordered by insertion.

    SimplificationVocabulary has no learner_id column; isolation is achieved at
    the session level.  The service layer must verify that the session belongs to
    the target learner before calling this function.
    """
    return list(
        db.scalars(
            select(SimplificationVocabulary)
            .where(SimplificationVocabulary.session_id == session_id)
            .order_by(SimplificationVocabulary.created_at)
        )
    )


# ── SimplificationFeedback (append-only) ─────────────────────────────────────


def record_feedback(
    db: Session,
    *,
    session_id: UUID,
    learner_id: UUID,
    feedback_signal: str,
    occurred_at: datetime,
    recorded_by_user_id: UUID,
    time_spent_seconds: int | None = None,
    vocabulary_lookups_count: int | None = None,
    completed_reading: bool | None = None,
) -> SimplificationFeedback:
    """Append a feedback event; no update or delete methods exist for this model."""
    row = SimplificationFeedback(
        session_id=session_id,
        learner_id=learner_id,
        feedback_signal=feedback_signal,
        occurred_at=occurred_at,
        recorded_by_user_id=recorded_by_user_id,
        time_spent_seconds=time_spent_seconds,
        vocabulary_lookups_count=vocabulary_lookups_count,
        completed_reading=completed_reading,
    )
    db.add(row)
    db.flush()
    return row


def get_feedback_for_session(
    db: Session,
    *,
    session_id: UUID,
    learner_id: UUID,
) -> list[SimplificationFeedback]:
    """Return feedback for a session scoped to the given learner, oldest first."""
    return list(
        db.scalars(
            select(SimplificationFeedback)
            .where(
                SimplificationFeedback.session_id == session_id,
                SimplificationFeedback.learner_id == learner_id,
            )
            .order_by(SimplificationFeedback.occurred_at)
        )
    )
