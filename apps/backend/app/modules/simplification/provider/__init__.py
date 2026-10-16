"""AI provider integration foundation for text simplification and vocabulary support."""

from app.modules.simplification.provider.base import (
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
    SimplificationAIResult,
    SimplificationProvider,
    VocabularyExplanationAIResult,
)
from app.modules.simplification.provider.disabled import DisabledSimplificationProvider
from app.modules.simplification.provider.factory import get_simplification_provider

__all__ = [
    "DisabledSimplificationProvider",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderUnavailableError",
    "SimplificationAIResult",
    "SimplificationProvider",
    "VocabularyExplanationAIResult",
    "get_simplification_provider",
]
