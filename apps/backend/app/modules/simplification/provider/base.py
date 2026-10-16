"""Abstract provider contracts and sanitized exceptions for Component 2 AI integration."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from app.modules.simplification.schemas import (
    ReadingLevel,
    SimplificationRequest,
    SimplificationStrategy,
    WordExplanationRequest,
)

# ── Sanitized Provider Exceptions ─────────────────────────────────────────────


class ProviderError(Exception):
    """Base sanitized exception for AI provider operations.

    Subclasses must only contain safe, fixed error messages, never raw prompts,
    untrusted learner inputs, credentials, or upstream error bodies.
    """

    def __init__(self, message: str = "AI provider error") -> None:
        super().__init__(message)
        self.message = message


class ProviderUnavailableError(ProviderError):
    """Raised when the AI provider is disabled, unconfigured, or unreachable."""

    def __init__(self, message: str = "Simplification provider is unavailable") -> None:
        super().__init__(message)


class ProviderRateLimitError(ProviderError):
    """Raised when an upstream AI provider rate limit is encountered."""

    def __init__(
        self,
        message: str = "AI provider rate limit reached",
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ProviderResponseError(ProviderError):
    """Raised when the upstream provider returns an invalid or malformed response."""

    def __init__(self, message: str = "Malformed or invalid AI response") -> None:
        super().__init__(message)


# ── Internal AI Result Contracts ──────────────────────────────────────────────


@dataclass(frozen=True)
class SimplificationAIResult:
    """Internal normalized result returned by a simplification provider."""

    simplified_text: str
    strategy_applied: SimplificationStrategy
    target_reading_level: ReadingLevel
    adaptation_attempt: int
    output_length: int
    ai_provider: str
    ai_latency_ms: int
    output_difficulty: Decimal | None = None
    concepts_preserved: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    vocabulary_items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict matching service and repository creation requirements."""
        return {
            "simplified_text": self.simplified_text,
            "strategy_applied": self.strategy_applied,
            "target_reading_level": self.target_reading_level,
            "adaptation_attempt": self.adaptation_attempt,
            "output_length": self.output_length,
            "ai_provider": self.ai_provider,
            "ai_latency_ms": self.ai_latency_ms,
            "output_difficulty": self.output_difficulty,
            "concepts_preserved": list(self.concepts_preserved),
            "validation_warnings": list(self.validation_warnings),
            "vocabulary_items": list(self.vocabulary_items),
        }


@dataclass(frozen=True)
class VocabularyExplanationAIResult:
    """Internal normalized result for an on-demand vocabulary explanation."""

    term: str
    simplified_definition: str
    ai_provider: str
    ai_latency_ms: int
    language_tag: str = "en"
    example_sentence: str | None = None
    synonyms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict matching vocabulary repository creation requirements."""
        return {
            "term": self.term,
            "simplified_definition": self.simplified_definition,
            "ai_provider": self.ai_provider,
            "ai_latency_ms": self.ai_latency_ms,
            "language_tag": self.language_tag,
            "example_sentence": self.example_sentence,
            "synonyms": list(self.synonyms),
        }


# ── Provider Protocol ─────────────────────────────────────────────────────────


class SimplificationProvider(Protocol):
    """Abstract protocol for text simplification and vocabulary support."""

    @property
    def provider_name(self) -> str:
        """Normalized identifier for the provider (recorded in session audit fields)."""
        ...

    def simplify(
        self,
        request: SimplificationRequest,
    ) -> SimplificationAIResult:
        """Simplify source text and extract key vocabulary.

        Raises:
            ProviderUnavailableError: If provider is disabled or unreachable.
            ProviderRateLimitError: If rate limit is exceeded.
            ProviderResponseError: If response fails schema validation.
        """
        ...

    def explain_word(
        self,
        request: WordExplanationRequest,
    ) -> VocabularyExplanationAIResult:
        """Provide on-demand plain language explanation for a selected term.

        Raises:
            ProviderUnavailableError: If provider is disabled or unreachable.
            ProviderRateLimitError: If rate limit is exceeded.
            ProviderResponseError: If response fails schema validation.
        """
        ...
