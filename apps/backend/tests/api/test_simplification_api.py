"""API integration and contract tests for Component 2 simplification endpoints.

These tests run completely offline without requiring a live PostgreSQL database,
using FastAPI dependency overrides and service-layer mocking.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.db.session import get_session
from app.modules.auth.contracts import Principal
from app.modules.auth.dependencies import get_current_principal
from app.modules.simplification.schemas import (
    ReadingLevel,
    SimplificationResponse,
    SimplificationStrategy,
    VocabularyItemResponse,
    VocabularySource,
    WordExplanationResponse,
)

LEARNER_ID = uuid4()
SESSION_ID = uuid4()
FEEDBACK_ID = uuid4()
ACTOR_ID = uuid4()
NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_principal(user_id: UUID = ACTOR_ID) -> Principal:
    return Principal(
        user_id=user_id,
        login_handle="synthetic_learner",
        roles=frozenset({"learner"}),
        session_id=uuid4(),
        authenticated_at=NOW,
        token_id=uuid4(),
        issued_at=NOW,
        expires_at=NOW,
    )


@pytest.fixture
def auth_client(application: FastAPI, client: TestClient) -> Iterator[TestClient]:
    """TestClient with authentication and database dependencies mocked."""
    principal = _make_principal()
    mock_db = MagicMock(spec=Session)
    application.dependency_overrides[get_current_principal] = lambda: principal
    application.dependency_overrides[get_session] = lambda: mock_db
    try:
        yield client
    finally:
        application.dependency_overrides.pop(get_current_principal, None)
        application.dependency_overrides.pop(get_session, None)


# ── Endpoint 1: POST /api/v1/simplification/{learner_id}/simplify ──────────────


def test_simplify_unauthenticated(client: TestClient) -> None:
    """Missing bearer token must yield 401 Authentication Required."""
    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    response = client.post(url, json={"source_text": "Sample text to simplify."})
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "authentication_required"
    assert response.headers.get("Cache-Control") == "no-store"


def test_simplify_provider_unavailable(auth_client: TestClient) -> None:
    """When the AI provider is unimplemented (NotImplementedError), return 503."""
    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    with patch(
        "app.modules.simplification.service._execute_simplification",
        side_effect=NotImplementedError("AI provider not configured"),
    ):
        with patch(
            "app.modules.simplification.service.authorize_learner_action",
            return_value=None,
        ):
            response = auth_client.post(url, json={"source_text": "Photosynthesis is the process."})
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "service_unavailable"
    assert data["error"]["message"] == "Service unavailable"
    assert response.headers.get("Cache-Control") == "no-store"


def test_simplify_success_mocked(auth_client: TestClient) -> None:
    """When the service completes simplification, return 200 with response schema."""
    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    mock_response = SimplificationResponse(
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        simplified_text="Plants make food with sunlight.",
        strategy_applied=SimplificationStrategy.FULL_REWRITE,
        target_reading_level=ReadingLevel.BEGINNER,
        estimated_output_difficulty=None,
        adaptation_attempt=1,
        vocabulary_items=[
            VocabularyItemResponse(
                term="photosynthesis",
                simplified_definition="How plants make food from light.",
                example_sentence=None,
                synonyms=[],
                source=VocabularySource.AUTOMATIC,
            )
        ],
        warnings=[],
        created_at=NOW,
    )
    with patch(
        "app.modules.simplification.service.simplify_text",
        return_value=mock_response,
    ):
        response = auth_client.post(
            url,
            json={
                "source_text": "Photosynthesis is the biochemical process.",
                "target_reading_level": "beginner",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == str(SESSION_ID)
    assert data["learner_id"] == str(LEARNER_ID)
    assert data["simplified_text"] == "Plants make food with sunlight."
    assert data["strategy_applied"] == "full_rewrite"
    assert len(data["vocabulary_items"]) == 1
    assert data["vocabulary_items"][0]["term"] == "photosynthesis"
    assert response.headers.get("Cache-Control") == "no-store"


def test_simplify_validation_empty_source_text(auth_client: TestClient) -> None:
    """Empty or whitespace-only source text must be rejected with 422."""
    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    response = auth_client.post(url, json={"source_text": "   "})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


def test_simplify_validation_missing_source_text(auth_client: TestClient) -> None:
    """Missing source_text field must be rejected with 422."""
    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    response = auth_client.post(url, json={})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


def test_simplify_rejects_alternative_learner_id_in_body(auth_client: TestClient) -> None:
    """Request schema forbids extra fields like learner_id in body (extra='forbid')."""
    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    response = auth_client.post(
        url,
        json={
            "source_text": "Some valid source text.",
            "learner_id": str(uuid4()),
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


def test_simplify_authorization_denied(auth_client: TestClient) -> None:
    """When learner authorization fails, service raises SecurityError 404."""
    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    with patch(
        "app.modules.simplification.service.simplify_text",
        side_effect=SecurityError(404, "not_found", "Resource not found"),
    ):
        response = auth_client.post(url, json={"source_text": "Valid source text."})
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "not_found"


# ── Endpoint 2: POST /api/v1/simplification/{learner_id}/vocabulary/explain ──


def test_explain_word_unauthenticated(client: TestClient) -> None:
    """Unauthenticated request to explain_word must return 401."""
    url = f"/api/v1/simplification/{LEARNER_ID}/vocabulary/explain"
    response = client.post(url, json={"term": "chlorophyll"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "authentication_required"


def test_explain_word_provider_unavailable(auth_client: TestClient) -> None:
    """When the AI vocabulary provider is unimplemented, return 503."""
    url = f"/api/v1/simplification/{LEARNER_ID}/vocabulary/explain"
    with patch(
        "app.modules.simplification.service._execute_simplification",
        side_effect=NotImplementedError("AI provider not configured"),
    ):
        with patch(
            "app.modules.simplification.service.authorize_learner_action",
            return_value=None,
        ):
            response = auth_client.post(url, json={"term": "chlorophyll"})
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "service_unavailable"
    assert data["error"]["message"] == "Service unavailable"
    assert response.headers.get("Cache-Control") == "no-store"


def test_explain_word_success_mocked(auth_client: TestClient) -> None:
    """When service completes explanation, return 200 with WordExplanationResponse."""
    url = f"/api/v1/simplification/{LEARNER_ID}/vocabulary/explain"
    mock_response = WordExplanationResponse(
        learner_id=LEARNER_ID,
        item=VocabularyItemResponse(
            term="chlorophyll",
            simplified_definition="A green substance that plants use to absorb sunlight.",
            example_sentence="Leaves are green because of chlorophyll.",
            synonyms=["plant pigment"],
            source=VocabularySource.USER,
        ),
        language_tag="en",
        session_id=SESSION_ID,
        created_at=NOW,
    )
    with patch(
        "app.modules.simplification.service.explain_word",
        return_value=mock_response,
    ):
        response = auth_client.post(
            url,
            json={
                "term": "chlorophyll",
                "session_id": str(SESSION_ID),
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["learner_id"] == str(LEARNER_ID)
    assert data["item"]["term"] == "chlorophyll"
    assert data["item"]["source"] == "user"
    assert data["session_id"] == str(SESSION_ID)
    assert response.headers.get("Cache-Control") == "no-store"


def test_explain_word_validation_empty_term(auth_client: TestClient) -> None:
    """Empty term must return 422."""
    url = f"/api/v1/simplification/{LEARNER_ID}/vocabulary/explain"
    response = auth_client.post(url, json={"term": "   "})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


def test_explain_word_authorization_denied(auth_client: TestClient) -> None:
    """When authorization or session ownership fails, return 404."""
    url = f"/api/v1/simplification/{LEARNER_ID}/vocabulary/explain"
    with patch(
        "app.modules.simplification.service.explain_word",
        side_effect=SecurityError(404, "not_found", "Resource not found"),
    ):
        response = auth_client.post(url, json={"term": "chlorophyll"})
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "not_found"


# ── Endpoint 3: POST /api/v1/simplification/{learner_id}/sessions/{session_id}/feedback ──


def test_record_feedback_unauthenticated(client: TestClient) -> None:
    """Unauthenticated request to feedback endpoint must return 401."""
    url = f"/api/v1/simplification/{LEARNER_ID}/sessions/{SESSION_ID}/feedback"
    response = client.post(url, json={"feedback_signal": "just_right"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "authentication_required"


def test_record_feedback_success(auth_client: TestClient) -> None:
    """Valid feedback submission returns 200 with ReadingFeedbackResponse."""
    from app.modules.simplification.schemas import ReadingFeedbackResponse

    url = f"/api/v1/simplification/{LEARNER_ID}/sessions/{SESSION_ID}/feedback"
    mock_response = ReadingFeedbackResponse(
        feedback_id=FEEDBACK_ID,
        session_id=SESSION_ID,
        feedback_recorded=True,
        created_at=NOW,
    )
    with patch(
        "app.modules.simplification.service.record_reading_feedback",
        return_value=mock_response,
    ):
        response = auth_client.post(
            url,
            json={
                "feedback_signal": "just_right",
                "time_spent_seconds": 60,
                "vocabulary_lookups_count": 2,
                "completed_reading": True,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["feedback_id"] == str(FEEDBACK_ID)
    assert data["session_id"] == str(SESSION_ID)
    assert data["feedback_recorded"] is True
    assert response.headers.get("Cache-Control") == "no-store"


def test_record_feedback_invalid_signal(auth_client: TestClient) -> None:
    """Invalid feedback_signal enum value must return 422."""
    url = f"/api/v1/simplification/{LEARNER_ID}/sessions/{SESSION_ID}/feedback"
    response = auth_client.post(url, json={"feedback_signal": "not_a_valid_signal"})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


def test_record_feedback_invalid_time_spent(auth_client: TestClient) -> None:
    """Negative time_spent_seconds must return 422."""
    url = f"/api/v1/simplification/{LEARNER_ID}/sessions/{SESSION_ID}/feedback"
    response = auth_client.post(
        url,
        json={"feedback_signal": "too_easy", "time_spent_seconds": -5},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


def test_record_feedback_session_not_owned_returns_404(auth_client: TestClient) -> None:
    """When session belongs to another learner, service raises 404, returning 404."""
    url = f"/api/v1/simplification/{LEARNER_ID}/sessions/{SESSION_ID}/feedback"
    with patch(
        "app.modules.simplification.service.record_reading_feedback",
        side_effect=SecurityError(404, "not_found", "Resource not found"),
    ):
        response = auth_client.post(url, json={"feedback_signal": "too_hard"})
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "not_found"


def test_record_feedback_rejects_extra_fields(auth_client: TestClient) -> None:
    """Extra fields in feedback body are forbidden (extra='forbid') -> 422."""
    url = f"/api/v1/simplification/{LEARNER_ID}/sessions/{SESSION_ID}/feedback"
    response = auth_client.post(
        url,
        json={
            "feedback_signal": "just_right",
            "medical_diagnosis": "reading disorder",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


def test_simplify_database_error_yields_503(auth_client: TestClient) -> None:
    """When a database exception occurs, database_exception_handler returns 503."""
    from sqlalchemy.exc import OperationalError

    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    with patch(
        "app.modules.simplification.service.simplify_text",
        side_effect=OperationalError("SELECT 1", {}, Exception("db error")),
    ):
        response = auth_client.post(url, json={"source_text": "Valid text."})
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "service_unavailable"
    assert data["error"]["message"] == "Service unavailable"
    assert response.headers.get("Cache-Control") == "no-store"


# ── Provider integration & error mapping tests ────────────────────────────────


def test_simplify_rate_limited_yields_429_with_retry_after(auth_client: TestClient) -> None:
    """When the AI provider raises ProviderRateLimitError, return 429 with Retry-After."""
    from app.modules.simplification.provider.base import ProviderRateLimitError

    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    with patch(
        "app.modules.simplification.service.simplify_text",
        side_effect=ProviderRateLimitError("Rate limit exceeded", retry_after=45),
    ):
        response = auth_client.post(url, json={"source_text": "Some text."})
    assert response.status_code == 429
    data = response.json()
    assert data["error"]["code"] == "rate_limited"
    assert data["error"]["message"] == "Try again later"
    assert response.headers.get("Retry-After") == "45"
    assert response.headers.get("Cache-Control") == "no-store"


def test_simplify_malformed_provider_output_yields_503(auth_client: TestClient) -> None:
    """When provider returns malformed output (ProviderResponseError), return 503."""
    from app.modules.simplification.provider.base import ProviderResponseError

    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    with patch(
        "app.modules.simplification.service.simplify_text",
        side_effect=ProviderResponseError("Malformed output"),
    ):
        response = auth_client.post(url, json={"source_text": "Some text."})
    assert response.status_code == 503
    data = response.json()
    assert data["error"]["code"] == "service_unavailable"
    assert data["error"]["message"] == "Service unavailable"


def test_explain_word_rate_limited_yields_429(auth_client: TestClient) -> None:
    """When explain_word provider is rate limited, return 429 with Retry-After."""
    from app.modules.simplification.provider.base import ProviderRateLimitError

    url = f"/api/v1/simplification/{LEARNER_ID}/vocabulary/explain"
    with patch(
        "app.modules.simplification.service.explain_word",
        side_effect=ProviderRateLimitError("Rate limit exceeded", retry_after=15),
    ):
        response = auth_client.post(url, json={"term": "chloroplast"})
    assert response.status_code == 429
    data = response.json()
    assert data["error"]["code"] == "rate_limited"
    assert response.headers.get("Retry-After") == "15"


def test_simplify_with_mock_provider_via_dependency_injection(
    application: FastAPI, auth_client: TestClient
) -> None:
    """Verify provider dependency override works through the router end-to-end."""
    from app.modules.simplification.provider.base import SimplificationAIResult
    from app.modules.simplification.router import get_simplification_provider_dep

    mock_provider = MagicMock()
    mock_provider.simplify.return_value = SimplificationAIResult(
        simplified_text="Adapted simple passage.",
        strategy_applied=SimplificationStrategy.FULL_REWRITE,
        target_reading_level=ReadingLevel.BEGINNER,
        adaptation_attempt=1,
        output_length=23,
        ai_provider="gemini-1.5-flash",
        ai_latency_ms=90,
    )

    application.dependency_overrides[get_simplification_provider_dep] = lambda: mock_provider
    try:
        url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
        with patch("app.modules.simplification.service.authorize_learner_action"):
            with patch("app.modules.simplification.service.repo.create_session") as mock_sess:
                mock_row = MagicMock(spec=SimplificationResponse)
                mock_row.id = SESSION_ID
                mock_row.simplified_text = "Adapted simple passage."
                mock_row.strategy_applied = SimplificationStrategy.FULL_REWRITE
                mock_row.target_reading_level = ReadingLevel.BEGINNER
                mock_row.output_difficulty = None
                mock_row.adaptation_attempt = 1
                mock_row.validation_warnings = []
                mock_row.created_at = NOW
                mock_sess.return_value = mock_row

                response = auth_client.post(url, json={"source_text": "Complicated text."})
        assert response.status_code == 200
        data = response.json()
        assert data["simplified_text"] == "Adapted simple passage."
        assert data["strategy_applied"] == "full_rewrite"
    finally:
        application.dependency_overrides.pop(get_simplification_provider_dep, None)


def test_get_simplification_provider_dep_lifecycle_and_cleanup() -> None:
    """Dependency yields configured provider and executes close() on exit, even on exception."""
    from pydantic import SecretStr

    from app.core.config import Settings
    from app.modules.simplification.router import get_simplification_provider_dep

    settings = Settings(
        _env_file=None,
        database_url=SecretStr("postgresql+psycopg://user:pass@localhost:5432/db"),
        jwt_signing_key=SecretStr("secret-key-for-test-lifecycle-cleanup"),
        app_env="test",
        simplification_ai_provider="disabled",
    )

    dep_gen = get_simplification_provider_dep(settings)
    provider = next(dep_gen)
    assert hasattr(provider, "close")

    with patch.object(provider, "close") as mock_close:
        try:
            dep_gen.throw(RuntimeError("Request error inside endpoint"))
        except RuntimeError:
            pass
        mock_close.assert_called_once()


def test_get_simplification_provider_dep_invalid_configuration_yields_503() -> None:
    """When provider instantiation fails in the dependency, SecurityError(503) is raised."""
    from app.core.config import Settings
    from app.modules.simplification.router import get_simplification_provider_dep

    settings = Settings.model_construct(
        simplification_ai_provider="unsupported_provider_xyz",
    )

    dep_gen = get_simplification_provider_dep(settings)
    with pytest.raises(SecurityError) as exc_info:
        next(dep_gen)
    assert exc_info.value.status == 503
    assert exc_info.value.code == "service_unavailable"


def test_simplify_unhandled_programming_error_does_not_mask_as_503(
    auth_client: TestClient,
) -> None:
    """Unexpected programming errors must NOT be masked as 503 service_unavailable."""
    url = f"/api/v1/simplification/{LEARNER_ID}/simplify"
    with patch(
        "app.modules.simplification.service.simplify_text",
        side_effect=TypeError("Unexpected code failure"),
    ):
        with pytest.raises(TypeError, match="Unexpected code failure"):
            auth_client.post(url, json={"source_text": "Any text."})


def test_reading_feedback_regression(auth_client: TestClient) -> None:
    """POST reading feedback returns 200 with correct fields and no-store header."""
    from app.modules.simplification.schemas import ReadingFeedbackResponse

    url = f"/api/v1/simplification/{LEARNER_ID}/sessions/{SESSION_ID}/feedback"
    mock_feedback = ReadingFeedbackResponse(
        feedback_id=FEEDBACK_ID,
        session_id=SESSION_ID,
        feedback_recorded=True,
        created_at=NOW,
    )
    with patch(
        "app.modules.simplification.service.record_reading_feedback",
        return_value=mock_feedback,
    ):
        response = auth_client.post(
            url,
            json={
                "feedback_signal": "just_right",
                "time_spent_seconds": 120,
                "vocabulary_lookups_count": 2,
                "completed_reading": True,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["feedback_id"] == str(FEEDBACK_ID)
    assert data["session_id"] == str(SESSION_ID)
    assert data["feedback_recorded"] is True
    assert response.headers.get("Cache-Control") == "no-store"
