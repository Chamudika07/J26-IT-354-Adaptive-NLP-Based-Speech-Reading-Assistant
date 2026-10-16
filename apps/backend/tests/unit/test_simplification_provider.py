"""Unit tests for the Component 2 simplification AI provider foundation."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.modules.simplification.provider import (
    DisabledSimplificationProvider,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
    SimplificationAIResult,
    VocabularyExplanationAIResult,
    get_simplification_provider,
)
from app.modules.simplification.schemas import (
    ReadingLevel,
    SimplificationRequest,
    SimplificationStrategy,
    WordExplanationRequest,
)

DATABASE_URL = "postgresql+psycopg://synthetic:secret@localhost:5432/config_test"
JWT_SECRET = "synthetic-test-signing-key-never-use-in-production"


def _make_settings(**overrides: object) -> Settings:
    defaults = {
        "_env_file": None,
        "database_url": SecretStr(DATABASE_URL),
        "jwt_signing_key": SecretStr(JWT_SECRET),
        "app_env": "test",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


# ── Disabled Provider Tests ───────────────────────────────────────────────────


def test_disabled_provider_properties():
    provider = DisabledSimplificationProvider()
    assert provider.provider_name == "disabled"


def test_disabled_provider_simplify_raises():
    provider = DisabledSimplificationProvider()
    request = SimplificationRequest(source_text="Test source text.")
    with pytest.raises(ProviderUnavailableError) as exc_info:
        provider.simplify(request)
    assert "disabled or not configured" in str(exc_info.value)


def test_disabled_provider_explain_word_raises():
    provider = DisabledSimplificationProvider()
    request = WordExplanationRequest(term="photosynthesis")
    with pytest.raises(ProviderUnavailableError) as exc_info:
        provider.explain_word(request)
    assert "disabled or not configured" in str(exc_info.value)


# ── Provider Factory Tests ────────────────────────────────────────────────────


def test_factory_returns_disabled_provider_by_default():
    settings = _make_settings()
    assert settings.simplification_ai_provider == "disabled"
    provider = get_simplification_provider(settings)
    assert isinstance(provider, DisabledSimplificationProvider)
    assert provider.provider_name == "disabled"


def test_factory_configured_external_provider_reports_not_implemented():
    settings = _make_settings(
        simplification_ai_provider="gemini",
        simplification_ai_api_key=SecretStr("valid-secret-key-for-test-purposes"),
    )
    with pytest.raises(ProviderUnavailableError) as exc_info:
        get_simplification_provider(settings)
    assert "network execution is not yet implemented" in str(exc_info.value)


def test_factory_configured_openai_reports_not_implemented():
    settings = _make_settings(
        simplification_ai_provider="openai",
        simplification_ai_api_key=SecretStr("valid-secret-key-for-test-purposes"),
    )
    with pytest.raises(ProviderUnavailableError) as exc_info:
        get_simplification_provider(settings)
    assert "Provider 'openai' is configured but network execution is not yet implemented" in str(
        exc_info.value
    )


def test_factory_rejects_unsupported_provider():
    mock_settings = MagicMock(spec=Settings)
    mock_settings.simplification_ai_provider = "unsupported_llm"
    with pytest.raises(ValueError, match="Unsupported simplification AI provider"):
        get_simplification_provider(mock_settings)


# ── Configuration Validation Tests ────────────────────────────────────────────


def test_ai_model_resolution():
    # Disabled provider has None model
    settings_disabled = _make_settings(simplification_ai_provider="disabled")
    assert settings_disabled.simplification_ai_model is None

    # Gemini default model
    settings_gemini = _make_settings(
        simplification_ai_provider="gemini",
        simplification_ai_api_key=SecretStr("valid-key-for-testing"),
    )
    assert settings_gemini.simplification_ai_model == "gemini-1.5-flash"

    # OpenAI default model
    settings_openai = _make_settings(
        simplification_ai_provider="openai",
        simplification_ai_api_key=SecretStr("valid-key-for-testing"),
    )
    assert settings_openai.simplification_ai_model == "gpt-4o-mini"

    # Explicit custom model preserved
    settings_custom = _make_settings(
        simplification_ai_provider="gemini",
        simplification_ai_api_key=SecretStr("valid-key-for-testing"),
        simplification_ai_model="gemini-2.0-flash-exp",
    )
    assert settings_custom.simplification_ai_model == "gemini-2.0-flash-exp"


def test_ai_provider_missing_key_rejected():
    with pytest.raises(ValidationError, match="A valid API key is required"):
        _make_settings(
            simplification_ai_provider="gemini",
            simplification_ai_api_key=None,
        )


def test_ai_provider_placeholder_key_rejected():
    with pytest.raises(ValidationError, match="A valid API key is required"):
        _make_settings(
            simplification_ai_provider="gemini",
            simplification_ai_api_key=SecretStr("replace_with_your_actual_key"),
        )


def test_ai_timeout_validation():
    # Below minimum (5s)
    with pytest.raises(ValidationError, match="simplification_ai_timeout_seconds"):
        _make_settings(simplification_ai_timeout_seconds=4)

    # Above maximum (120s)
    with pytest.raises(ValidationError, match="simplification_ai_timeout_seconds"):
        _make_settings(simplification_ai_timeout_seconds=121)

    # Valid bounds
    settings = _make_settings(simplification_ai_timeout_seconds=60)
    assert settings.simplification_ai_timeout_seconds == 60


def test_ai_max_retries_validation():
    # Below minimum (0)
    with pytest.raises(ValidationError, match="simplification_ai_max_retries"):
        _make_settings(simplification_ai_max_retries=-1)

    # Above maximum (2)
    with pytest.raises(ValidationError, match="simplification_ai_max_retries"):
        _make_settings(simplification_ai_max_retries=3)

    # Valid
    settings = _make_settings(simplification_ai_max_retries=2)
    assert settings.simplification_ai_max_retries == 2


def test_ai_base_url_validation():
    # Valid https (trailing slash stripped)
    settings = _make_settings(simplification_ai_base_url="https://api.example.com/v1/")
    assert settings.simplification_ai_base_url == "https://api.example.com/v1"

    # Valid local http
    settings_local = _make_settings(simplification_ai_base_url="http://127.0.0.1:8000/v1")
    assert settings_local.simplification_ai_base_url == "http://127.0.0.1:8000/v1"

    # Insecure external http rejected
    with pytest.raises(ValidationError, match="simplification_ai_base_url must use https"):
        _make_settings(simplification_ai_base_url="http://insecure-external-api.com/v1")

    # Malformed URL without scheme or host rejected
    with pytest.raises(ValidationError, match="simplification_ai_base_url must be a valid URL"):
        _make_settings(simplification_ai_base_url="not-a-valid-url")
    with pytest.raises(ValidationError, match="simplification_ai_base_url must be a valid URL"):
        _make_settings(simplification_ai_base_url="https://")
    with pytest.raises(ValidationError, match="simplification_ai_base_url must use https"):
        _make_settings(simplification_ai_base_url="http://insecure-external-api.com/v1")


# ── Secret Safety Tests ───────────────────────────────────────────────────────


def test_ai_api_key_hidden_in_repr_and_str():
    secret_marker = "super-secret-marker-ai-key-998877"
    settings = _make_settings(
        simplification_ai_provider="gemini",
        simplification_ai_api_key=SecretStr(secret_marker),
    )
    assert secret_marker not in repr(settings)
    assert secret_marker not in str(settings)
    assert settings.simplification_ai_api_key is not None
    assert settings.simplification_ai_api_key.get_secret_value() == secret_marker


# ── Sanitized Provider Exceptions Tests ───────────────────────────────────────


def test_sanitized_exceptions_properties():
    base_err = ProviderError("Safe error message")
    assert str(base_err) == "Safe error message"

    unavail_err = ProviderUnavailableError("Provider offline")
    assert str(unavail_err) == "Provider offline"

    rate_err = ProviderRateLimitError("Quota exceeded", retry_after=45)
    assert str(rate_err) == "Quota exceeded"
    assert rate_err.retry_after == 45

    resp_err = ProviderResponseError("Invalid JSON structure")
    assert str(resp_err) == "Invalid JSON structure"


# ── Result Contracts Serialization Tests ──────────────────────────────────────


def test_simplification_result_to_dict():
    result = SimplificationAIResult(
        simplified_text="Simplified text here.",
        strategy_applied=SimplificationStrategy.VOCABULARY_SWAP,
        target_reading_level=ReadingLevel.BEGINNER,
        adaptation_attempt=1,
        output_length=21,
        ai_provider="mock_provider",
        ai_latency_ms=120,
        output_difficulty=Decimal("0.25"),
        concepts_preserved=["photosynthesis"],
        validation_warnings=["reading_level_derived_from_age_band"],
        vocabulary_items=[{"term": "test", "simplified_definition": "a test term"}],
    )
    d = result.to_dict()
    assert d["simplified_text"] == "Simplified text here."
    assert d["strategy_applied"] == SimplificationStrategy.VOCABULARY_SWAP
    assert d["ai_latency_ms"] == 120
    assert d["concepts_preserved"] == ["photosynthesis"]
    assert len(d["vocabulary_items"]) == 1


def test_vocabulary_result_to_dict():
    result = VocabularyExplanationAIResult(
        term="chlorophyll",
        simplified_definition="Green substance in plants.",
        ai_provider="mock_provider",
        ai_latency_ms=90,
        language_tag="en",
        example_sentence="Leaves have chlorophyll.",
        synonyms=["plant pigment"],
    )
    d = result.to_dict()
    assert d["term"] == "chlorophyll"
    assert d["simplified_definition"] == "Green substance in plants."
    assert d["ai_provider"] == "mock_provider"
    assert d["synonyms"] == ["plant pigment"]
