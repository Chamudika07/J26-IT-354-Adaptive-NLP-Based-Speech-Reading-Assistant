"""Synthetic tests for pure longitudinal learning-progress analytics."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

import app.modules.learner_modelling.longitudinal as longitudinal_module
from app.modules.learner_modelling.analytics import (
    ENGAGEMENT_FORMULA_VERSION,
    SessionTelemetry,
)
from app.modules.learner_modelling.longitudinal import (
    EARLY_LATE_WINDOW_SIZE,
    HESITATION_CALCULATION_VERSION,
    LONGITUDINAL_CALCULATION_VERSION,
    MIN_TREND_OBSERVATIONS,
    NON_CLINICAL_LONGITUDINAL_DISCLAIMER,
    READING_ACCURACY_CALCULATION_VERSION,
    WPM_CALCULATION_VERSION,
    LongitudinalObservation,
    LongitudinalWindow,
    MetricTrend,
    calculate_longitudinal_progress,
)

_AUTO_ENGAGEMENT = object()


def _utc(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


def _window(start_day: int = 1, end_day: int = 20) -> LongitudinalWindow:
    return LongitudinalWindow(start_at_utc=_utc(start_day, 0), end_at_utc=_utc(end_day, 0))


def _observation(
    day: int,
    *,
    session_id: str | None = None,
    observed_at: datetime | None = None,
    words_attempted: int = 100,
    words_correct: int = 80,
    target_word_count: int = 100,
    active_duration_ms: int = 60000,
    total_duration_ms: int = 70000,
    hesitation_count: int | None = 8,
    total_pause_duration_ms: int | None = 10000,
    task_type: str = "independent_reading",
    difficulty_tier: str = "intermediate",
    support_mode: str = "adaptive",
    engagement_score: Decimal | None | object = _AUTO_ENGAGEMENT,
    engagement_version: str | None = ENGAGEMENT_FORMULA_VERSION,
) -> LongitudinalObservation:
    telemetry = SessionTelemetry(
        session_start_time=observed_at or _utc(day),
        session_id=session_id if session_id is not None else f"session-{day:02d}",
        words_attempted=words_attempted,
        words_correct=words_correct,
        target_word_count=target_word_count,
        active_duration_ms=active_duration_ms,
        total_duration_ms=total_duration_ms,
        hesitation_count=hesitation_count,
        total_pause_duration_ms=total_pause_duration_ms,
        task_type=task_type,
        difficulty_tier=difficulty_tier,
        support_mode=support_mode,
    )
    if engagement_score is _AUTO_ENGAGEMENT:
        return LongitudinalObservation.from_telemetry(telemetry)
    assert engagement_score is None or isinstance(engagement_score, Decimal)
    return LongitudinalObservation(
        telemetry=telemetry,
        engagement_score=engagement_score,
        engagement_formula_version=engagement_version,
    )


def _six_trending_observations() -> list[LongitudinalObservation]:
    correct = [60, 70, 80, 90, 95, 100]
    durations = [120000, 100000, 75000, 60000, 50000, 40000]
    hesitations = [12, 10, 8, 6, 4, 2]
    engagements = ["0.4000", "0.5000", "0.6000", "0.7000", "0.8000", "0.9000"]
    return [
        _observation(
            index,
            words_correct=correct[index - 1],
            active_duration_ms=durations[index - 1],
            total_duration_ms=durations[index - 1] + 10000,
            hesitation_count=hesitations[index - 1],
            engagement_score=Decimal(engagements[index - 1]),
        )
        for index in range(1, 7)
    ]


def _metrics(observations: list[LongitudinalObservation]) -> dict[str, MetricTrend]:
    report = calculate_longitudinal_progress(observations, _window())
    assert len(report.partitions) == 1
    return {metric.metric_name: metric for metric in report.partitions[0].metrics}


def test_all_four_metric_trends_units_versions_and_precision() -> None:
    metrics = _metrics(_six_trending_observations())

    assert tuple(metrics) == (
        "reading_accuracy",
        "reading_fluency_wpm",
        "hesitation_rate_per_word",
        "engagement_score",
    )
    assert metrics["reading_accuracy"].unit == "proportion"
    assert metrics["reading_fluency_wpm"].unit == "words_per_minute"
    assert metrics["hesitation_rate_per_word"].unit == "hesitations_per_attempted_word"
    assert metrics["engagement_score"].unit == "proportion"

    assert metrics["reading_accuracy"].metric_calculation_version == (
        READING_ACCURACY_CALCULATION_VERSION
    )
    assert metrics["reading_fluency_wpm"].metric_calculation_version == WPM_CALCULATION_VERSION
    assert metrics["hesitation_rate_per_word"].metric_calculation_version == (
        HESITATION_CALCULATION_VERSION
    )
    assert metrics["engagement_score"].metric_calculation_version == ENGAGEMENT_FORMULA_VERSION
    assert all(
        metric.longitudinal_calculation_version == LONGITUDINAL_CALCULATION_VERSION
        for metric in metrics.values()
    )

    accuracy = metrics["reading_accuracy"]
    assert accuracy.early_window_mean == Decimal("0.7000")
    assert accuracy.late_window_mean == Decimal("0.9500")
    assert accuracy.numeric_change == Decimal("0.2500")
    assert accuracy.change_direction == "increased"

    wpm = metrics["reading_fluency_wpm"]
    assert wpm.early_window_mean == Decimal("63.33")
    assert wpm.late_window_mean == Decimal("123.33")
    assert wpm.numeric_change == Decimal("60.00")

    hesitation = metrics["hesitation_rate_per_word"]
    assert hesitation.early_window_mean == Decimal("0.1000")
    assert hesitation.late_window_mean == Decimal("0.0400")
    assert hesitation.numeric_change == Decimal("-0.0600")
    assert hesitation.change_direction == "decreased"

    engagement = metrics["engagement_score"]
    assert engagement.early_window_mean == Decimal("0.5000")
    assert engagement.late_window_mean == Decimal("0.8000")
    assert engagement.numeric_change == Decimal("0.3000")


def test_exactly_six_values_use_two_non_overlapping_three_value_windows() -> None:
    metric = _metrics(_six_trending_observations())["reading_accuracy"]
    assert MIN_TREND_OBSERVATIONS == 6
    assert EARLY_LATE_WINDOW_SIZE == 3
    assert metric.valid_observation_count == 6
    assert metric.early_window_count == 3
    assert metric.late_window_count == 3
    assert metric.evidence_sufficient is True


def test_fewer_than_six_values_report_descriptions_without_a_trend() -> None:
    metric = _metrics(_six_trending_observations()[:5])["reading_accuracy"]
    assert metric.valid_observation_count == 5
    assert metric.first_value == Decimal("0.6000")
    assert metric.latest_value == Decimal("0.9500")
    assert metric.evidence_sufficient is False
    assert metric.early_window_count == 0
    assert metric.late_window_count == 0
    assert metric.early_window_mean is None
    assert metric.late_window_mean is None
    assert metric.numeric_change is None
    assert metric.change_direction == "insufficient_evidence"
    assert metric.fluctuation_detected is None


def test_more_than_six_values_use_first_and_last_three_not_middle_values() -> None:
    observations = _six_trending_observations()
    middle = _observation(
        7,
        observed_at=_utc(3, 12),
        session_id="middle-outlier",
        words_correct=0,
        engagement_score=Decimal("0.0000"),
    )
    observations.append(middle)
    metric = _metrics(observations)["reading_accuracy"]
    assert metric.valid_observation_count == 7
    assert metric.early_window_mean == Decimal("0.7000")
    assert metric.late_window_mean == Decimal("0.9500")


def test_missing_metrics_have_independent_counts_and_reason_codes() -> None:
    observations = _six_trending_observations()
    observations[0] = _observation(
        1,
        words_attempted=0,
        words_correct=0,
        active_duration_ms=0,
        hesitation_count=None,
        engagement_score=None,
    )
    metrics = _metrics(observations)

    assert metrics["reading_accuracy"].missing_observation_count == 1
    assert metrics["reading_accuracy"].missing_observations[0].reason_code == (
        "zero_words_attempted"
    )
    assert metrics["reading_fluency_wpm"].missing_observations[0].reason_code == (
        "insufficient_active_duration"
    )
    assert metrics["hesitation_rate_per_word"].missing_observations[0].reason_code == (
        "hesitation_not_measured"
    )
    assert metrics["engagement_score"].missing_observations[0].reason_code == (
        "engagement_inputs_missing"
    )
    assert all(metric.evidence_sufficient is False for metric in metrics.values())


def test_zero_duration_session_can_contribute_other_valid_metrics() -> None:
    observation = _observation(
        1,
        words_attempted=10,
        words_correct=8,
        target_word_count=0,
        active_duration_ms=0,
        total_duration_ms=0,
        hesitation_count=2,
        total_pause_duration_ms=None,
        engagement_score=None,
    )
    metrics = _metrics([observation])
    assert metrics["reading_accuracy"].first_value == Decimal("0.8000")
    assert metrics["hesitation_rate_per_word"].first_value == Decimal("0.2000")
    assert metrics["reading_fluency_wpm"].first_value is None
    assert metrics["engagement_score"].first_value is None


def test_empty_analysis_window_has_empty_deterministic_report() -> None:
    report = calculate_longitudinal_progress(
        [_observation(1)],
        LongitudinalWindow(start_at_utc=_utc(10, 0), end_at_utc=_utc(11, 0)),
    )
    assert report.included_session_count == 0
    assert report.partitions == ()
    assert report.support_mode_exposures == ()
    assert report.difficulty_timeline == ()


def test_all_missing_metrics_are_never_coerced_to_zero() -> None:
    observations = [
        _observation(
            day,
            words_attempted=0,
            words_correct=0,
            target_word_count=0,
            active_duration_ms=0,
            total_duration_ms=0,
            hesitation_count=None,
            total_pause_duration_ms=None,
            engagement_score=None,
        )
        for day in range(1, 7)
    ]
    for metric in _metrics(observations).values():
        assert metric.valid_observation_count == 0
        assert metric.missing_observation_count == 6
        assert metric.first_value is None
        assert metric.latest_value is None
        assert metric.evidence_sufficient is False


def test_window_rejects_naive_timestamps_and_normalizes_aware_offsets() -> None:
    with pytest.raises(ValidationError):
        LongitudinalWindow(
            start_at_utc=datetime(2026, 1, 1),
            end_at_utc=datetime(2026, 1, 2),
        )

    local = timezone(timedelta(hours=5, minutes=30))
    window = LongitudinalWindow(
        start_at_utc=datetime(2026, 1, 1, 5, 30, tzinfo=local),
        end_at_utc=datetime(2026, 1, 2, 5, 30, tzinfo=local),
    )
    assert window.start_at_utc == datetime(2026, 1, 1, tzinfo=UTC)
    assert window.end_at_utc == datetime(2026, 1, 2, tzinfo=UTC)
    assert window.start_at_utc.tzinfo is UTC


def test_window_requires_positive_duration() -> None:
    with pytest.raises(ValidationError, match="earlier"):
        LongitudinalWindow(start_at_utc=_utc(2), end_at_utc=_utc(2))
    with pytest.raises(ValidationError, match="earlier"):
        LongitudinalWindow(start_at_utc=_utc(3), end_at_utc=_utc(2))


def test_half_open_window_includes_start_and_excludes_end() -> None:
    start = _utc(2, 0)
    end = _utc(3, 0)
    report = calculate_longitudinal_progress(
        [
            _observation(1, session_id="before", observed_at=start - timedelta(microseconds=1)),
            _observation(2, session_id="at-start", observed_at=start),
            _observation(2, session_id="inside", observed_at=end - timedelta(microseconds=1)),
            _observation(3, session_id="at-end", observed_at=end),
        ],
        LongitudinalWindow(start_at_utc=start, end_at_utc=end),
    )
    assert report.included_session_count == 2
    assert report.partitions[0].first_session_at == start
    assert report.partitions[0].latest_session_at == end - timedelta(microseconds=1)


def test_equal_timestamps_use_session_id_as_deterministic_tie_breaker() -> None:
    same_time = _utc(5)
    observations = [
        _observation(
            5,
            session_id=f"session-{letter}",
            observed_at=same_time,
            words_correct=value,
            engagement_score=Decimal("0.5000"),
        )
        for letter, value in zip("fedcba", [100, 90, 80, 70, 60, 50], strict=True)
    ]
    metric = _metrics(observations)["reading_accuracy"]
    assert metric.first_value == Decimal("0.5000")
    assert metric.latest_value == Decimal("1.0000")
    assert metric.change_direction == "increased"


def test_input_order_does_not_change_report() -> None:
    observations = _six_trending_observations()
    forward = calculate_longitudinal_progress(observations, _window())
    reverse = calculate_longitudinal_progress(list(reversed(observations)), _window())
    permuted = calculate_longitudinal_progress(
        [observations[index] for index in (2, 5, 0, 4, 1, 3)], _window()
    )
    assert forward == reverse == permuted


@pytest.mark.parametrize(
    ("values", "expected_direction"),
    [
        ([50, 55, 60, 80, 85, 90], "increased"),
        ([90, 85, 80, 60, 55, 50], "decreased"),
        ([75, 75, 75, 75, 75, 75], "no_observed_change"),
    ],
)
def test_increasing_decreasing_and_flat_directions(
    values: list[int], expected_direction: str
) -> None:
    observations = [
        _observation(day, words_correct=value, engagement_score=Decimal("0.5000"))
        for day, value in enumerate(values, start=1)
    ]
    metric = _metrics(observations)["reading_accuracy"]
    assert metric.change_direction == expected_direction


def test_fluctuating_series_is_reported_without_changing_numeric_direction() -> None:
    values = [50, 70, 60, 80, 70, 90]
    observations = [
        _observation(day, words_correct=value, engagement_score=Decimal("0.5000"))
        for day, value in enumerate(values, start=1)
    ]
    metric = _metrics(observations)["reading_accuracy"]
    assert metric.change_direction == "increased"
    assert metric.fluctuation_detected is True


def test_contradictory_metrics_remain_separate() -> None:
    observations = [
        _observation(
            day,
            words_correct=50 + day * 5,
            active_duration_ms=30000 + day * 10000,
            total_duration_ms=40000 + day * 10000,
            engagement_score=Decimal("0.5000"),
        )
        for day in range(1, 7)
    ]
    metrics = _metrics(observations)
    assert metrics["reading_accuracy"].change_direction == "increased"
    assert metrics["reading_fluency_wpm"].change_direction == "decreased"
    assert "caus" not in metrics["reading_accuracy"].educational_interpretation.lower()


def test_context_partitions_are_isolated() -> None:
    adaptive = _six_trending_observations()
    fixed = [
        _observation(
            day + 7,
            task_type="assisted_read_aloud",
            difficulty_tier="early",
            support_mode="baseline_fixed",
            engagement_score=Decimal("0.5000"),
        )
        for day in range(1, 7)
    ]
    report = calculate_longitudinal_progress(adaptive + fixed, _window(end_day=20))
    assert len(report.partitions) == 2
    keys = {partition.key for partition in report.partitions}
    assert {(key.task_type, key.difficulty_tier, key.support_mode) for key in keys} == {
        ("independent_reading", "intermediate", "adaptive"),
        ("assisted_read_aloud", "early", "baseline_fixed"),
    }
    assert all(partition.session_count == 6 for partition in report.partitions)


def test_support_mode_exposure_is_descriptive_and_sums_durations() -> None:
    observations = [
        _observation(
            1,
            active_duration_ms=1000,
            total_duration_ms=2000,
            total_pause_duration_ms=500,
        ),
        _observation(
            2,
            active_duration_ms=2000,
            total_duration_ms=3000,
            total_pause_duration_ms=500,
        ),
        _observation(
            3,
            active_duration_ms=3000,
            total_duration_ms=4000,
            total_pause_duration_ms=500,
            support_mode="manual_override",
        ),
    ]
    report = calculate_longitudinal_progress(observations, _window())
    exposures = {item.support_mode: item for item in report.support_mode_exposures}
    assert exposures["adaptive"].session_count == 2
    assert exposures["adaptive"].active_duration_ms == 3000
    assert exposures["adaptive"].total_duration_ms == 5000
    assert exposures["manual_override"].session_count == 1
    assert any("randomized" in limitation for limitation in report.limitations)


def test_difficulty_timeline_emits_initial_tier_and_changes_per_context() -> None:
    tiers = ["early", "early", "intermediate", "intermediate", "advanced", "early"]
    observations = [
        _observation(
            day,
            difficulty_tier=tier,
            engagement_score=Decimal("0.5000"),
        )
        for day, tier in enumerate(tiers, start=1)
    ]
    timeline = calculate_longitudinal_progress(observations, _window()).difficulty_timeline
    assert [item.difficulty_tier for item in timeline] == [
        "early",
        "intermediate",
        "advanced",
        "early",
    ]
    assert [item.previous_difficulty_tier for item in timeline] == [
        None,
        "early",
        "intermediate",
        "advanced",
    ]
    assert all(item.task_type == "independent_reading" for item in timeline)
    assert all(item.support_mode == "adaptive" for item in timeline)


def test_mixed_engagement_versions_are_descriptive_but_non_comparable() -> None:
    observations = [
        _observation(
            day,
            engagement_score=Decimal(f"0.{day}000"),
            engagement_version="engagement-v1" if day <= 3 else "engagement-v2",
        )
        for day in range(1, 7)
    ]
    metric = _metrics(observations)["engagement_score"]
    assert metric.valid_observation_count == 6
    assert metric.first_value == Decimal("0.1000")
    assert metric.latest_value == Decimal("0.6000")
    assert metric.observed_metric_versions == ("engagement-v1", "engagement-v2")
    assert metric.metric_calculation_version is None
    assert metric.comparison_blocker == "mixed_metric_versions"
    assert metric.evidence_sufficient is False
    assert metric.numeric_change is None
    assert "cannot be compared" in metric.educational_interpretation


def test_wpm_ceiling_marks_filtered_value_missing_and_blocks_sufficiency() -> None:
    observations = _six_trending_observations()
    observations[0] = _observation(
        1,
        words_attempted=200,
        words_correct=190,
        active_duration_ms=2000,
        total_duration_ms=3000,
        total_pause_duration_ms=1000,
        engagement_score=Decimal("0.5000"),
    )
    report = calculate_longitudinal_progress(observations, _window(), max_wpm=600)
    metric = {item.metric_name: item for item in report.partitions[0].metrics}[
        "reading_fluency_wpm"
    ]
    assert metric.valid_observation_count == 5
    assert metric.missing_observations[0].reason_code == "wpm_above_configured_ceiling"
    assert metric.evidence_sufficient is False
    with pytest.raises(ValueError, match="max_wpm"):
        calculate_longitudinal_progress(observations, _window(), max_wpm=-1)


def test_invalid_missing_and_duplicate_session_identifiers_are_rejected() -> None:
    telemetry = SessionTelemetry(
        session_start_time=_utc(1),
        session_id=None,
        words_attempted=10,
        words_correct=8,
        target_word_count=10,
        active_duration_ms=1000,
        total_duration_ms=2000,
    )
    with pytest.raises(ValueError, match="session_id"):
        LongitudinalObservation.from_telemetry(telemetry)
    with pytest.raises(ValueError, match="session_id"):
        _observation(1, session_id=" ")

    duplicate = _observation(1, session_id="duplicate")
    with pytest.raises(ValueError, match="unique"):
        calculate_longitudinal_progress([duplicate, duplicate], _window())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_type", "quiz"),
        ("difficulty_tier", "expert"),
        ("support_mode", "automatic"),
    ],
)
def test_invalid_context_categories_are_rejected(field: str, value: str) -> None:
    kwargs: dict[str, Any] = {field: value}
    with pytest.raises(ValueError, match=field):
        _observation(1, **kwargs)


def test_engagement_score_requires_valid_decimal_and_version() -> None:
    with pytest.raises(ValueError, match="formula version"):
        _observation(1, engagement_score=Decimal("0.5"), engagement_version=None)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        _observation(1, engagement_score=Decimal("1.1"))


def test_results_and_inputs_are_immutable() -> None:
    observation = _observation(1)
    report = calculate_longitudinal_progress([observation], _window())
    with pytest.raises(FrozenInstanceError):
        observation.engagement_score = Decimal("0.2")  # type: ignore[misc]
    with pytest.raises(ValidationError):
        report.included_session_count = 99  # type: ignore[misc]


def test_output_contract_rejects_non_finite_decimals_and_unknown_fields() -> None:
    metric = _metrics(_six_trending_observations())["reading_accuracy"]
    values = metric.model_dump(mode="python")
    values["first_value"] = Decimal("NaN")
    with pytest.raises(ValidationError):
        MetricTrend.model_validate(values)

    values = metric.model_dump(mode="python")
    values["learner_name"] = "Synthetic learner"
    with pytest.raises(ValidationError):
        MetricTrend.model_validate(values)


def test_interpretations_are_deterministic_bounded_and_non_clinical() -> None:
    first = calculate_longitudinal_progress(_six_trending_observations(), _window())
    second = calculate_longitudinal_progress(_six_trending_observations(), _window())
    assert first == second
    texts = [
        metric.educational_interpretation
        for partition in first.partitions
        for metric in partition.metrics
    ]
    assert all(len(text) <= 500 for text in texts)
    assert any("Measured reading accuracy increased" in text for text in texts)
    combined = " ".join(texts + [first.disclaimer]).lower()
    assert "severity" in first.disclaimer.lower()
    assert "treatment advice" in first.disclaimer.lower()
    assert "dyslexia" not in combined
    assert "diagnosis" in NON_CLINICAL_LONGITUDINAL_DISCLAIMER.lower()
    engagement = _metrics(_six_trending_observations())["engagement_score"]
    assert engagement.metric_disclaimer is not None
    assert "research heuristic" in engagement.metric_disclaimer


def test_report_has_no_learner_identity_or_sensitive_content_fields() -> None:
    field_names = set(longitudinal_module.LongitudinalProgressReport.model_fields)
    serialized = calculate_longitudinal_progress(
        _six_trending_observations(), _window()
    ).model_dump_json()
    assert (
        not {
            "learner_id",
            "learner_name",
            "raw_audio",
            "document_text",
            "diagnosis",
            "research_assignment",
        }
        & field_names
    )
    for forbidden in ("learner_id", "learner_name", "raw_audio", "document_text"):
        assert forbidden not in serialized


def test_module_has_no_database_http_auth_consent_or_network_imports() -> None:
    tree = ast.parse(inspect.getsource(longitudinal_module))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    forbidden_roots = {
        "sqlalchemy",
        "psycopg",
        "fastapi",
        "httpx",
        "requests",
        "socket",
    }
    assert {name.split(".")[0] for name in imported_modules}.isdisjoint(forbidden_roots)
    assert not any("modules.auth" in name or "consent" in name for name in imported_modules)
