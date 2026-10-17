"""Disabled simplification provider implementation."""

from app.modules.simplification.provider.base import (
    ProviderUnavailableError,
    SimplificationAIResult,
    VocabularyExplanationAIResult,
)
from app.modules.simplification.schemas import (
    SimplificationRequest,
    WordExplanationRequest,
)


class DisabledSimplificationProvider:
    """Safe placeholder provider when simplification AI is disabled or unconfigured."""

    @property
    def provider_name(self) -> str:
        return "disabled"

    def simplify(
        self,
        request: SimplificationRequest,
    ) -> SimplificationAIResult:
        """Always raises ProviderUnavailableError."""
        raise ProviderUnavailableError("Simplification AI provider is disabled or not configured.")

    def explain_word(
        self,
        request: WordExplanationRequest,
    ) -> VocabularyExplanationAIResult:
        """Always raises ProviderUnavailableError."""
        raise ProviderUnavailableError("Simplification AI provider is disabled or not configured.")

    def close(self) -> None:
        """No-op for disabled provider."""
        return None
