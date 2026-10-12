"""Unit tests for deterministic educational analytics calculations.

Tests verify mathematical correctness, boundary invariants, zero-denominator safety,
missing-measurement handling, context partitioning, and deterministic stability using
synthetic test fixtures.
"""

from datetime import UTC, datetime

import pytest

from app.modules.learner_modelling.analytics import (
    ENGAGEMENT_FORMULA_VERSION,
    CompletionStatistics,
    EngagementIndicator,
    EngagementWeights,
    PartitionKey,
    SessionTelemetry,
    calculate_completion_statistics,
    calculate_experimental_engagement,
    calculate_hesitation_frequency,
    calculate_partitioned_progress,
    calculate_reading_accuracy,
    calculate_words_per_minute,
)


def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# ==============================================================================
# 1. Reading Accuracy Tests
# ==============================================================================


def test_reading_accuracy_known_values() -> None:
    # 45 correct out of 50 attempted = 0.9000 (90%)
    assert calculate_reading_accuracy(words_attempted=50, words_correct=45) == 0.9000
    # 100 correct out of 100 attempted = 1.0000 (100%)
    assert calculate_reading_accuracy(words_attempted=100, words_correct=100) == 1.0000
    # 0 correct out of 50 attempted = 0.0000 (0%)
    assert calculate_reading_accuracy(words_attempted=50, words_correct=0) == 0.0000
    # 104 correct out of 118 attempted = 0.8814
    assert calculate_reading_accuracy(words_attempted=118, words_correct=104) == 0.8814


def test_reading_accuracy_zero_denominator_returns_none() -> None:
    # When no words are attempted, accuracy is undefined (None), NOT 0%
    assert calculate_reading_accuracy(words_attempted=0, words_correct=0) is None


def test_reading_accuracy_rejects_negative_or_exceeding_counts() -> None:
    with pytest.raises(ValueError, match="Word counts cannot be negative"):
        calculate_reading_accuracy(words_attempted=-1, words_correct=0)

    with pytest.raises(ValueError, match="Word counts cannot be negative"):
        calculate_reading_accuracy(words_attempted=10, words_correct=-2)

    with pytest.raises(ValueError, match="words_correct .* cannot exceed words_attempted"):
        calculate_reading_accuracy(words_attempted=50, words_correct=51)


# ==============================================================================
# 2. Words Per Minute (WPM) Tests
# ==============================================================================


def test_words_per_minute_known_values() -> None:
    # 120 words in 120,000 ms (2.0 minutes) = 60.00 WPM
    assert calculate_words_per_minute(words_attempted=120, active_duration_ms=120000) == 60.00
    # 50 words in 30,000 ms (0.5 minutes) = 100.00 WPM
    assert calculate_words_per_minute(words_attempted=50, active_duration_ms=30000) == 100.00
    # 118 words in 412,000 ms (6.8667 minutes) = 17.18 WPM
    assert calculate_words_per_minute(words_attempted=118, active_duration_ms=412000) == 17.18


def test_words_per_minute_zero_and_threshold_behavior() -> None:
    # Zero duration returns None (cannot divide by zero)
    assert calculate_words_per_minute(words_attempted=10, active_duration_ms=0) is None

    # Duration below minimum threshold (e.g. 500 ms < 1000 ms) returns None
    assert calculate_words_per_minute(words_attempted=2, active_duration_ms=500) is None

    # Zero attempted words with adequate active reading time returns 0.0 WPM
    assert calculate_words_per_minute(words_attempted=0, active_duration_ms=60000) == 0.0


def test_words_per_minute_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="words_attempted cannot be negative"):
        calculate_words_per_minute(words_attempted=-5, active_duration_ms=60000)

    with pytest.raises(ValueError, match="active_duration_ms cannot be negative"):
        calculate_words_per_minute(words_attempted=50, active_duration_ms=-1000)


# ==============================================================================
# 3. Hesitation Frequency Tests
# ==============================================================================


def test_hesitation_frequency_known_values() -> None:
    # 5 hesitations on 50 words across 120,000 ms (2.0 min)
    # rate_per_word = 5/50 = 0.1000, rate_per_minute = 5/2.0 = 2.50
    stats = calculate_hesitation_frequency(
        hesitation_count=5, words_attempted=50, active_duration_ms=120000
    )
    assert stats is not None
    assert stats.hesitation_count == 5
    assert stats.rate_per_word == 0.1000
    assert stats.rate_per_minute == 2.50


def test_hesitation_frequency_missing_measurement_returns_none() -> None:
    # If hesitation was not measured (None), result is None, not 0
    assert (
        calculate_hesitation_frequency(
            hesitation_count=None, words_attempted=50, active_duration_ms=60000
        )
        is None
    )


def test_hesitation_frequency_zero_denominators() -> None:
    # 0 attempted words -> rate_per_word is None
    stats = calculate_hesitation_frequency(
        hesitation_count=2, words_attempted=0, active_duration_ms=60000
    )
    assert stats is not None
    assert stats.rate_per_word is None
    assert stats.rate_per_minute == 2.00

    # 0 active duration -> rate_per_minute is None
    stats_zero_time = calculate_hesitation_frequency(
        hesitation_count=2, words_attempted=10, active_duration_ms=0
    )
    assert stats_zero_time is not None
    assert stats_zero_time.rate_per_word == 0.2000
    assert stats_zero_time.rate_per_minute is None


def test_hesitation_frequency_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="hesitation_count cannot be negative"):
        calculate_hesitation_frequency(
            hesitation_count=-1, words_attempted=10, active_duration_ms=60000
        )


# ==============================================================================
# 4. Session Completion Statistics Tests
# ==============================================================================


def test_completion_statistics_completed_session() -> None:
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=100,
        words_correct=92,
        target_word_count=100,
        active_duration_ms=80000,
        total_duration_ms=100000,
        total_pause_duration_ms=20000,
        completion_status="completed",
    )
    stats = calculate_completion_statistics(telemetry)
    assert isinstance(stats, CompletionStatistics)
    assert stats.completion_status == "completed"
    assert stats.is_fully_read is True
    assert stats.completion_ratio == 1.0000
    assert stats.active_time_ratio == 0.8000
    assert stats.pause_time_ratio == 0.2000


def test_completion_statistics_abandoned_session() -> None:
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=40,
        words_correct=32,
        target_word_count=100,
        active_duration_ms=30000,
        total_duration_ms=50000,
        total_pause_duration_ms=20000,
        completion_status="abandoned",
    )
    stats = calculate_completion_statistics(telemetry)
    assert stats.completion_status == "abandoned"
    assert stats.is_fully_read is False
    assert stats.completion_ratio == 0.4000
    assert stats.active_time_ratio == 0.6000
    assert stats.pause_time_ratio == 0.4000


def test_completion_statistics_missing_pause_telemetry() -> None:
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=50,
        words_correct=45,
        target_word_count=50,
        active_duration_ms=40000,
        total_duration_ms=50000,
        total_pause_duration_ms=None,
    )
    stats = calculate_completion_statistics(telemetry)
    assert stats.pause_time_ratio is None
    assert stats.active_time_ratio == 0.8000


def test_session_telemetry_validates_invariants() -> None:
    with pytest.raises(ValueError, match="active_duration_ms .* cannot exceed total_duration_ms"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=10,
            words_correct=10,
            target_word_count=10,
            active_duration_ms=70000,
            total_duration_ms=60000,
        )

    with pytest.raises(
        ValueError, match="total_pause_duration_ms .* cannot exceed total_duration_ms"
    ):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=10,
            words_correct=10,
            target_word_count=10,
            active_duration_ms=50000,
            total_duration_ms=60000,
            total_pause_duration_ms=65000,
        )


# ==============================================================================
# 5. Experimental Engagement Indicator Tests
# ==============================================================================


def test_experimental_engagement_known_values() -> None:
    # Completed session:
    # completion_subscore = 1.0 (completed)
    # active_time_subscore = 40000 / 50000 = 0.8000
    # pause_time = 10000 ms, active_time * 0.5 = 20000 ms. pause_burden = 10000/20000 = 0.50.
    # pause_efficiency_subscore = 1.0 - 0.50 = 0.5000
    # composite = 0.50*1.0 + 0.30*0.80 + 0.20*0.50 = 0.50 + 0.24 + 0.10 = 0.8400
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=100,
        words_correct=90,
        target_word_count=100,
        active_duration_ms=40000,
        total_duration_ms=50000,
        total_pause_duration_ms=10000,
        completion_status="completed",
    )
    result = calculate_experimental_engagement(telemetry)

    assert isinstance(result, EngagementIndicator)
    assert result.is_computable is True
    assert result.score == 0.8400
    assert result.completion_subscore == 1.0
    assert result.active_time_subscore == 0.8000
    assert result.pause_efficiency_subscore == 0.5000
    assert result.formula_version == ENGAGEMENT_FORMULA_VERSION
    assert len(result.missing_measurements) == 0
    assert "heuristic" in result.disclaimer.lower()


def test_experimental_engagement_missing_measurements_returns_none() -> None:
    # Missing pause duration must cause indicator to return None
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=50,
        words_correct=45,
        target_word_count=50,
        active_duration_ms=30000,
        total_duration_ms=40000,
        total_pause_duration_ms=None,
    )
    result = calculate_experimental_engagement(telemetry)
    assert result.is_computable is False
    assert result.score is None
    assert "total_pause_duration_ms" in result.missing_measurements


def test_experimental_engagement_custom_weights() -> None:
    custom_weights = EngagementWeights(
        completion_weight=0.40,
        active_time_weight=0.40,
        pause_efficiency_weight=0.20,
    )
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=100,
        words_correct=90,
        target_word_count=100,
        active_duration_ms=40000,
        total_duration_ms=50000,
        total_pause_duration_ms=10000,
        completion_status="completed",
    )
    result = calculate_experimental_engagement(telemetry, weights=custom_weights)
    # composite = 0.40*1.0 + 0.40*0.80 + 0.20*0.50 = 0.40 + 0.32 + 0.10 = 0.8200
    assert result.score == 0.8200
    assert result.weights == custom_weights


def test_engagement_weights_validation() -> None:
    with pytest.raises(ValueError, match="Engagement weights must sum to 1.0"):
        EngagementWeights(
            completion_weight=0.5, active_time_weight=0.5, pause_efficiency_weight=0.5
        )

    with pytest.raises(ValueError, match="Engagement weights cannot be negative"):
        EngagementWeights(
            completion_weight=1.2, active_time_weight=-0.2, pause_efficiency_weight=0.0
        )


# ==============================================================================
# 6. Context-Partitioned Progress Tests
# ==============================================================================


def test_partitioned_progress_separates_contexts_and_enforces_evidence() -> None:
    # 3 sessions of Independent Reading at Intermediate difficulty
    part1_sessions = [
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            session_id="s1",
            words_attempted=50,
            words_correct=40,
            target_word_count=50,
            active_duration_ms=60000,  # 50 WPM
            total_duration_ms=70000,
            task_type="independent_reading",
            difficulty_tier="intermediate",
            support_mode="adaptive",
        ),
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 2),
            session_id="s2",
            words_attempted=50,
            words_correct=42,
            target_word_count=50,
            active_duration_ms=50000,  # 60 WPM
            total_duration_ms=60000,
            task_type="independent_reading",
            difficulty_tier="intermediate",
            support_mode="adaptive",
        ),
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 3),
            session_id="s3",
            words_attempted=50,
            words_correct=45,
            target_word_count=50,
            active_duration_ms=45000,  # 66.67 WPM
            total_duration_ms=55000,
            task_type="independent_reading",
            difficulty_tier="intermediate",
            support_mode="adaptive",
        ),
    ]

    # 1 session of Assisted Reading at Advanced difficulty (insufficient evidence)
    part2_sessions = [
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            session_id="s4",
            words_attempted=80,
            words_correct=60,
            target_word_count=80,
            active_duration_ms=100000,
            total_duration_ms=120000,
            task_type="assisted_read_aloud",
            difficulty_tier="advanced",
            support_mode="adaptive",
        ),
    ]

    combined = part1_sessions + part2_sessions
    results = calculate_partitioned_progress(combined, min_required_sessions=3)

    key_part1 = PartitionKey(
        task_type="independent_reading",
        difficulty_tier="intermediate",
        support_mode="adaptive",
    )
    key_part2 = PartitionKey(
        task_type="assisted_read_aloud",
        difficulty_tier="advanced",
        support_mode="adaptive",
    )

    assert len(results) == 2
    assert key_part1 in results
    assert key_part2 in results

    # Partition 1 has 3 sessions -> sufficient evidence
    p1 = results[key_part1]
    assert p1.session_count == 3
    assert p1.has_sufficient_evidence is True
    assert p1.status == "sufficient_evidence"
    assert p1.total_words_attempted == 150
    assert p1.total_words_correct == 127
    # Mean accuracy = (40/50 + 42/50 + 45/50) / 3 = (0.8000 + 0.8400 + 0.9000) / 3 = 0.8467
    assert p1.mean_accuracy == 0.8467
    # Mean WPM = (50.0 + 60.0 + 66.67) / 3 = 58.89
    assert p1.mean_wpm == 58.89
    # Trend delta: second half (s2, s3) mean minus first half (s1) mean
    # Second half mean accuracy = (0.8400 + 0.9000)/2 = 0.8700
    # First half mean accuracy = 0.8000
    # Delta = 0.8700 - 0.8000 = +0.0700
    assert p1.accuracy_trend_delta == 0.0700

    # Partition 2 has only 1 session -> insufficient data
    p2 = results[key_part2]
    assert p2.session_count == 1
    assert p2.has_sufficient_evidence is False
    assert p2.status == "insufficient_data"
    assert p2.accuracy_trend_delta is None  # Cannot compute trend with < 2 sessions


def test_partitioned_progress_min_required_sessions_validation() -> None:
    with pytest.raises(ValueError, match="min_required_sessions must be >= 1"):
        calculate_partitioned_progress([], min_required_sessions=0)


# ==============================================================================
# 7. Determinism and Version Stability
# ==============================================================================


def test_deterministic_stability() -> None:
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=118,
        words_correct=104,
        target_word_count=120,
        active_duration_ms=412000,
        total_duration_ms=495000,
        hesitation_count=6,
        total_pause_duration_ms=45000,
        completion_status="completed",
    )

    first_acc = calculate_reading_accuracy(telemetry.words_attempted, telemetry.words_correct)
    first_wpm = calculate_words_per_minute(telemetry.words_attempted, telemetry.active_duration_ms)
    first_eng = calculate_experimental_engagement(telemetry)

    # Re-run 100 times to verify deterministic reproducibility
    for _ in range(100):
        acc = calculate_reading_accuracy(telemetry.words_attempted, telemetry.words_correct)
        assert acc == first_acc
        wpm = calculate_words_per_minute(telemetry.words_attempted, telemetry.active_duration_ms)
        assert wpm == first_wpm
        assert calculate_experimental_engagement(telemetry).score == first_eng.score


def test_session_telemetry_additional_invariants() -> None:
    with pytest.raises(ValueError, match="words_attempted cannot be negative"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=-1,
            words_correct=0,
            target_word_count=10,
            active_duration_ms=1000,
            total_duration_ms=2000,
        )

    with pytest.raises(ValueError, match="words_correct cannot be negative"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=10,
            words_correct=-1,
            target_word_count=10,
            active_duration_ms=1000,
            total_duration_ms=2000,
        )

    with pytest.raises(ValueError, match="words_correct .* cannot exceed words_attempted"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=10,
            words_correct=12,
            target_word_count=10,
            active_duration_ms=1000,
            total_duration_ms=2000,
        )

    with pytest.raises(ValueError, match="target_word_count cannot be negative"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=5,
            words_correct=5,
            target_word_count=-1,
            active_duration_ms=1000,
            total_duration_ms=2000,
        )

    with pytest.raises(ValueError, match="active_duration_ms cannot be negative"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=5,
            words_correct=5,
            target_word_count=10,
            active_duration_ms=-1,
            total_duration_ms=2000,
        )

    with pytest.raises(ValueError, match="total_duration_ms cannot be negative"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=5,
            words_correct=5,
            target_word_count=10,
            active_duration_ms=1000,
            total_duration_ms=-1,
        )

    with pytest.raises(ValueError, match="total_pause_duration_ms cannot be negative"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=5,
            words_correct=5,
            target_word_count=10,
            active_duration_ms=1000,
            total_duration_ms=2000,
            total_pause_duration_ms=-1,
        )

    with pytest.raises(ValueError, match="hesitation_count cannot be negative"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=5,
            words_correct=5,
            target_word_count=10,
            active_duration_ms=1000,
            total_duration_ms=2000,
            hesitation_count=-1,
        )

    with pytest.raises(ValueError, match="pause_count cannot be negative"):
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            words_attempted=5,
            words_correct=5,
            target_word_count=10,
            active_duration_ms=1000,
            total_duration_ms=2000,
            pause_count=-1,
        )


def test_experimental_engagement_interrupted_and_zero_active_duration() -> None:
    # Interrupted session with 50/100 words attempted:
    # completion_subscore = 0.50 * (50/100) = 0.2500
    # active_time = 0 -> active_time_subscore = 0.0, pause_efficiency = 0.0
    telemetry_interrupted = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=50,
        words_correct=45,
        target_word_count=100,
        active_duration_ms=0,
        total_duration_ms=50000,
        total_pause_duration_ms=20000,
        completion_status="interrupted",
    )
    result = calculate_experimental_engagement(telemetry_interrupted)
    assert result.is_computable is True
    assert result.completion_subscore == 0.2500
    assert result.active_time_subscore == 0.0
    assert result.pause_efficiency_subscore == 0.0
    # composite = 0.50 * 0.2500 + 0.30 * 0.0 + 0.20 * 0.0 = 0.1250
    assert result.score == 0.1250


def test_experimental_engagement_missing_target_or_total_duration() -> None:
    telemetry_zero_target = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=0,
        words_correct=0,
        target_word_count=0,
        active_duration_ms=0,
        total_duration_ms=50000,
        total_pause_duration_ms=10000,
    )
    res1 = calculate_experimental_engagement(telemetry_zero_target)
    assert res1.is_computable is False
    assert "target_word_count" in res1.missing_measurements

    telemetry_zero_duration = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=10,
        words_correct=10,
        target_word_count=50,
        active_duration_ms=0,
        total_duration_ms=0,
        total_pause_duration_ms=0,
    )
    res2 = calculate_experimental_engagement(telemetry_zero_duration)
    assert res2.is_computable is False
    assert "total_duration_ms" in res2.missing_measurements


def test_completion_statistics_zero_durations() -> None:
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=0,
        words_correct=0,
        target_word_count=0,
        active_duration_ms=0,
        total_duration_ms=0,
        total_pause_duration_ms=0,
    )
    stats = calculate_completion_statistics(telemetry)
    assert stats.completion_ratio is None
    assert stats.active_time_ratio is None
    assert stats.pause_time_ratio is None
    assert stats.is_fully_read is False


def test_hesitation_frequency_negative_durations_rejected() -> None:
    with pytest.raises(ValueError, match="words_attempted cannot be negative"):
        calculate_hesitation_frequency(
            hesitation_count=1, words_attempted=-1, active_duration_ms=5000
        )

    with pytest.raises(ValueError, match="active_duration_ms cannot be negative"):
        calculate_hesitation_frequency(
            hesitation_count=1, words_attempted=10, active_duration_ms=-100
        )


# ==============================================================================
# 8. Longitudinal Determinism, Chronological Sorting, and Defect Coverage Tests
# ==============================================================================


def test_session_telemetry_rejects_naive_datetime() -> None:
    """DEFECT 1: SessionTelemetry must reject naive datetimes without timezone info."""
    naive_dt = datetime(2024, 1, 1, 10, 0, 0)  # no tzinfo
    with pytest.raises(ValueError, match="session_start_time must be timezone-aware"):
        SessionTelemetry(
            session_start_time=naive_dt,
            words_attempted=50,
            words_correct=45,
            target_word_count=50,
            active_duration_ms=60000,
            total_duration_ms=70000,
        )


def test_partitioned_progress_shuffled_input_same_result() -> None:
    """DEFECT 1: Input list ordering must not affect longitudinal trend deltas."""
    s1 = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1, 9, 0),
        session_id="session-1",
        words_attempted=50,
        words_correct=35,  # 70%
        target_word_count=50,
        active_duration_ms=60000,
        total_duration_ms=70000,
    )
    s2 = SessionTelemetry(
        session_start_time=_utc(2024, 1, 2, 9, 0),
        session_id="session-2",
        words_attempted=50,
        words_correct=40,  # 80%
        target_word_count=50,
        active_duration_ms=55000,
        total_duration_ms=65000,
    )
    s3 = SessionTelemetry(
        session_start_time=_utc(2024, 1, 3, 9, 0),
        session_id="session-3",
        words_attempted=50,
        words_correct=45,  # 90%
        target_word_count=50,
        active_duration_ms=50000,
        total_duration_ms=60000,
    )
    s4 = SessionTelemetry(
        session_start_time=_utc(2024, 1, 4, 9, 0),
        session_id="session-4",
        words_attempted=50,
        words_correct=48,  # 96%
        target_word_count=50,
        active_duration_ms=45000,
        total_duration_ms=55000,
    )

    key = PartitionKey(
        task_type="independent_reading",
        difficulty_tier="intermediate",
        support_mode="adaptive",
    )

    # Chronological forward order: [s1, s2, s3, s4]
    # First half = [s1, s2] -> mean acc = (0.70 + 0.80)/2 = 0.7500
    # Second half = [s3, s4] -> mean acc = (0.90 + 0.96)/2 = 0.9300
    # Expected delta = 0.9300 - 0.7500 = +0.1800
    forward_results = calculate_partitioned_progress([s1, s2, s3, s4], min_required_sessions=3)
    p_fwd = forward_results[key]
    assert p_fwd.accuracy_trend_delta == 0.1800

    # Reversed order: [s4, s3, s2, s1] - should produce identical results because of internal sort
    reversed_results = calculate_partitioned_progress([s4, s3, s2, s1], min_required_sessions=3)
    p_rev = reversed_results[key]
    assert p_rev.accuracy_trend_delta == 0.1800
    assert p_rev.wpm_trend_delta == p_fwd.wpm_trend_delta
    assert p_rev.mean_accuracy == p_fwd.mean_accuracy

    # Permuted order: [s2, s4, s1, s3]
    permuted_results = calculate_partitioned_progress([s2, s4, s1, s3], min_required_sessions=3)
    p_perm = permuted_results[key]
    assert p_perm.accuracy_trend_delta == 0.1800


def test_partitioned_progress_equal_timestamps_deterministic_tie_breaker() -> None:
    """DEFECT 1: Identical timestamps must be stably sorted by session_id tie-breaker."""
    same_time = _utc(2024, 1, 1, 12, 0)
    s_a = SessionTelemetry(
        session_start_time=same_time,
        session_id="session-a",
        words_attempted=50,
        words_correct=35,
        target_word_count=50,
        active_duration_ms=60000,
        total_duration_ms=70000,
    )
    s_b = SessionTelemetry(
        session_start_time=same_time,
        session_id="session-b",
        words_attempted=50,
        words_correct=45,
        target_word_count=50,
        active_duration_ms=50000,
        total_duration_ms=60000,
    )

    key = PartitionKey(
        task_type="independent_reading",
        difficulty_tier="intermediate",
        support_mode="adaptive",
    )

    # Since timestamps are identical, s_a ("session-a") sorts before s_b ("session-b")
    # First half = [s_a] (0.7000), Second half = [s_b] (0.9000), delta = +0.2000
    res1 = calculate_partitioned_progress([s_a, s_b], min_required_sessions=2)
    res2 = calculate_partitioned_progress([s_b, s_a], min_required_sessions=2)

    assert res1[key].accuracy_trend_delta == 0.2000
    assert res2[key].accuracy_trend_delta == 0.2000


def test_partitioned_progress_odd_session_split_documented() -> None:
    """DEFECT 2: Odd-numbered sessions split via floor division; second half gets extra session."""
    # 5 sessions: floor(5/2) = 2. First half = [:2] (2 sessions), second half = [2:] (3 sessions).
    sessions = [
        SessionTelemetry(
            session_start_time=_utc(2024, 1, day),
            session_id=f"session-{day}",
            words_attempted=50,
            # day 1: 33 (0.66), day 2: 36 (0.72), day 3: 39 (0.78)
            # day 4: 42 (0.84), day 5: 45 (0.90)
            words_correct=30 + day * 3,
            target_word_count=50,
            active_duration_ms=60000,
            total_duration_ms=70000,
        )
        for day in range(1, 6)
    ]
    key = PartitionKey(
        task_type="independent_reading",
        difficulty_tier="intermediate",
        support_mode="adaptive",
    )
    results = calculate_partitioned_progress(sessions, min_required_sessions=3)
    p = results[key]
    assert p.session_count == 5
    # First half: day 1 (0.66) + day 2 (0.72) -> mean = 0.6900
    # Second half: day 3 (0.78) + day 4 (0.84) + day 5 (0.90) -> mean = 0.8400
    # Delta = 0.8400 - 0.6900 = +0.1500
    assert p.accuracy_trend_delta == 0.1500


def test_words_per_minute_max_wpm_ceiling() -> None:
    """DEFECT 3: max_wpm parameter acts as an outlier filter when specified."""
    # 200 words in 2000 ms (0.0333 min) = 6000.00 WPM (an instrument capture glitch)
    # Default behavior without max_wpm: computes raw value
    assert calculate_words_per_minute(words_attempted=200, active_duration_ms=2000) == 6000.00

    # With max_wpm cap: returns None when exceeded
    assert (
        calculate_words_per_minute(words_attempted=200, active_duration_ms=2000, max_wpm=600)
        is None
    )

    # Within legitimate bounds: returns computed WPM
    assert (
        calculate_words_per_minute(words_attempted=50, active_duration_ms=30000, max_wpm=600)
        == 100.00
    )

    # Negative max_wpm must raise ValueError
    with pytest.raises(ValueError, match="max_wpm cannot be negative"):
        calculate_words_per_minute(words_attempted=50, active_duration_ms=30000, max_wpm=-1)


def test_partitioned_progress_passes_max_wpm() -> None:
    """DEFECT 3: calculate_partitioned_progress forwards max_wpm to ignore outliers."""
    sessions = [
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 1),
            session_id="s1",
            words_attempted=50,
            words_correct=45,
            target_word_count=50,
            active_duration_ms=60000,  # 50 WPM (normal)
            total_duration_ms=70000,
        ),
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 2),
            session_id="s2",
            words_attempted=200,
            words_correct=190,
            target_word_count=200,
            active_duration_ms=2000,  # 6000 WPM (glitch)
            total_duration_ms=5000,
        ),
        SessionTelemetry(
            session_start_time=_utc(2024, 1, 3),
            session_id="s3",
            words_attempted=50,
            words_correct=46,
            target_word_count=50,
            active_duration_ms=60000,  # 50 WPM (normal)
            total_duration_ms=70000,
        ),
    ]
    key = PartitionKey(
        task_type="independent_reading",
        difficulty_tier="intermediate",
        support_mode="adaptive",
    )

    # Without max_wpm: mean WPM is skewed by glitch: (50 + 6000 + 50) / 3 = 2033.33
    res_uncapped = calculate_partitioned_progress(sessions, min_required_sessions=3)
    assert res_uncapped[key].mean_wpm == 2033.33

    # With max_wpm=600: outlier session is filtered out from WPM: (50 + 50) / 2 = 50.00
    res_capped = calculate_partitioned_progress(sessions, min_required_sessions=3, max_wpm=600)
    assert res_capped[key].mean_wpm == 50.00


def test_completion_statistics_ratio_exceeds_one() -> None:
    """DEFECT 4: completion_ratio > 1.0 when words_attempted exceeds target_word_count."""
    telemetry = SessionTelemetry(
        session_start_time=_utc(2024, 1, 1),
        words_attempted=120,
        words_correct=100,
        target_word_count=100,
        active_duration_ms=80000,
        total_duration_ms=100000,
        completion_status="completed",
    )
    stats = calculate_completion_statistics(telemetry)
    assert stats.is_fully_read is True
    assert stats.completion_ratio == 1.2000
