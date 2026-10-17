"""Synthetic tests for privacy-aware educational dashboard projections."""

from __future__ import annotations

import ast
import inspect
import json
import re
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

import app.modules.learner_modelling.dashboard_projections as projection_module
from app.modules.learner_modelling.analytics import (
    DifficultyTier,
    SessionTelemetry,
    SupportMode,
    TaskType,
)
from app.modules.learner_modelling.dashboard_projections import (
    DashboardWindow,
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    LearnerProgressProjection,
    project_educator_analytics,
    project_guardian_summary,
    project_learner_progress,
)
from app.modules.learner_modelling.longitudinal import (
    HESITATION_CALCULATION_VERSION,
    LONGITUDINAL_CALCULATION_VERSION,
    READING_ACCURACY_CALCULATION_VERSION,
    WPM_CALCULATION_VERSION,
    LongitudinalObservation,
    LongitudinalProgressReport,
    LongitudinalWindow,
    calculate_longitudinal_progress,
)


def _utc(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


def _observation(
    day: int,
    *,
    session_id: str | None = None,
    words_attempted: int = 100,
    words_correct: int = 80,
    active_duration_ms: int = 60000,
    hesitation_count: int | None = 8,
    task_type: TaskType = "independent_reading",
    difficulty_tier: DifficultyTier = "intermediate",
    support_mode: SupportMode = "adaptive",
) -> LongitudinalObservation:
    telemetry = SessionTelemetry(
        session_start_time=_utc(day),
        session_id=session_id or f"synthetic-session-{day}",
        words_attempted=words_attempted,
        words_correct=words_correct,
        target_word_count=100,
        active_duration_ms=active_duration_ms,
        total_duration_ms=max(active_duration_ms, 1) + 10000,
        hesitation_count=hesitation_count,
        total_pause_duration_ms=10000,
        task_type=task_type,
        difficulty_tier=difficulty_tier,
        support_mode=support_mode,
    )
    return LongitudinalObservation.from_telemetry(telemetry)


def _window() -> LongitudinalWindow:
    return LongitudinalWindow(start_at_utc=_utc(1, 0), end_at_utc=_utc(31, 0))


def _report(
    observations: list[LongitudinalObservation] | None = None,
) -> LongitudinalProgressReport:
    return calculate_longitudinal_progress(observations or [], _window())


def _trending_observations() -> list[LongitudinalObservation]:
    correct = [60, 70, 80, 90, 95, 100]
    hesitations = [12, 10, 8, 6, 4, 2]
    return [
        _observation(
            index,
            words_correct=correct[index - 1],
            hesitation_count=hesitations[index - 1],
        )
        for index in range(1, 7)
    ]


def _project_all(
    report: LongitudinalProgressReport,
) -> tuple[LearnerProgressProjection, GuardianSummaryProjection, EducatorAnalyticsProjection]:
    return (
        project_learner_progress(report),
        project_guardian_summary(report),
        project_educator_analytics(report),
    )


def _json_text(model: object) -> str:
    assert hasattr(model, "model_dump")
    payload = model.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True)


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        return keys | set().union(*(_all_keys(item) for item in value.values()), set())
    if isinstance(value, (list, tuple)):
        return set().union(*(_all_keys(item) for item in value), set())
    return set()


def test_projection_contracts_are_separate_and_frozen() -> None:
    report = _report(_trending_observations())
    learner, guardian, educator = _project_all(report)

    assert isinstance(learner, LearnerProgressProjection)
    assert isinstance(guardian, GuardianSummaryProjection)
    assert isinstance(educator, EducatorAnalyticsProjection)
    assert not issubclass(LearnerProgressProjection, EducatorAnalyticsProjection)
    assert not issubclass(GuardianSummaryProjection, EducatorAnalyticsProjection)

    with pytest.raises(ValidationError, match="frozen"):
        learner.reporting_period.start_at_utc = _utc(2)  # type: ignore[misc]


def test_exact_learner_serialized_allowlists() -> None:
    learner = project_learner_progress(_report(_trending_observations()))
    payload = learner.model_dump(mode="json")

    assert set(payload) == {
        "reporting_period",
        "included_session_count",
        "contexts",
        "support_observations",
        "difficulty_observations",
        "evidence_message",
        "disclaimer",
    }
    assert set(payload["reporting_period"]) == {"start_at_utc", "end_at_utc"}
    assert set(payload["contexts"][0]) == {
        "task_label",
        "difficulty_label",
        "support_label",
        "metrics",
    }
    assert set(payload["contexts"][0]["metrics"][0]) == {
        "metric_name",
        "display_label",
        "unit",
        "first_value",
        "latest_value",
        "change_direction",
        "evidence_state",
        "explanation",
    }


def test_exact_guardian_serialized_allowlists() -> None:
    guardian = project_guardian_summary(_report(_trending_observations()))
    payload = guardian.model_dump(mode="json")

    assert set(payload) == {
        "reporting_period",
        "included_session_count",
        "contexts",
        "support_exposures",
        "difficulty_history",
        "evidence_limitations",
        "disclaimer",
    }
    assert set(payload["contexts"][0]) == {
        "task_type",
        "task_label",
        "difficulty_tier",
        "difficulty_label",
        "support_mode",
        "support_label",
        "session_count",
        "first_session_at",
        "latest_session_at",
        "metrics",
    }
    assert set(payload["contexts"][0]["metrics"][0]) == {
        "metric_name",
        "display_label",
        "unit",
        "valid_observation_count",
        "missing_observation_count",
        "first_value",
        "latest_value",
        "change_direction",
        "evidence_sufficient",
        "fluctuation_detected",
        "explanation",
    }


def test_exact_educator_serialized_allowlists() -> None:
    educator = project_educator_analytics(_report(_trending_observations()))
    payload = educator.model_dump(mode="json")

    assert set(payload) == {
        "reporting_period",
        "included_session_count",
        "partitions",
        "support_mode_exposures",
        "difficulty_timeline",
        "longitudinal_calculation_version",
        "limitations",
        "disclaimer",
    }
    assert set(payload["partitions"][0]) == {
        "task_type",
        "difficulty_tier",
        "support_mode",
        "window",
        "session_count",
        "first_session_at",
        "latest_session_at",
        "metrics",
    }
    assert set(payload["partitions"][0]["metrics"][0]) == {
        "metric_name",
        "unit",
        "total_relevant_sessions",
        "valid_observation_count",
        "missing_observation_count",
        "missing_observations",
        "first_value",
        "first_observed_at",
        "latest_value",
        "latest_observed_at",
        "early_window_count",
        "early_window_mean",
        "late_window_count",
        "late_window_mean",
        "numeric_change",
        "change_direction",
        "evidence_sufficient",
        "fluctuation_detected",
        "metric_calculation_version",
        "observed_metric_versions",
        "longitudinal_calculation_version",
        "comparison_blocker",
        "educational_interpretation",
    }


def test_educator_only_evidence_is_absent_from_smaller_projections() -> None:
    observations = _trending_observations()
    observations[0] = _observation(
        1,
        words_attempted=0,
        words_correct=0,
        active_duration_ms=0,
        hesitation_count=None,
    )
    learner, guardian, educator = _project_all(_report(observations))
    restricted_fields = {
        "early_window_mean",
        "late_window_mean",
        "numeric_change",
        "metric_calculation_version",
        "observed_metric_versions",
        "longitudinal_calculation_version",
        "comparison_blocker",
        "missing_observations",
        "reason_code",
    }

    assert _all_keys(learner.model_dump()) & restricted_fields == set()
    assert _all_keys(guardian.model_dump()) & restricted_fields == set()
    assert restricted_fields <= _all_keys(educator.model_dump())


def test_empty_report_produces_empty_role_outputs() -> None:
    learner, guardian, educator = _project_all(_report())

    assert learner.included_session_count == 0
    assert learner.contexts == ()
    assert learner.support_observations == ()
    assert learner.difficulty_observations == ()
    assert "No measured observations" in learner.evidence_message
    assert guardian.contexts == ()
    assert guardian.support_exposures == ()
    assert guardian.difficulty_history == ()
    assert educator.partitions == ()
    assert educator.support_mode_exposures == ()
    assert educator.difficulty_timeline == ()


def test_insufficient_evidence_preserves_values_without_inventing_change() -> None:
    learner, guardian, educator = _project_all(_report(_trending_observations()[:5]))

    learner_metric = learner.contexts[0].metrics[0]
    guardian_metric = guardian.contexts[0].metrics[0]
    educator_metric = educator.partitions[0].metrics[0]
    assert learner_metric.first_value == Decimal("0.6000")
    assert learner_metric.latest_value == Decimal("0.9500")
    assert learner_metric.change_direction == "insufficient_evidence"
    assert learner_metric.evidence_state == "limited"
    assert guardian_metric.evidence_sufficient is False
    assert educator_metric.numeric_change is None
    assert educator_metric.early_window_mean is None
    assert educator_metric.late_window_mean is None


def test_missing_values_are_not_replaced_with_zero() -> None:
    observations = _trending_observations()
    observations[0] = _observation(
        1,
        words_attempted=0,
        words_correct=0,
        active_duration_ms=0,
        hesitation_count=None,
    )
    learner, guardian, educator = _project_all(_report(observations))

    assert all(metric.evidence_state == "limited" for metric in learner.contexts[0].metrics)
    assert all(metric.missing_observation_count == 1 for metric in guardian.contexts[0].metrics)
    reasons = {
        missing.reason_code
        for metric in educator.partitions[0].metrics
        for missing in metric.missing_observations
    }
    assert reasons == {
        "zero_words_attempted",
        "insufficient_active_duration",
        "hesitation_not_measured",
    }
    assert "zero_words_attempted" not in _json_text(learner)
    assert "zero_words_attempted" not in _json_text(guardian)


def test_metric_labels_units_and_all_directions_are_preserved() -> None:
    learner, guardian, educator = _project_all(_report(_trending_observations()))
    learner_metrics = learner.contexts[0].metrics

    assert tuple((item.display_label, item.unit) for item in learner_metrics) == (
        ("Reading accuracy", "proportion"),
        ("Reading speed", "words_per_minute"),
        ("Hesitation rate", "hesitations_per_attempted_word"),
    )
    assert {item.change_direction for item in learner_metrics} == {
        "increased",
        "decreased",
        "no_observed_change",
    }
    assert tuple(item.unit for item in guardian.contexts[0].metrics) == tuple(
        item.unit for item in learner_metrics
    )
    assert tuple(item.unit for item in educator.partitions[0].metrics) == tuple(
        item.unit for item in learner_metrics
    )
    limited = project_learner_progress(_report(_trending_observations()[:1]))
    assert {item.change_direction for item in limited.contexts[0].metrics} == {
        "insufficient_evidence"
    }


@pytest.mark.parametrize(
    ("task_type", "difficulty_tier", "support_mode"),
    [
        ("independent_reading", "early", "baseline_fixed"),
        ("assisted_read_aloud", "intermediate", "adaptive"),
        ("guided_echo_reading", "advanced", "manual_override"),
    ],
)
def test_every_context_enum_has_a_readable_projection(
    task_type: TaskType,
    difficulty_tier: DifficultyTier,
    support_mode: SupportMode,
) -> None:
    report = _report(
        [
            _observation(
                1,
                task_type=task_type,
                difficulty_tier=difficulty_tier,
                support_mode=support_mode,
            )
        ]
    )
    learner, guardian, educator = _project_all(report)

    assert learner.contexts[0].task_label
    assert learner.contexts[0].difficulty_label
    assert learner.contexts[0].support_label
    assert guardian.contexts[0].task_type == task_type
    assert guardian.contexts[0].difficulty_tier == difficulty_tier
    assert guardian.contexts[0].support_mode == support_mode
    assert educator.partitions[0].task_type == task_type
    assert educator.partitions[0].difficulty_tier == difficulty_tier
    assert educator.partitions[0].support_mode == support_mode


def test_reporting_period_and_nested_timestamps_are_utc() -> None:
    offset = timezone(timedelta(hours=5, minutes=30))
    window = LongitudinalWindow(
        start_at_utc=datetime(2026, 1, 1, 5, 30, tzinfo=offset),
        end_at_utc=datetime(2026, 2, 1, 5, 30, tzinfo=offset),
    )
    report = calculate_longitudinal_progress([_observation(2)], window)

    for projection in _project_all(report):
        assert projection.reporting_period.start_at_utc.tzinfo is UTC
        assert projection.reporting_period.end_at_utc.tzinfo is UTC


def test_input_order_and_repeated_projection_are_deterministic() -> None:
    observations = _trending_observations()
    forward = _report(observations)
    reverse = _report(list(reversed(observations)))

    for projector in (
        project_learner_progress,
        project_guardian_summary,
        project_educator_analytics,
    ):
        first = projector(forward)
        assert first == projector(forward)
        assert first == projector(reverse)


def test_projectors_do_not_mutate_the_source_report() -> None:
    report = _report(_trending_observations())
    before = report.model_dump(mode="json")

    _project_all(report)

    assert report.model_dump(mode="json") == before


def test_strict_extra_fields_and_coercion_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DashboardWindow.model_validate(
            {
                "start_at_utc": _utc(1),
                "end_at_utc": _utc(2),
                "learner_id": "not-allowed",
            }
        )
    with pytest.raises(ValidationError):
        DashboardWindow.model_validate(
            {
                "start_at_utc": _utc(1).isoformat(),
                "end_at_utc": _utc(2).isoformat(),
            }
        )


def test_no_identity_session_consent_or_authorization_data_is_disclosed() -> None:
    session_uuid = "123e4567-e89b-12d3-a456-426614174000"
    report = _report([_observation(1, session_id=session_uuid)])
    forbidden_keys = {
        "learner_id",
        "learner_name",
        "session_id",
        "client_session_id",
        "principal",
        "authorization",
        "consent",
        "jwt",
        "audio",
        "document_text",
    }

    for projection in _project_all(report):
        payload = projection.model_dump(mode="json")
        assert _all_keys(payload) & forbidden_keys == set()
        assert session_uuid not in json.dumps(payload)
        assert not re.search(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            json.dumps(payload).lower(),
        )


def test_experimental_engagement_is_absent_from_all_initial_outputs() -> None:
    report = _report(_trending_observations())

    for projection in _project_all(report):
        assert "engagement" not in _json_text(projection).lower()


def test_educator_preserves_approved_formula_versions_and_values() -> None:
    report = _report(_trending_observations())
    educator = project_educator_analytics(report)
    metrics = {item.metric_name: item for item in educator.partitions[0].metrics}

    assert metrics["reading_accuracy"].metric_calculation_version == (
        READING_ACCURACY_CALCULATION_VERSION
    )
    assert metrics["reading_fluency_wpm"].metric_calculation_version == (WPM_CALCULATION_VERSION)
    assert metrics["hesitation_rate_per_word"].metric_calculation_version == (
        HESITATION_CALCULATION_VERSION
    )
    assert all(
        item.longitudinal_calculation_version == LONGITUDINAL_CALCULATION_VERSION
        for item in metrics.values()
    )
    upstream = {
        item.metric_name: item
        for item in report.partitions[0].metrics
        if item.metric_name != "engagement_score"
    }
    for name, metric in metrics.items():
        assert metric.first_value == upstream[name].first_value
        assert metric.latest_value == upstream[name].latest_value
        assert metric.early_window_mean == upstream[name].early_window_mean
        assert metric.late_window_mean == upstream[name].late_window_mean
        assert metric.numeric_change == upstream[name].numeric_change


def test_fluctuation_is_disclosed_without_a_steady_progress_claim() -> None:
    values = [60, 90, 70, 95, 80, 100]
    report = _report(
        [_observation(day, words_correct=value) for day, value in enumerate(values, start=1)]
    )
    learner = project_learner_progress(report)
    accuracy = learner.contexts[0].metrics[0]

    assert "varied" in accuracy.explanation
    assert "steady progress" not in accuracy.explanation.lower()


def test_support_and_difficulty_descriptions_are_observational() -> None:
    report = _report(
        [
            _observation(1, difficulty_tier="early", support_mode="baseline_fixed"),
            _observation(2, difficulty_tier="intermediate", support_mode="adaptive"),
            _observation(3, difficulty_tier="advanced", support_mode="manual_override"),
        ]
    )
    learner = project_learner_progress(report)
    text = _json_text(learner).lower()

    assert "sessions were recorded using" in text
    assert "sessions were observed" in text
    for unsupported in (
        "caused progress",
        "proves improvement",
        "randomized intervention",
        "achievement",
    ):
        assert unsupported not in text


def test_outputs_contain_no_diagnostic_or_treatment_claims() -> None:
    report = _report(_trending_observations())
    forbidden = ("diagnos", "dyslexia", "severity", "treatment", "clinical prediction")

    for projection in _project_all(report):
        text = _json_text(projection).lower()
        assert all(term not in text for term in forbidden)


def test_module_has_no_database_network_http_or_adaptation_dependency() -> None:
    source = inspect.getsource(projection_module)
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    forbidden_prefixes = (
        "fastapi",
        "sqlalchemy",
        "requests",
        "httpx",
        "socket",
        "urllib",
        "app.db",
        "app.modules.auth",
        "app.modules.learners",
        "app.modules.learner_modelling.adaptation",
        "app.modules.learner_modelling.repository",
        "app.modules.learner_modelling.service",
    )

    assert not any(name.startswith(forbidden_prefixes) for name in imports)
    assert "safe_to_apply_automatically" not in source
    assert "AdaptationDecision" not in source


def test_projectors_accept_only_a_longitudinal_report() -> None:
    for projector in (
        project_learner_progress,
        project_guardian_summary,
        project_educator_analytics,
    ):
        signature = inspect.signature(projector)
        assert tuple(signature.parameters) == ("report",)
        assert signature.parameters["report"].annotation == "LongitudinalProgressReport"


def test_projection_source_is_limited_to_the_two_approved_files() -> None:
    path = Path(projection_module.__file__).resolve()

    assert path.name == "dashboard_projections.py"
    assert Path(__file__).name == "test_learner_dashboard_projections.py"
