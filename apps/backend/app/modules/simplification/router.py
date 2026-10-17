"""FastAPI router for adaptive text simplification, vocabulary, and reading feedback."""

import logging
from collections.abc import Iterator
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core.exceptions import SecurityError, rate_limited
from app.modules.auth.dependencies import Authenticated, Database, RuntimeSettings
from app.modules.simplification import service
from app.modules.simplification.provider import (
    ProviderError,
    ProviderRateLimitError,
    SimplificationProvider,
    get_simplification_provider,
)
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


def get_simplification_provider_dep(
    settings: RuntimeSettings,
) -> Iterator[SimplificationProvider]:
    """Dependency that instantiates the configured simplification AI provider.

    Ensures HTTP clients and network resources are cleanly disposed of
    at the end of the request lifecycle.
    """
    try:
        provider = get_simplification_provider(settings)
    except (ProviderError, ValueError):
        raise SecurityError(
            status=503,
            code="service_unavailable",
            message="Service unavailable",
        ) from None
    try:
        yield provider
    finally:
        if hasattr(provider, "close"):
            provider.close()


ProviderDep = Annotated[SimplificationProvider, Depends(get_simplification_provider_dep)]


def _handle_provider_error(exc: Exception) -> NoReturn:
    """Map internal provider exceptions to sanitized API error responses."""
    if isinstance(exc, ProviderRateLimitError):
        retry_after = exc.retry_after if exc.retry_after is not None else 60
        raise rate_limited(retry_after) from None
    if isinstance(exc, (ProviderError, NotImplementedError)):
        raise SecurityError(
            status=503,
            code="service_unavailable",
            message="Service unavailable",
        ) from None
    raise exc


@router.post("/{learner_id}/simplify", response_model=SimplificationResponse)
def simplify_text(
    learner_id: UUID,
    payload: SimplificationRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
    provider: ProviderDep,
) -> SimplificationResponse:
    """Simplify input text and return adapted text with key vocabulary.

    Raises:
        SecurityError(404): If principal lacks permission for this learner.
        SecurityError(429): If the AI simplification provider rate limit is exceeded.
        SecurityError(503): If the AI simplification provider is unavailable or fails.
    """
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.simplify_text(db, principal, learner_id, payload, provider=provider)
    except (ProviderError, NotImplementedError) as exc:
        _handle_provider_error(exc)


@router.post("/{learner_id}/vocabulary/explain", response_model=WordExplanationResponse)
def explain_word(
    learner_id: UUID,
    payload: WordExplanationRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
    provider: ProviderDep,
) -> WordExplanationResponse:
    """Explain a word selected by the learner in plain language.

    Raises:
        SecurityError(404): If principal lacks permission or session does not belong to learner.
        SecurityError(429): If the AI vocabulary provider rate limit is exceeded.
        SecurityError(503): If the AI vocabulary provider is unavailable or fails.
    """
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.explain_word(db, principal, learner_id, payload, provider=provider)
    except (ProviderError, NotImplementedError) as exc:
        _handle_provider_error(exc)


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
