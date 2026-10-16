"""FastAPI router for adaptive text simplification, vocabulary, and reading feedback."""

import logging
from uuid import UUID

from fastapi import APIRouter, Response

from app.core.exceptions import SecurityError
from app.modules.auth.dependencies import Authenticated, Database
from app.modules.simplification import service
from app.modules.simplification.schemas import (
    ReadingFeedbackRequest,
    ReadingFeedbackResponse,
    SimplificationRequest,
    SimplificationResponse,
    WordExplanationRequest,
    WordExplanationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{learner_id}/simplify", response_model=SimplificationResponse)
def simplify_text(
    learner_id: UUID,
    payload: SimplificationRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> SimplificationResponse:
    """Simplify input text and return adapted text with key vocabulary.

    Raises:
        SecurityError(404): If principal lacks permission for this learner.
        SecurityError(503): If the AI simplification provider is not yet available.
    """
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.simplify_text(db, principal, learner_id, payload)
    except NotImplementedError:
        raise SecurityError(
            status=503,
            code="service_unavailable",
            message="Service unavailable",
        ) from None


@router.post("/{learner_id}/vocabulary/explain", response_model=WordExplanationResponse)
def explain_word(
    learner_id: UUID,
    payload: WordExplanationRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> WordExplanationResponse:
    """Explain a word selected by the learner in plain language.

    Raises:
        SecurityError(404): If principal lacks permission or session does not belong to learner.
        SecurityError(503): If the AI vocabulary provider is not yet available.
    """
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.explain_word(db, principal, learner_id, payload)
    except NotImplementedError:
        raise SecurityError(
            status=503,
            code="service_unavailable",
            message="Service unavailable",
        ) from None


@router.post(
    "/{learner_id}/sessions/{session_id}/feedback",
    response_model=ReadingFeedbackResponse,
)
def record_feedback(
    learner_id: UUID,
    session_id: UUID,
    payload: ReadingFeedbackRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> ReadingFeedbackResponse:
    """Record learner post-reading feedback for a simplification session.

    Raises:
        SecurityError(404): If principal lacks permission or session does not belong to learner.
    """
    response.headers["Cache-Control"] = "no-store"
    return service.record_reading_feedback(db, principal, learner_id, session_id, payload)
