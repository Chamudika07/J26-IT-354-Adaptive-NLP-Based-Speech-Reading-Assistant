"""Deterministic educational analytics functions for reading sessions.

These functions implement pure, deterministic mathematical transformations of
reading-session measurements. All indicators are experimental educational heuristics
for software scaffolding; they must NEVER be interpreted or presented as clinical,
psychological, or diagnostic findings.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ENGAGEMENT_FORMULA_VERSION: str = "v0.1-research-heuristic"

CompletionStatus = Literal["completed", "abandoned", "interrupted"]
TaskType = Literal["independent_reading", "assisted_read_aloud", "guided_echo_reading"]
DifficultyTier = Literal["early", "intermediate", "advanced"]
SupportMode = Literal["baseline_fixed", "adaptive", "manual_override"]


@dataclass(frozen=True, slots=True)
class SessionTelemetry:
    """Immutable input measurements captured from a single reading session.

    All counts and durations must be non-negative. Missing measurements must remain
    None and must not be coerced to zero.

    session_start_time must be timezone-aware (rejecting naive datetimes) to guarantee
    deterministic, stable chronological ordering in longitudinal analytics.
    """

    session_start_time: datetime
    words_attempted: int
    words_correct: int
    target_word_count: int
    active_duration_ms: int
    total_duration_ms: int
    hesitation_count: int | None = None
    total_pause_duration_ms: int | None = None
    pause_count: int | None = None
    completion_status: CompletionStatus = "completed"
    session_id: str | None = None
    task_type: str = "independent_reading"
    difficulty_tier: str = "intermediate"
    support_mode: str = "adaptive"

    def __post_init__(self) -> None:
        """Validate relational and boundary invariants on telemetry fields."""
        if (
            self.session_start_time.tzinfo is None
            or self.session_start_time.tzinfo.utcoffset(self.session_start_time) is None
        ):
            raise ValueError(
                "session_start_time must be timezone-aware; naive datetimes are not permitted"
            )
        if self.words_attempted < 0:
            raise ValueError(f"words_attempted cannot be negative, got {self.words_attempted}")
        if self.words_correct < 0:
            raise ValueError(f"words_correct cannot be negative, got {self.words_correct}")
        if self.words_correct > self.words_attempted:
            raise ValueError(
                f"words_correct ({self.words_correct}) cannot exceed "
                f"words_attempted ({self.words_attempted})"
            )
        if self.target_word_count < 0:
            raise ValueError(f"target_word_count cannot be negative, got {self.target_word_count}")
        if self.active_duration_ms < 0:
            raise ValueError(
                f"active_duration_ms cannot be negative, got {self.active_duration_ms}"
            )
        if self.total_duration_ms < 0:
            raise ValueError(f"total_duration_ms cannot be negative, got {self.total_duration_ms}")
        if self.active_duration_ms > self.total_duration_ms:
            raise ValueError(
                f"active_duration_ms ({self.active_duration_ms}) cannot exceed "
                f"total_duration_ms ({self.total_duration_ms})"
            )
        if self.total_pause_duration_ms is not None:
            if self.total_pause_duration_ms < 0:
                raise ValueError(
                    "total_pause_duration_ms cannot be negative, "
                    f"got {self.total_pause_duration_ms}"
                )
            if self.total_pause_duration_ms > self.total_duration_ms:
                raise ValueError(
                    f"total_pause_duration_ms ({self.total_pause_duration_ms}) cannot exceed "
                    f"total_duration_ms ({self.total_duration_ms})"
                )
        if self.hesitation_count is not None and self.hesitation_count < 0:
            raise ValueError(f"hesitation_count cannot be negative, got {self.hesitation_count}")
        if self.pause_count is not None and self.pause_count < 0:
            raise ValueError(f"pause_count cannot be negative, got {self.pause_count}")


@dataclass(frozen=True, slots=True)
class CompletionStatistics:
    """Factual summary of reading completion and duration ratios."""

    completion_status: CompletionStatus
    is_fully_read: bool
    completion_ratio: float | None
    active_time_ratio: float | None
    pause_time_ratio: float | None


@dataclass(frozen=True, slots=True)
class HesitationStatistics:
    """Hesitation rate normalized by attempted words and active speech time."""

    hesitation_count: int
    rate_per_word: float | None
    rate_per_minute: float | None


@dataclass(frozen=True, slots=True)
class EngagementWeights:
    """Explicitly documented weights for the experimental engagement heuristic."""

    completion_weight: float = 0.50
    active_time_weight: float = 0.30
    pause_efficiency_weight: float = 0.20

    def __post_init__(self) -> None:
        total = self.completion_weight + self.active_time_weight + self.pause_efficiency_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Engagement weights must sum to 1.0, got {total}")
        if (
            self.completion_weight < 0.0
            or self.active_time_weight < 0.0
            or self.pause_efficiency_weight < 0.0
        ):
            raise ValueError("Engagement weights cannot be negative")


@dataclass(frozen=True, slots=True)
class EngagementIndicator:
    """Versioned composite engagement score labeled as an unvalidated heuristic."""

    score: float | None
    is_computable: bool
    formula_version: str
    weights: EngagementWeights
    completion_subscore: float | None
    active_time_subscore: float | None
    pause_efficiency_subscore: float | None
    missing_measurements: list[str]
    disclaimer: str = (
        "Experimental educational research heuristic only; "
        "does not measure or infer clinical, psychological, or attentional states."
    )


@dataclass(frozen=True, slots=True)
class PartitionKey:
    """Contextual grouping key to ensure like-for-like progress comparison."""

    task_type: str
    difficulty_tier: str
    support_mode: str


@dataclass(frozen=True, slots=True)
class PartitionProgress:
    """Longitudinal metrics aggregated strictly within a comparable context partition."""

    key: PartitionKey
    session_count: int
    has_sufficient_evidence: bool
    min_required_sessions: int
    total_words_attempted: int
    total_words_correct: int
    mean_accuracy: float | None
    mean_wpm: float | None
    mean_hesitation_rate_per_word: float | None
    accuracy_trend_delta: float | None
    wpm_trend_delta: float | None
    status: Literal["sufficient_evidence", "insufficient_data", "no_sessions"]


def calculate_reading_accuracy(words_attempted: int, words_correct: int) -> float | None:
    """Calculate decoding accuracy rate as a proportion in [0.0000, 1.0000].

    Formula:
        accuracy = words_correct / words_attempted

    Zero-denominator behavior:
        If words_attempted == 0, returns None. Missing attempts must not be penalized
        as 0% accuracy.

    Validation:
        Raises ValueError if counts are negative or if words_correct > words_attempted.
    """
    if words_attempted < 0 or words_correct < 0:
        raise ValueError("Word counts cannot be negative")
    if words_correct > words_attempted:
        raise ValueError(
            f"words_correct ({words_correct}) cannot exceed words_attempted ({words_attempted})"
        )
    if words_attempted == 0:
        return None
    return round(words_correct / words_attempted, 4)


def calculate_words_per_minute(
    words_attempted: int,
    active_duration_ms: int,
    min_duration_ms: int = 1000,
    max_wpm: int | None = None,
) -> float | None:
    """Calculate reading pace scaled to words per minute.

    Formula:
        WPM = words_attempted / (active_duration_ms / 60,000.0)

    Zero-denominator and threshold behavior:
        If active_duration_ms < min_duration_ms (default 1,000 ms), returns None
        because duration is insufficient to produce a meaningful reading pace.
        If words_attempted == 0 and active_duration_ms >= min_duration_ms, returns 0.0.
        If max_wpm is specified and the computed WPM exceeds max_wpm, returns None
        to filter out implausible pacing outliers (e.g., telemetry capture artifacts).
        Note: max_wpm is an unvalidated research ceiling / heuristic, not an empirically
        established physiological limit.

    Validation:
        Raises ValueError if words_attempted < 0, active_duration_ms < 0, min_duration_ms < 0,
        or max_wpm is negative.
    """
    if words_attempted < 0:
        raise ValueError(f"words_attempted cannot be negative, got {words_attempted}")
    if active_duration_ms < 0:
        raise ValueError(f"active_duration_ms cannot be negative, got {active_duration_ms}")
    if min_duration_ms < 0:
        raise ValueError(f"min_duration_ms cannot be negative, got {min_duration_ms}")
    if max_wpm is not None and max_wpm < 0:
        raise ValueError(f"max_wpm cannot be negative, got {max_wpm}")
    if active_duration_ms < min_duration_ms:
        return None
    if words_attempted == 0:
        return 0.0
    minutes = active_duration_ms / 60000.0
    wpm = round(words_attempted / minutes, 2)
    if max_wpm is not None and wpm > max_wpm:
        return None
    return wpm


def calculate_hesitation_frequency(
    hesitation_count: int | None,
    words_attempted: int,
    active_duration_ms: int,
    min_duration_ms: int = 1000,
) -> HesitationStatistics | None:
    """Calculate hesitation frequency per attempted word and per minute of speech.

    Hesitations represent acoustic pauses >= 2.5 seconds before pronouncing a word.

    Missing data behavior:
        If hesitation_count is None, returns None. Uninstrumented sessions are not
        assumed to have zero hesitations.

    Zero-denominator behavior:
        - rate_per_word is None when words_attempted == 0.
        - rate_per_minute is None when active_duration_ms < min_duration_ms.

    Validation:
        Raises ValueError if hesitation_count < 0, words_attempted < 0, or active_duration_ms < 0.
    """
    if hesitation_count is None:
        return None
    if hesitation_count < 0:
        raise ValueError(f"hesitation_count cannot be negative, got {hesitation_count}")
    if words_attempted < 0:
        raise ValueError(f"words_attempted cannot be negative, got {words_attempted}")
    if active_duration_ms < 0:
        raise ValueError(f"active_duration_ms cannot be negative, got {active_duration_ms}")

    rate_per_word: float | None = None
    if words_attempted > 0:
        rate_per_word = round(hesitation_count / words_attempted, 4)

    rate_per_minute: float | None = None
    if active_duration_ms >= min_duration_ms:
        minutes = active_duration_ms / 60000.0
        rate_per_minute = round(hesitation_count / minutes, 2)

    return HesitationStatistics(
        hesitation_count=hesitation_count,
        rate_per_word=rate_per_word,
        rate_per_minute=rate_per_minute,
    )


def calculate_completion_statistics(telemetry: SessionTelemetry) -> CompletionStatistics:
    """Derive factual completion metrics without applying arbitrary pass/fail thresholds.

    Definitions:
        - is_fully_read: True when words_attempted >= target_word_count (and target > 0).
        - completion_ratio: words_attempted / target_word_count (None if target == 0).
          Note: completion_ratio may exceed 1.0 when words_attempted exceeds target_word_count
          (e.g., repeated-word attempts, self-corrections, or rereading).
          This is factual and intentional.
        - active_time_ratio: active_duration_ms / total_duration_ms (None if total == 0).
        - pause_time_ratio: total_pause_duration_ms / total_duration_ms (None if unmeasured).
    """
    is_fully_read = (
        telemetry.target_word_count > 0 and telemetry.words_attempted >= telemetry.target_word_count
    )

    completion_ratio: float | None = None
    if telemetry.target_word_count > 0:
        completion_ratio = round(telemetry.words_attempted / telemetry.target_word_count, 4)

    active_time_ratio: float | None = None
    if telemetry.total_duration_ms > 0:
        active_time_ratio = round(telemetry.active_duration_ms / telemetry.total_duration_ms, 4)

    pause_time_ratio: float | None = None
    if telemetry.total_pause_duration_ms is not None and telemetry.total_duration_ms > 0:
        pause_time_ratio = round(telemetry.total_pause_duration_ms / telemetry.total_duration_ms, 4)

    return CompletionStatistics(
        completion_status=telemetry.completion_status,
        is_fully_read=is_fully_read,
        completion_ratio=completion_ratio,
        active_time_ratio=active_time_ratio,
        pause_time_ratio=pause_time_ratio,
    )


def calculate_experimental_engagement(
    telemetry: SessionTelemetry,
    weights: EngagementWeights | None = None,
) -> EngagementIndicator:
    """Compute versioned composite engagement heuristic.

    IMPORTANT:
        This metric is an unvalidated research heuristic for software scaffolding.
        It must never be presented as a measure of attention, focus, cognitive ability,
        or psychological state.

    Required measurements:
        - target_word_count > 0
        - total_duration_ms > 0
        - total_pause_duration_ms is not None

    Missing data behavior:
        If ANY required measurement is missing or zero, score is None.
        Missing values are never assumed to be zero.

    Formula (v0.1-research-heuristic):
        score = (w_comp * completion_subscore)
              + (w_act * active_time_subscore)
              + (w_pause * pause_efficiency_subscore)
    """
    applied_weights = weights if weights is not None else EngagementWeights()
    missing_measurements: list[str] = []

    if telemetry.target_word_count <= 0:
        missing_measurements.append("target_word_count")
    if telemetry.total_duration_ms <= 0:
        missing_measurements.append("total_duration_ms")
    if telemetry.total_pause_duration_ms is None:
        missing_measurements.append("total_pause_duration_ms")

    if missing_measurements or telemetry.total_pause_duration_ms is None:
        return EngagementIndicator(
            score=None,
            is_computable=False,
            formula_version=ENGAGEMENT_FORMULA_VERSION,
            weights=applied_weights,
            completion_subscore=None,
            active_time_subscore=None,
            pause_efficiency_subscore=None,
            missing_measurements=missing_measurements,
        )

    pause_duration_ms: int = telemetry.total_pause_duration_ms

    # 1. Completion subscore: scale by status and attempted fraction
    raw_completion_fraction = min(1.0, telemetry.words_attempted / telemetry.target_word_count)
    if telemetry.completion_status == "completed":
        completion_subscore = 1.0
    elif telemetry.completion_status == "abandoned":
        completion_subscore = round(raw_completion_fraction, 4)
    else:  # "interrupted"
        completion_subscore = round(0.50 * raw_completion_fraction, 4)

    # 2. Active time subscore: fraction of session spent actively reading
    active_time_subscore = round(
        min(1.0, telemetry.active_duration_ms / telemetry.total_duration_ms), 4
    )

    # 3. Pause efficiency subscore: penalize excessive pause time relative to active reading
    # If active reading is 0 ms, efficiency is 0.0.
    if telemetry.active_duration_ms == 0:
        pause_efficiency_subscore = 0.0
    else:
        # Benchmark allowance: pauses exceeding 50% of active reading duration reduce efficiency
        pause_burden = pause_duration_ms / (telemetry.active_duration_ms * 0.50)
        pause_penalty = min(1.0, pause_burden)
        pause_efficiency_subscore = round(max(0.0, 1.0 - pause_penalty), 4)

    composite_score = round(
        (applied_weights.completion_weight * completion_subscore)
        + (applied_weights.active_time_weight * active_time_subscore)
        + (applied_weights.pause_efficiency_weight * pause_efficiency_subscore),
        4,
    )
    composite_score = max(0.0, min(1.0, composite_score))

    return EngagementIndicator(
        score=composite_score,
        is_computable=True,
        formula_version=ENGAGEMENT_FORMULA_VERSION,
        weights=applied_weights,
        completion_subscore=completion_subscore,
        active_time_subscore=active_time_subscore,
        pause_efficiency_subscore=pause_efficiency_subscore,
        missing_measurements=[],
    )


def calculate_partitioned_progress(
    sessions: Sequence[SessionTelemetry],
    min_required_sessions: int = 3,
    max_wpm: int | None = None,
) -> dict[PartitionKey, PartitionProgress]:
    """Calculate progress indicators partitioned strictly by comparable contexts.

    Progress comparisons across different difficulty tiers (e.g. Early vs Advanced)
    or task types (e.g. Independent vs Assisted) produce uninterpretable conflations.
    This function groups sessions by PartitionKey(task_type, difficulty_tier, support_mode).

    Chronological ordering:
        Within each partition, sessions are sorted chronologically by
        `(session_start_time, session_id or "")` prior to metric aggregation and trend
        calculation. Callers are NOT required to provide pre-sorted session lists;
        the function is completely deterministic regardless of input list permutation.
        Identical timestamps are broken deterministically using `session_id`.

    Trend delta & odd-numbered session groups:
        Longitudinal trend deltas are calculated when `session_count >= 2` as
        `mean(second_half) - mean(first_half)`. For odd-numbered session counts
        (e.g., N=3 or N=5), integer floor division `half_point = session_count // 2`
        is applied: `first_half = partition[:half_point]` and
        `second_half = partition[half_point:]`.
        Consequently, the second half contains the extra middle session (e.g., for N=3,
        first half has 1 session, second half has 2; for N=5, first half has 2 sessions,
        second half has 3). This slight asymmetry provides slightly heavier weighting to
        more recent observations while maintaining a completely deterministic split.

    Insufficient sample size behavior:
        If a partition contains fewer than min_required_sessions, has_sufficient_evidence
        is set to False, and status is 'insufficient_data'.
    """
    if min_required_sessions < 1:
        raise ValueError(f"min_required_sessions must be >= 1, got {min_required_sessions}")

    grouped: dict[PartitionKey, list[SessionTelemetry]] = defaultdict(list)
    for session in sessions:
        key = PartitionKey(
            task_type=session.task_type,
            difficulty_tier=session.difficulty_tier,
            support_mode=session.support_mode,
        )
        grouped[key].append(session)

    results: dict[PartitionKey, PartitionProgress] = {}

    for key, partition in grouped.items():
        # Sort chronologically by (session_start_time, session_id or "")
        partition.sort(key=lambda s: (s.session_start_time, s.session_id or ""))

        session_count = len(partition)
        has_sufficient = session_count >= min_required_sessions
        status: Literal["sufficient_evidence", "insufficient_data", "no_sessions"] = (
            "sufficient_evidence" if has_sufficient else "insufficient_data"
        )

        total_words_attempted = sum(s.words_attempted for s in partition)
        total_words_correct = sum(s.words_correct for s in partition)

        # Compute valid accuracies
        accuracies = [
            acc
            for s in partition
            if (acc := calculate_reading_accuracy(s.words_attempted, s.words_correct)) is not None
        ]
        mean_accuracy = round(sum(accuracies) / len(accuracies), 4) if accuracies else None

        # Compute valid WPMs
        wpms = [
            wpm
            for s in partition
            if (
                wpm := calculate_words_per_minute(
                    s.words_attempted, s.active_duration_ms, max_wpm=max_wpm
                )
            )
            is not None
        ]
        mean_wpm = round(sum(wpms) / len(wpms), 2) if wpms else None

        # Compute valid hesitation rates per word
        hesitation_rates: list[float] = []
        for s in partition:
            hes_stats = calculate_hesitation_frequency(
                s.hesitation_count, s.words_attempted, s.active_duration_ms
            )
            if hes_stats is not None and hes_stats.rate_per_word is not None:
                hesitation_rates.append(hes_stats.rate_per_word)
        mean_hesitation_rate = (
            round(sum(hesitation_rates) / len(hesitation_rates), 4) if hesitation_rates else None
        )

        # Compute longitudinal trend deltas (second-half mean minus first-half mean)
        accuracy_trend_delta: float | None = None
        wpm_trend_delta: float | None = None
        if session_count >= 2:
            half_point = session_count // 2
            first_half = partition[:half_point]
            second_half = partition[half_point:]

            first_accs = [
                acc
                for s in first_half
                if (acc := calculate_reading_accuracy(s.words_attempted, s.words_correct))
                is not None
            ]
            second_accs = [
                acc
                for s in second_half
                if (acc := calculate_reading_accuracy(s.words_attempted, s.words_correct))
                is not None
            ]
            if first_accs and second_accs:
                mean_first = sum(first_accs) / len(first_accs)
                mean_second = sum(second_accs) / len(second_accs)
                accuracy_trend_delta = round(mean_second - mean_first, 4)

            first_wpms = [
                wpm
                for s in first_half
                if (
                    wpm := calculate_words_per_minute(
                        s.words_attempted, s.active_duration_ms, max_wpm=max_wpm
                    )
                )
                is not None
            ]
            second_wpms = [
                wpm
                for s in second_half
                if (
                    wpm := calculate_words_per_minute(
                        s.words_attempted, s.active_duration_ms, max_wpm=max_wpm
                    )
                )
                is not None
            ]
            if first_wpms and second_wpms:
                mean_first_wpm = sum(first_wpms) / len(first_wpms)
                mean_second_wpm = sum(second_wpms) / len(second_wpms)
                wpm_trend_delta = round(mean_second_wpm - mean_first_wpm, 2)

        results[key] = PartitionProgress(
            key=key,
            session_count=session_count,
            has_sufficient_evidence=has_sufficient,
            min_required_sessions=min_required_sessions,
            total_words_attempted=total_words_attempted,
            total_words_correct=total_words_correct,
            mean_accuracy=mean_accuracy,
            mean_wpm=mean_wpm,
            mean_hesitation_rate_per_word=mean_hesitation_rate,
            accuracy_trend_delta=accuracy_trend_delta,
            wpm_trend_delta=wpm_trend_delta,
            status=status,
        )

    return results
