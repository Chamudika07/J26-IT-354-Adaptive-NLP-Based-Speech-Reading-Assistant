"""Business rules and explicit transaction boundaries for adaptive text simplification.

Responsibilities:
- Enforce authorization via the existing learner authorization framework.
- Coordinate repository functions for sessions, vocabulary, and feedback.
- Document and enforce the source-text retention boundary (never stored by default).
- Keep feedback append-only.
- Verify session ownership before exposing vocabulary or accepting feedback.

Intentionally out of scope for Component 2:
- Learner reading-level updates and analytics (Component 4).
- AI provider selection and execution (behind _execute_simplification, not yet implemented).
- Consent record creation or management (learner module owns that flow).
- Source-text retention: no consent evaluation service exists yet; source_text is
  always None until the consent framework is completed and reviewed.

Transaction discipline:
- Repository functions call flush() but never commit().
- Service functions commit() exactly once at the end of a successful write path,
  or rollback() and re-raise on any failure.
- Read-only service functions do not commit or rollback.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.learners.service import LearnerAction, authorize_learner_action
from app.modules.simplification import repository as repo
from app.modules.simplification.models import (
    SimplificationFeedback,
    SimplificationSession,
    SimplificationVocabulary,
)
from app.modules.simplification.schemas import (
    ReadingFeedbackRequest,
    ReadingFeedbackResponse,
    SimplificationRequest,
    SimplificationResponse,
    VocabularyItemResponse,
    VocabularySource,
    WordExplanationRequest,
    WordExplanationResponse,
)

logger = logging.getLogger(__name__)

# ── Internal error factories ───────────────────────────────────────────────────

_SESSION_NOT_FOUND = SecurityError(404, "not_found", "Resource not found")


def _session_not_found() -> SecurityError:
    """Return a fixed 404 for missing or unauthorized session access.

    Using the same message as the learner module prevents leaking whether a
    session exists under a different learner.
    """
    return _SESSION_NOT_FOUND


# ── Source-text retention boundary ────────────────────────────────────────────


def _sha256_hex(text: str) -> str:
    """Return the hex SHA-256 digest of the UTF-8 encoding of text."""
    return hashlib.sha256(text.encode()).hexdigest()


def _source_text_for_retention(source_text: str) -> str | None:
    """Return raw source text only when valid retention consent has been confirmed.

    LIMITATION / ARCHITECTURAL BOUNDARY:
    1. Learner authorization (`authorize_learner_action`) confirms only access rights
       for PERFORM_LEARNING_INTERACTION and explicitly specifies `consent_evaluated = False`.
       It does not evaluate or imply consent.
    2. The shared backend does not yet provide a consent evaluation service or public query
       interface to determine active, non-withdrawn consent for data processing purposes.
    3. Per repository engineering rules, Component 2 must not query another module's
       tables (such as `consent_records` or `consent_notice_versions`) directly.
    4. Consequently, no valid consent evaluator exists for Component 2 to verify retention consent.

    Until a validated consent evaluation service is provided by the learners module,
    this function MUST return None unconditionally. No caller may store raw source text.
    """
    # Consent evaluation not yet implemented — never retain source text.
    return None


# ── AI execution boundary ─────────────────────────────────────────────────────


def _execute_simplification(
    request: SimplificationRequest,
) -> dict[str, Any]:
    """Boundary function for AI simplification execution.

    This function is a placeholder that defines the contract for the AI layer.
    It must return a dict with keys matching the fields required by create_session:
      simplified_text, strategy_applied, target_reading_level, adaptation_attempt,
      output_length, ai_provider, ai_latency_ms, output_difficulty (optional),
      concepts_preserved (optional), validation_warnings (list[str]),
      vocabulary_items (list of VocabularyItemResponse-compatible dicts).

    The AI provider, model selection, retry logic, and rate-limit handling belong
    entirely inside this boundary.  Component 2 service functions must never call
    external AI APIs directly.
    """
    raise NotImplementedError(
        "AI simplification execution is not yet implemented. "
        "Implement this function before wiring up the simplification endpoint."
    )


# ── Authorization helpers ──────────────────────────────────────────────────────


def _require_learning_interaction(
    db: Session,
    principal: Principal,
    learner_id: UUID,
) -> None:
    """Raise SecurityError(404) if the principal cannot perform learning interactions."""
    authorize_learner_action(db, principal, learner_id, LearnerAction.PERFORM_LEARNING_INTERACTION)


def _require_session_ownership(
    db: Session,
    session_id: UUID,
    learner_id: UUID,
) -> SimplificationSession:
    """Return the session if it belongs to the learner; raise 404 otherwise.

    Always call _require_learning_interaction before this function so that
    authorization is verified before any session lookup is attempted.
    """
    session = repo.get_session(db, session_id=session_id, learner_id=learner_id)
    if session is None:
        raise _session_not_found()
    return session


# ── Public service functions ───────────────────────────────────────────────────


def simplify_text(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    request: SimplificationRequest,
) -> SimplificationResponse:
    """Authorize, execute, and persist a simplification session.

    Source text is never stored (consent framework not yet implemented).
    AI execution is delegated to _execute_simplification; this function
    never calls AI APIs directly.

    Raises:
        SecurityError(404): Principal is not authorized to interact with the learner.
        NotImplementedError: AI execution boundary not yet implemented.
    """
    _require_learning_interaction(db, principal, learner_id)
    try:
        ai_result = _execute_simplification(request)
        source_sha256 = _sha256_hex(request.source_text)
        session = repo.create_session(
            db,
            learner_id=learner_id,
            actor_user_id=principal.user_id,
            source_text_sha256=source_sha256,
            source_length=len(request.source_text),
            source_text=_source_text_for_retention(request.source_text),
            source_difficulty=request.source_difficulty,
            document_id=request.document_id,
            strategy_applied=ai_result["strategy_applied"],
            target_reading_level=ai_result["target_reading_level"],
            adaptation_attempt=ai_result["adaptation_attempt"],
            simplified_text=ai_result["simplified_text"],
            output_length=ai_result["output_length"],
            output_difficulty=ai_result.get("output_difficulty"),
            concepts_preserved=ai_result.get("concepts_preserved"),
            ai_provider=ai_result["ai_provider"],
            ai_latency_ms=ai_result["ai_latency_ms"],
            validation_warnings=ai_result.get("validation_warnings", []),
        )
        vocab_items: list[VocabularyItemResponse] = []
        for item_data in ai_result.get("vocabulary_items", []):
            vocab_row = repo.create_vocabulary(
                db,
                session_id=session.id,
                term=item_data["term"],
                simplified_definition=item_data["simplified_definition"],
                source=VocabularySource.AUTOMATIC,
                language_tag=item_data.get("language_tag", "en"),
                example_sentence=item_data.get("example_sentence"),
                synonyms=item_data.get("synonyms", []),
            )
            vocab_items.append(
                VocabularyItemResponse(
                    term=vocab_row.term,
                    simplified_definition=vocab_row.simplified_definition,
                    example_sentence=vocab_row.example_sentence,
                    synonyms=list(vocab_row.synonyms),
                    source=VocabularySource.AUTOMATIC,
                )
            )
        response = SimplificationResponse(
            session_id=session.id,
            learner_id=learner_id,
            simplified_text=session.simplified_text,
            strategy_applied=session.strategy_applied,
            target_reading_level=session.target_reading_level,
            estimated_output_difficulty=session.output_difficulty,
            adaptation_attempt=session.adaptation_attempt,
            vocabulary_items=vocab_items,
            warnings=list(session.validation_warnings),
            created_at=session.created_at,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def get_simplification_session(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    session_id: UUID,
) -> SimplificationSession:
    """Return a simplification session that belongs to the authorized learner.

    Raises:
        SecurityError(404): Not authorized, or session does not belong to learner.
    """
    _require_learning_interaction(db, principal, learner_id)
    return _require_session_ownership(db, session_id, learner_id)


def list_simplification_sessions(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    *,
    limit: int,
    offset: int = 0,
) -> list[SimplificationSession]:
    """Return a paged list of the learner's simplification sessions, newest first.

    Raises:
        SecurityError(404): Not authorized to perform learning interactions.
    """
    _require_learning_interaction(db, principal, learner_id)
    return repo.list_sessions_for_learner(db, learner_id=learner_id, limit=limit, offset=offset)


def explain_word(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    request: WordExplanationRequest,
) -> WordExplanationResponse:
    """Authorize and persist an on-demand vocabulary explanation.

    If request.session_id is provided, the session must belong to the learner.
    AI execution is delegated and not yet implemented.

    Raises:
        SecurityError(404): Not authorized, or session_id provided but not owned.
        NotImplementedError: AI execution boundary not yet implemented.
    """
    _require_learning_interaction(db, principal, learner_id)
    if request.session_id is not None:
        _require_session_ownership(db, request.session_id, learner_id)
    try:
        # AI boundary — not yet implemented; raises NotImplementedError.
        ai_result: dict[str, Any] = _execute_simplification(request)  # type: ignore[arg-type]
        vocab_row = repo.create_vocabulary(
            db,
            session_id=request.session_id,
            term=ai_result["term"],
            simplified_definition=ai_result["simplified_definition"],
            source=VocabularySource.USER,
            language_tag=ai_result.get("language_tag", "en"),
            example_sentence=ai_result.get("example_sentence"),
            synonyms=ai_result.get("synonyms", []),
        )
        response = WordExplanationResponse(
            learner_id=learner_id,
            item=VocabularyItemResponse(
                term=vocab_row.term,
                simplified_definition=vocab_row.simplified_definition,
                example_sentence=vocab_row.example_sentence,
                synonyms=list(vocab_row.synonyms),
                source=VocabularySource.USER,
            ),
            language_tag=ai_result.get("language_tag", "en"),
            session_id=request.session_id,
            created_at=vocab_row.created_at,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def get_vocabulary_for_session(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    session_id: UUID,
) -> list[SimplificationVocabulary]:
    """Return vocabulary entries for a session owned by the authorized learner.

    Session ownership is verified before any vocabulary rows are returned;
    SimplificationVocabulary has no learner_id column so this guard is essential.

    Raises:
        SecurityError(404): Not authorized or session not owned by learner.
    """
    _require_learning_interaction(db, principal, learner_id)
    _require_session_ownership(db, session_id, learner_id)
    return repo.get_vocabulary_for_session(db, session_id=session_id)


def record_reading_feedback(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    session_id: UUID,
    request: ReadingFeedbackRequest,
) -> ReadingFeedbackResponse:
    """Append post-reading feedback for an authorized learner's session.

    Feedback is append-only; no update or delete operations exist.
    If request.occurred_at is None the current database time is used.

    Raises:
        SecurityError(404): Not authorized or session not owned by learner.
    """
    _require_learning_interaction(db, principal, learner_id)
    _require_session_ownership(db, session_id, learner_id)
    try:
        occurred_at: datetime = request.occurred_at or repo.current_time(db)
        feedback = repo.record_feedback(
            db,
            session_id=session_id,
            learner_id=learner_id,
            feedback_signal=request.feedback_signal,
            occurred_at=occurred_at,
            recorded_by_user_id=principal.user_id,
            time_spent_seconds=request.time_spent_seconds,
            vocabulary_lookups_count=request.vocabulary_lookups_count,
            completed_reading=request.completed_reading,
        )
        response = ReadingFeedbackResponse(
            feedback_id=feedback.id,
            session_id=session_id,
            created_at=feedback.recorded_at,
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def get_reading_feedback(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    session_id: UUID,
) -> list[SimplificationFeedback]:
    """Return post-reading feedback events for an authorized learner's session.

    Session ownership is verified before any feedback rows are returned.

    Raises:
        SecurityError(404): Not authorized or session not owned by learner.
    """
    _require_learning_interaction(db, principal, learner_id)
    _require_session_ownership(db, session_id, learner_id)
    return repo.get_feedback_for_session(db, session_id=session_id, learner_id=learner_id)
