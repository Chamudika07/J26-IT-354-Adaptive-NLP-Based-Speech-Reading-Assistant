"""Frozen factual formulas. Never infer clinical status or educational thresholds."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

SCORING_VERSION = "reading-scoring-v1"
PROTOCOL_VERSION = "reading-observation-v1"


@dataclass(frozen=True)
class ReadingMetrics:
    reading_duration_seconds: Decimal
    reading_time_minutes: Decimal
    attempted_words_per_minute: Decimal
    words_correct_per_minute: Decimal
    attempted_word_accuracy_percentage: Decimal | None
    incorrect_attempt_percentage: Decimal | None
    comprehension_percentage: Decimal | None


def calculate_metrics(
    *,
    reading_duration_ms: int,
    attempted_word_count: int,
    correct_word_count: int,
    comprehension_correct: int | None,
    comprehension_total: int | None,
    scoring_version: str = SCORING_VERSION,
) -> ReadingMetrics:
    """Dispatch explicitly; retain v1 unchanged when adding later formula versions."""
    if scoring_version != SCORING_VERSION:
        raise ValueError("Unsupported scoring version")
    values = [reading_duration_ms, attempted_word_count, correct_word_count]
    values += [v for v in (comprehension_correct, comprehension_total) if v is not None]
    if any(type(v) is not int or not 0 <= v <= 2147483647 for v in values):
        raise ValueError("Invalid measurements")
    if reading_duration_ms == 0 or correct_word_count > attempted_word_count:
        raise ValueError("Invalid measurements")
    if (comprehension_correct is None) != (comprehension_total is None):
        raise ValueError("Invalid comprehension")
    if comprehension_total is not None and (
        comprehension_total <= 0
        or comprehension_correct is None
        or comprehension_correct > comprehension_total
    ):
        raise ValueError("Invalid comprehension")
    with localcontext() as context:
        context.prec = 40

        def rounded(numerator: int, denominator: int) -> Decimal:
            return (Decimal(numerator) / Decimal(denominator)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        return ReadingMetrics(
            rounded(reading_duration_ms, 1000),
            rounded(reading_duration_ms, 60000),
            rounded(attempted_word_count * 60000, reading_duration_ms),
            rounded(correct_word_count * 60000, reading_duration_ms),
            rounded(correct_word_count * 100, attempted_word_count)
            if attempted_word_count
            else None,
            rounded((attempted_word_count - correct_word_count) * 100, attempted_word_count)
            if attempted_word_count
            else None,
            rounded(comprehension_correct * 100, comprehension_total)
            if comprehension_correct is not None and comprehension_total is not None
            else None,
        )
