from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from app.core.exceptions import SecurityError
from app.modules.assessments.schemas import AssessmentCompletionRequest
from app.modules.assessments.scoring import calculate_metrics
from app.modules.assessments.service import decode_cursor


def calculate(**overrides):
    values = dict(
        reading_duration_ms=30000,
        attempted_word_count=8,
        correct_word_count=6,
        comprehension_correct=2,
        comprehension_total=3,
    )
    values.update(overrides)
    return calculate_metrics(**values)


def test_formulas_and_independent_decimal_context():
    with localcontext() as context:
        context.prec = 3
        result = calculate()
    assert result.reading_duration_seconds == Decimal("30.00")
    assert result.reading_time_minutes == Decimal("0.50")
    assert result.attempted_words_per_minute == Decimal("16.00")
    assert result.words_correct_per_minute == Decimal("12.00")
    assert result.attempted_word_accuracy_percentage == Decimal("75.00")
    assert result.incorrect_attempt_percentage == Decimal("25.00")
    assert result.comprehension_percentage == Decimal("66.67")


def test_zero_denominators_and_unknown_comprehension():
    result = calculate(
        attempted_word_count=0,
        correct_word_count=0,
        comprehension_correct=None,
        comprehension_total=None,
    )
    assert result.attempted_words_per_minute == 0
    assert result.words_correct_per_minute == 0
    assert result.attempted_word_accuracy_percentage is None
    assert result.incorrect_attempt_percentage is None
    assert result.comprehension_percentage is None


@pytest.mark.parametrize("milliseconds, expected", [(1004, "1.00"), (1005, "1.01"), (1015, "1.02")])
def test_half_up_rounding(milliseconds, expected):
    assert calculate(reading_duration_ms=milliseconds).reading_duration_seconds == Decimal(expected)


@pytest.mark.parametrize(
    "values",
    [
        {"scoring_version": "unknown"},
        {"reading_duration_ms": 0},
        {"reading_duration_ms": -1},
        {"attempted_word_count": True},
        {"correct_word_count": 9},
        {"comprehension_total": 0},
        {"comprehension_total": None},
        {"comprehension_correct": None},
        {"comprehension_correct": 4},
    ],
)
def test_scoring_rejects_invalid_inputs_and_unknown_versions(values):
    with pytest.raises(ValueError):
        calculate(**values)


@pytest.mark.parametrize(
    "field",
    [
        "row_version",
        "reading_duration_ms",
        "attempted_word_count",
        "correct_word_count",
        "omission_count",
        "substitution_count",
        "insertion_count",
        "repetition_count",
        "self_correction_count",
        "unfamiliar_word_count",
        "comprehension_correct",
        "comprehension_total",
    ],
)
@pytest.mark.parametrize("value", [True, "1", 1.5, -1])
def test_strict_integer_validation(observations, field, value):
    with pytest.raises(ValidationError):
        AssessmentCompletionRequest(**(observations | {field: value}))


@pytest.mark.parametrize(
    "field",
    [
        "reading_duration_ms",
        "attempted_word_count",
        "correct_word_count",
        "omission_count",
        "substitution_count",
        "insertion_count",
        "repetition_count",
        "self_correction_count",
    ],
)
def test_core_observations_required(observations, field):
    del observations[field]
    with pytest.raises(ValidationError):
        AssessmentCompletionRequest(**observations)


@pytest.mark.parametrize(
    "field",
    [
        "actor_id",
        "learner_id",
        "material_id",
        "collection_mode",
        "protocol_version",
        "scoring_version",
    ],
)
def test_provenance_is_not_client_writable(observations, field):
    with pytest.raises(ValidationError):
        AssessmentCompletionRequest(**(observations | {field: "untrusted"}))


def test_event_counts_do_not_need_to_reconcile(observations):
    assert AssessmentCompletionRequest(**observations).substitution_count == 3


@pytest.mark.parametrize(
    "cursor", ["bad", "2020-01-01|bad", "2020-01-01|00000000-0000-0000-0000-000000000001"]
)
def test_invalid_cursor_sanitized(cursor):
    with pytest.raises(SecurityError) as exc:
        decode_cursor(cursor)
    assert exc.value.code == "validation_error"
