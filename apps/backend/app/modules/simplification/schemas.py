"""Request and response schemas for adaptive text simplification and vocabulary support.

All schemas inherit from app.core.schemas.Schema, enforcing strict attribute validation
and forbidding unexpected fields (extra="forbid").
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AliasChoices,
    AwareDatetime,
    Field,
    StringConstraints,
    field_validator,
)

from app.core.schemas import Schema
from app.modules.learners.schemas import LanguageTag

# ── Field bounds & constrained types ──────────────────────────────────────────

# Bounded input text: min 1 character, max 50,000 characters (~25 printed pages)
SourceText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000),
]

# Vocabulary word or term: max 200 characters
VocabularyTerm = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]

# Vocabulary synonym: max 100 characters
SynonymTerm = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]

# Optional context sentence: max 500 characters
ContextSentence = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]

# Key concept label from Component 1: max 120 characters
ConceptLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]

# Difficulty score: normalized between 0.00 (easiest) and 1.00 (hardest)
DifficultyScore = Annotated[
    Decimal,
    Field(ge=Decimal("0.00"), le=Decimal("1.00"), decimal_places=2),
]


# ── Enumerations ──────────────────────────────────────────────────────────────


class ReadingLevel(StrEnum):
    """Target and advisory reading levels proposed for Component 2.

    Note: This is a proposed qualitative classification. The authoritative learner
    foundation uses numeric GradeLevel (3-8) and AgeBand (9-12). The mapping between
    this qualitative taxonomy and the learner's numeric level must be agreed upon
    with Component 4 (Learner Analytics) before production integration.
    """

    BEGINNER = "beginner"
    ELEMENTARY = "elementary"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class SimplificationStrategy(StrEnum):
    """Adaptation strategy applied or requested for text simplification."""

    VOCABULARY_SWAP = "vocabulary_swap"
    SENTENCE_SPLIT = "sentence_split"
    CONCEPT_REDUCTION = "concept_reduction"
    FULL_REWRITE = "full_rewrite"
    COMBINED = "combined"


class VocabularySource(StrEnum):
    """Origin of the vocabulary item."""

    AUTOMATIC = "automatic"
    USER = "user"


class FeedbackSignal(StrEnum):
    """Coarse learner feedback signal on reading difficulty."""

    TOO_HARD = "too_hard"
    TOO_EASY = "too_easy"
    JUST_RIGHT = "just_right"
    SKIPPED = "skipped"


# ── Shared Vocabulary Schemas ─────────────────────────────────────────────────


class VocabularyItemResponse(Schema):
    """A single vocabulary term and plain-language explanation."""

    term: VocabularyTerm
    simplified_definition: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ]
    example_sentence: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
        ]
        | None
    ) = None
    synonyms: list[SynonymTerm] = Field(default_factory=list, max_length=5)
    source: VocabularySource = VocabularySource.AUTOMATIC


# ── API 1: Text Simplification ────────────────────────────────────────────────


class SimplificationRequest(Schema):
    """Request payload for text simplification.

    Learner identity is resolved from the URL path and JWT authentication.
    Client-supplied reading levels and strategies are advisory hints only.
    """

    source_text: SourceText
    source_difficulty: DifficultyScore | None = Field(
        default=None,
        validation_alias=AliasChoices("source_difficulty", "document_difficulty"),
    )
    document_id: UUID | None = None
    key_concepts: list[ConceptLabel] = Field(default_factory=list, max_length=20)
    current_reading_level: ReadingLevel | None = None
    target_reading_level: ReadingLevel | None = None
    preferred_strategy: SimplificationStrategy | None = None

    @field_validator("key_concepts", mode="before")
    @classmethod
    def filter_empty_concepts(cls, value: object) -> object:
        if isinstance(value, list):
            return [c for c in value if isinstance(c, str) and c.strip()]
        return value


class SimplificationResponse(Schema):
    """Response containing simplified text, extracted vocabulary, and validation warnings."""

    session_id: UUID
    learner_id: UUID
    simplified_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=60_000),
    ]
    strategy_applied: SimplificationStrategy
    target_reading_level: ReadingLevel
    estimated_output_difficulty: DifficultyScore | None = None
    adaptation_attempt: int = Field(ge=1, le=10)
    vocabulary_items: list[VocabularyItemResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: AwareDatetime


# ── API 2: On-Demand Word Explanation ─────────────────────────────────────────


class WordExplanationRequest(Schema):
    """Request payload for on-demand explanation of a selected word."""

    term: VocabularyTerm
    context_sentence: ContextSentence | None = None
    session_id: UUID | None = None

    @field_validator("context_sentence", mode="before")
    @classmethod
    def normalize_context_sentence(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class WordExplanationResponse(Schema):
    """Response containing plain-language explanation for a selected word."""

    learner_id: UUID
    item: VocabularyItemResponse
    language_tag: LanguageTag
    session_id: UUID | None = None
    created_at: AwareDatetime


# ── API 3: Post-Reading Feedback ──────────────────────────────────────────────


class ReadingFeedbackRequest(Schema):
    """Post-reading feedback signal from the learner or educator."""

    feedback_signal: FeedbackSignal
    time_spent_seconds: Annotated[int, Field(ge=0, le=7200)] | None = None
    vocabulary_lookups_count: Annotated[int, Field(ge=0, le=100)] | None = None
    completed_reading: bool | None = None
    occurred_at: AwareDatetime | None = None


class ReadingFeedbackResponse(Schema):
    """Receipt acknowledging recorded feedback."""

    feedback_id: UUID
    session_id: UUID
    feedback_recorded: Literal[True] = True
    created_at: AwareDatetime
