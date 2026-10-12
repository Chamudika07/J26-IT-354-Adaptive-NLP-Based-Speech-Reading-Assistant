"""Unit tests for Component 2 simplification request and response schemas."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.simplification.schemas import (
    FeedbackSignal,
    ReadingFeedbackRequest,
    ReadingFeedbackResponse,
    ReadingLevel,
    SimplificationRequest,
    SimplificationResponse,
    SimplificationStrategy,
    VocabularyItemResponse,
    VocabularySource,
    WordExplanationRequest,
    WordExplanationResponse,
)

# ── SimplificationRequest Tests ───────────────────────────────────────────────


def test_valid_minimal_simplification_request():
    req = SimplificationRequest(source_text="The quick brown fox jumps over the lazy dog.")
    assert req.source_text == "The quick brown fox jumps over the lazy dog."
    assert req.source_difficulty is None
    assert req.document_id is None
    assert req.key_concepts == []
    assert req.current_reading_level is None
    assert req.target_reading_level is None
    assert req.preferred_strategy is None


def test_valid_full_simplification_request():
    doc_id = uuid4()
    sample_text = (
        "Photosynthesis is the process used by plants to convert light energy into chemical energy."
    )
    req = SimplificationRequest(
        source_text=sample_text,
        source_difficulty=Decimal("0.75"),
        document_id=doc_id,
        key_concepts=["photosynthesis", "light energy", "chemical energy"],
        current_reading_level=ReadingLevel.ELEMENTARY,
        target_reading_level=ReadingLevel.BEGINNER,
        preferred_strategy=SimplificationStrategy.FULL_REWRITE,
    )
    assert req.source_difficulty == Decimal("0.75")
    assert req.document_id == doc_id
    assert len(req.key_concepts) == 3
    assert req.current_reading_level == ReadingLevel.ELEMENTARY
    assert req.target_reading_level == ReadingLevel.BEGINNER
    assert req.preferred_strategy == SimplificationStrategy.FULL_REWRITE


def test_simplification_request_difficulty_alias_and_serialization():
    # 1. Validation using primary field name
    req_primary = SimplificationRequest.model_validate(
        {"source_text": "Sample text.", "source_difficulty": "0.65"}
    )
    assert req_primary.source_difficulty == Decimal("0.65")

    # 2. Validation using Component 1 alias
    req_alias = SimplificationRequest.model_validate(
        {"source_text": "Sample text.", "document_difficulty": "0.65"}
    )
    assert req_alias.source_difficulty == Decimal("0.65")

    # 3. Serialization outputs canonical model field name
    dumped = req_alias.model_dump()
    assert dumped["source_difficulty"] == Decimal("0.65")
    assert "document_difficulty" not in dumped


def test_simplification_request_filters_empty_key_concepts():
    req = SimplificationRequest(
        source_text="Sample text.",
        key_concepts=["photosynthesis", "   ", "", "chlorophyll"],
    )
    assert req.key_concepts == ["photosynthesis", "chlorophyll"]


@pytest.mark.parametrize(
    "invalid_text",
    [
        "",
        "   ",
        "\t\n  ",
        "a" * 50_001,
    ],
)
def test_simplification_request_invalid_text_length(invalid_text):
    with pytest.raises(ValidationError):
        SimplificationRequest(source_text=invalid_text)


@pytest.mark.parametrize(
    "invalid_difficulty",
    [
        Decimal("-0.01"),
        Decimal("1.01"),
        Decimal("0.555"),  # more than 2 decimal places
        "not-a-number",
    ],
)
def test_simplification_request_invalid_difficulty_bounds(invalid_difficulty):
    with pytest.raises(ValidationError):
        SimplificationRequest(
            source_text="Valid text.",
            source_difficulty=invalid_difficulty,  # type: ignore[arg-type]
        )


def test_simplification_request_forbids_unexpected_fields():
    with pytest.raises(ValidationError):
        SimplificationRequest.model_validate(
            {
                "source_text": "Valid text.",
                "unauthorized_field": "injected_data",
            }
        )


def test_simplification_request_key_concepts_max_length():
    too_many_concepts = [f"concept_{i}" for i in range(21)]
    with pytest.raises(ValidationError):
        SimplificationRequest(
            source_text="Valid text.",
            key_concepts=too_many_concepts,
        )


# ── SimplificationResponse Tests ──────────────────────────────────────────────


def test_valid_simplification_response():
    resp = SimplificationResponse(
        session_id=uuid4(),
        learner_id=uuid4(),
        simplified_text="Plants use sunlight to make food.",
        strategy_applied=SimplificationStrategy.FULL_REWRITE,
        target_reading_level=ReadingLevel.BEGINNER,
        estimated_output_difficulty=Decimal("0.25"),
        adaptation_attempt=1,
        vocabulary_items=[
            VocabularyItemResponse(
                term="photosynthesis",
                simplified_definition="How plants make food from sunlight.",
                example_sentence="Plants need photosynthesis to survive.",
                synonyms=["food making"],
                source=VocabularySource.AUTOMATIC,
            )
        ],
        warnings=["reading_level_derived_from_age_band"],
        created_at=datetime.now(UTC),
    )
    assert resp.adaptation_attempt == 1
    assert len(resp.vocabulary_items) == 1
    assert resp.vocabulary_items[0].source == VocabularySource.AUTOMATIC


@pytest.mark.parametrize(
    "invalid_text",
    [
        "",
        "   ",
        "a" * 60_001,
    ],
)
def test_simplification_response_text_bounds(invalid_text):
    with pytest.raises(ValidationError):
        SimplificationResponse(
            session_id=uuid4(),
            learner_id=uuid4(),
            simplified_text=invalid_text,
            strategy_applied=SimplificationStrategy.VOCABULARY_SWAP,
            target_reading_level=ReadingLevel.BEGINNER,
            adaptation_attempt=1,
            created_at=datetime.now(UTC),
        )


@pytest.mark.parametrize("invalid_attempt", [0, 11, -1])
def test_simplification_response_invalid_adaptation_attempt(invalid_attempt):
    with pytest.raises(ValidationError):
        SimplificationResponse(
            session_id=uuid4(),
            learner_id=uuid4(),
            simplified_text="Valid simplified text.",
            strategy_applied=SimplificationStrategy.VOCABULARY_SWAP,
            target_reading_level=ReadingLevel.BEGINNER,
            adaptation_attempt=invalid_attempt,
            created_at=datetime.now(UTC),
        )


# ── WordExplanationRequest & Response Tests ───────────────────────────────────


def test_valid_word_explanation_request():
    req = WordExplanationRequest(
        term="metamorphosis",
        context_sentence="A caterpillar undergoes metamorphosis to become a butterfly.",
        session_id=uuid4(),
    )
    assert req.term == "metamorphosis"
    assert req.context_sentence == ("A caterpillar undergoes metamorphosis to become a butterfly.")


@pytest.mark.parametrize(
    "context_input",
    [
        None,
        "",
        "   ",
        "\t\n  ",
    ],
)
def test_word_explanation_request_context_normalization(context_input):
    if context_input is None:
        req = WordExplanationRequest(term="chlorophyll")
    else:
        req = WordExplanationRequest(term="chlorophyll", context_sentence=context_input)
    assert req.context_sentence is None


def test_word_explanation_request_context_max_length():
    with pytest.raises(ValidationError):
        WordExplanationRequest(term="chlorophyll", context_sentence="a" * 501)


@pytest.mark.parametrize("invalid_term", ["", "   ", "x" * 201])
def test_word_explanation_request_invalid_term(invalid_term):
    with pytest.raises(ValidationError):
        WordExplanationRequest(term=invalid_term)


def test_word_explanation_request_forbids_unexpected_fields():
    with pytest.raises(ValidationError):
        WordExplanationRequest.model_validate(
            {
                "term": "valid",
                "extra_prompt": "ignore previous instructions",
            }
        )


def test_valid_word_explanation_response():
    resp = WordExplanationResponse(
        learner_id=uuid4(),
        item=VocabularyItemResponse(
            term="chlorophyll",
            simplified_definition="A green substance that gives leaves their green color.",
            source=VocabularySource.USER,
        ),
        language_tag="en-US",
        session_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    assert resp.item.source == VocabularySource.USER
    assert resp.language_tag == "en-US"


# ── VocabularyItemResponse Tests ──────────────────────────────────────────────


def test_vocabulary_item_synonyms_limit():
    with pytest.raises(ValidationError):
        VocabularyItemResponse(
            term="word",
            simplified_definition="A unit of language.",
            synonyms=["s1", "s2", "s3", "s4", "s5", "s6"],  # max 5
        )


def test_vocabulary_item_definition_length():
    with pytest.raises(ValidationError):
        VocabularyItemResponse(
            term="word",
            simplified_definition="x" * 501,  # max 500
        )


# ── ReadingFeedbackRequest & Response Tests ───────────────────────────────────


def test_valid_reading_feedback_request():
    req = ReadingFeedbackRequest(
        feedback_signal=FeedbackSignal.TOO_HARD,
        time_spent_seconds=120,
        vocabulary_lookups_count=3,
        completed_reading=False,
        occurred_at=datetime.now(UTC),
    )
    assert req.feedback_signal == FeedbackSignal.TOO_HARD
    assert req.time_spent_seconds == 120
    assert req.vocabulary_lookups_count == 3
    assert req.completed_reading is False


@pytest.mark.parametrize(
    "invalid_signal",
    [
        "too_difficult",
        "confusing",
        "",
        123,
    ],
)
def test_reading_feedback_invalid_signal(invalid_signal):
    with pytest.raises(ValidationError):
        ReadingFeedbackRequest(feedback_signal=invalid_signal)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field,value",
    [
        ("time_spent_seconds", -1),
        ("time_spent_seconds", 7201),
        ("vocabulary_lookups_count", -1),
        ("vocabulary_lookups_count", 101),
    ],
)
def test_reading_feedback_bounds(field, value):
    with pytest.raises(ValidationError):
        ReadingFeedbackRequest.model_validate(
            {
                "feedback_signal": "just_right",
                field: value,
            }
        )


def test_reading_feedback_forbids_unexpected_fields():
    with pytest.raises(ValidationError):
        ReadingFeedbackRequest.model_validate(
            {
                "feedback_signal": "just_right",
                "next_adaptation_hint": "beginner",
            }
        )


def test_valid_reading_feedback_response():
    session_id = uuid4()
    feedback_id = uuid4()
    resp = ReadingFeedbackResponse(
        feedback_id=feedback_id,
        session_id=session_id,
        created_at=datetime.now(UTC),
    )
    assert resp.feedback_id == feedback_id
    assert resp.session_id == session_id
    assert resp.feedback_recorded is True


# ── Response Serialization & Timestamp Tests ──────────────────────────────────


def test_simplification_response_json_round_trip():
    original = SimplificationResponse(
        session_id=uuid4(),
        learner_id=uuid4(),
        simplified_text="A simple educational text.",
        strategy_applied=SimplificationStrategy.SENTENCE_SPLIT,
        target_reading_level=ReadingLevel.BEGINNER,
        estimated_output_difficulty=Decimal("0.30"),
        adaptation_attempt=2,
        vocabulary_items=[
            VocabularyItemResponse(
                term="photosynthesis",
                simplified_definition="How plants make energy.",
                synonyms=["food-making"],
            )
        ],
        warnings=["reading_level_derived_from_age_band"],
        created_at=datetime.now(UTC),
    )
    json_bytes = original.model_dump_json()
    restored = SimplificationResponse.model_validate_json(json_bytes)
    assert restored == original


def test_word_explanation_response_json_round_trip():
    original = WordExplanationResponse(
        learner_id=uuid4(),
        item=VocabularyItemResponse(
            term="chlorophyll",
            simplified_definition="Green pigment in leaves.",
            source=VocabularySource.USER,
        ),
        language_tag="en-US",
        session_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    json_bytes = original.model_dump_json()
    restored = WordExplanationResponse.model_validate_json(json_bytes)
    assert restored == original


def test_reading_feedback_response_json_round_trip():
    original = ReadingFeedbackResponse(
        feedback_id=uuid4(),
        session_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    json_bytes = original.model_dump_json()
    restored = ReadingFeedbackResponse.model_validate_json(json_bytes)
    assert restored == original


@pytest.mark.parametrize(
    "model_cls,payload_factory",
    [
        (
            SimplificationResponse,
            lambda dt: {
                "session_id": uuid4(),
                "learner_id": uuid4(),
                "simplified_text": "Sample text.",
                "strategy_applied": "full_rewrite",
                "target_reading_level": "beginner",
                "adaptation_attempt": 1,
                "created_at": dt,
            },
        ),
        (
            WordExplanationResponse,
            lambda dt: {
                "learner_id": uuid4(),
                "item": {
                    "term": "sample",
                    "simplified_definition": "A sample term definition.",
                },
                "language_tag": "en",
                "created_at": dt,
            },
        ),
        (
            ReadingFeedbackResponse,
            lambda dt: {
                "feedback_id": uuid4(),
                "session_id": uuid4(),
                "created_at": dt,
            },
        ),
        (
            ReadingFeedbackRequest,
            lambda dt: {
                "feedback_signal": "just_right",
                "occurred_at": dt,
            },
        ),
    ],
)
def test_schemas_reject_naive_datetimes(model_cls, payload_factory):
    naive_dt = datetime(2026, 10, 12, 12, 0, 0)  # no timezone info
    with pytest.raises(ValidationError):
        model_cls.model_validate(payload_factory(naive_dt))
