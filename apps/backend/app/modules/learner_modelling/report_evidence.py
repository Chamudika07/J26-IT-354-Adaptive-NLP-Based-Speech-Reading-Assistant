"""Pure role-specific factual report construction, with no retrieval or persistence.

Inputs must come from the existing authorized projection pipeline. Type validation
is not authentication, learner authorization, consent, or third-party processing
approval. The original projection remains authoritative; provider input contains
only closed, deterministic statements from numeric values and approved categories.
Free-text explanations, version labels and descriptions never enter provider input.
Recommendations are intentionally absent: no approved authorized recommendation
projection is accepted by this foundation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from pydantic import ValidationError

from app.modules.learner_modelling.dashboard_projections import (
    DisplayTrend,
    EducatorAnalyticsProjection,
    EducatorContextTrend,
    EducatorMetricTrend,
    GuardianContextSummary,
    GuardianMetricTrend,
    GuardianSummaryProjection,
    LearnerProgressProjection,
)
from app.modules.learner_modelling.report_contracts import (
    NarrativeRequest,
    ReferencedStatement,
    ReportRole,
)

Projection = LearnerProgressProjection | GuardianSummaryProjection | EducatorAnalyticsProjection
MetricProjection = DisplayTrend | GuardianMetricTrend | EducatorMetricTrend

_UNITS = {
    "reading_accuracy": "proportion",
    "reading_fluency_wpm": "words_per_minute",
    "hesitation_rate_per_word": "hesitations_per_attempted_word",
}
_TASKS = {
    "independent_reading": "Independent reading",
    "assisted_read_aloud": "Assisted read-aloud",
    "guided_echo_reading": "Guided echo reading",
}
_DIFFICULTY = {
    "early": "Early level",
    "intermediate": "Intermediate level",
    "advanced": "Advanced level",
}
_SUPPORT = {
    "baseline_fixed": "Fixed support",
    "adaptive": "Adaptive support",
    "manual_override": "Manually selected support",
}
_DIRECTIONS = {
    "increased": "increased",
    "decreased": "decreased",
    "no_observed_change": "showed no observed change",
}


class ReportEvidenceError(ValueError):
    def __init__(self) -> None:
        super().__init__("The supplied report evidence is invalid or unsupported.")


@dataclass(frozen=True, slots=True)
class StructuredEvidenceReport:
    """Authoritative facts stay separate from candidate narrative statements."""

    role: ReportRole
    projection: Projection
    narrative_request: NarrativeRequest
    recommendation_status: str = "No authorized recommendation projection supplied."
    advisory_only: bool = True


def _number(value: Decimal | None) -> str:
    return "unavailable" if value is None else str(value)


def _metric_statements(metric: MetricProjection, context: int) -> list[str]:
    if metric.unit != _UNITS[metric.metric_name]:
        raise ReportEvidenceError()
    sufficient = (
        metric.evidence_state == "sufficient"
        if isinstance(metric, DisplayTrend)
        else metric.evidence_sufficient
    )
    if sufficient == (metric.change_direction == "insufficient_evidence"):
        raise ReportEvidenceError()
    if (metric.first_value is None) != (metric.latest_value is None):
        raise ReportEvidenceError()
    if isinstance(metric, DisplayTrend) and (
        (metric.evidence_state == "no_observations") != (metric.first_value is None)
    ):
        raise ReportEvidenceError()
    if sufficient and metric.first_value is None:
        raise ReportEvidenceError()
    if metric.metric_name == "reading_accuracy" and any(
        value is not None and value > 1 for value in (metric.first_value, metric.latest_value)
    ):
        raise ReportEvidenceError()
    prefix = f"Context {context}, {metric.metric_name}"
    statements = [
        f"{prefix}: first {_number(metric.first_value)}, latest {_number(metric.latest_value)}; "
        f"unit {metric.unit}.",
        (
            f"{prefix}: insufficient comparable evidence for a trend."
            if not sufficient
            else f"{prefix}: measurements {_DIRECTIONS[metric.change_direction]} "
            "in comparable observations; this does not establish improvement in ability."
        ),
    ]
    if isinstance(metric, (GuardianMetricTrend, EducatorMetricTrend)):
        if sufficient and metric.valid_observation_count < 6:
            raise ReportEvidenceError()
        if (metric.valid_observation_count == 0) != (metric.first_value is None):
            raise ReportEvidenceError()
        statements.append(
            f"{prefix}: {metric.valid_observation_count} valid observations and "
            f"{metric.missing_observation_count} missing measurements. Missing values are not zero."
        )
        if metric.fluctuation_detected:
            statements.append(f"{prefix}: measurements varied during the reporting period.")
    if isinstance(metric, EducatorMetricTrend):
        if metric.valid_observation_count + metric.missing_observation_count != (
            metric.total_relevant_sessions
        ):
            raise ReportEvidenceError()
        if (
            sum(item.count for item in metric.missing_observations)
            != metric.missing_observation_count
        ):
            raise ReportEvidenceError()
        if sufficient:
            if (
                metric.early_window_count != 3
                or metric.late_window_count != 3
                or metric.early_window_mean is None
                or metric.late_window_mean is None
                or metric.numeric_change is None
                or metric.comparison_blocker is not None
            ):
                raise ReportEvidenceError()
            delta = metric.late_window_mean - metric.early_window_mean
            if delta != metric.numeric_change or (
                (delta > 0 and metric.change_direction != "increased")
                or (delta < 0 and metric.change_direction != "decreased")
                or (delta == 0 and metric.change_direction != "no_observed_change")
            ):
                raise ReportEvidenceError()
            statements.append(
                f"{prefix}: early-window mean {metric.early_window_mean}, late-window mean "
                f"{metric.late_window_mean}; each window contains 3 comparable observations."
            )
        elif (
            metric.early_window_count != 0
            or metric.late_window_count != 0
            or metric.early_window_mean is not None
            or metric.late_window_mean is not None
            or metric.numeric_change is not None
        ):
            raise ReportEvidenceError()
        else:
            statements.append(f"{prefix}: no comparison-window averages are available.")
        if metric.comparison_blocker == "mixed_metric_versions":
            statements.append(f"{prefix}: mixed metric versions prevent a comparable trend.")
    return statements


def build_structured_report(projection: Projection) -> StructuredEvidenceReport:
    """Accept only the three exact projection types and revalidate copied/constructed inputs."""
    if type(projection) not in (
        LearnerProgressProjection,
        GuardianSummaryProjection,
        EducatorAnalyticsProjection,
    ):
        raise ReportEvidenceError()
    try:
        validated = type(projection).model_validate(
            projection.model_dump(mode="python", warnings=False)
        )
        return _build_validated_report(validated)
    except (ValidationError, ValueError, TypeError, KeyError, ArithmeticError):
        raise ReportEvidenceError() from None


def _build_validated_report(projection: Projection) -> StructuredEvidenceReport:
    window = projection.reporting_period
    if window.start_at_utc >= window.end_at_utc:
        raise ReportEvidenceError()
    text = [
        f"Reporting period [{window.start_at_utc.isoformat()}, "
        f"{window.end_at_utc.isoformat()}); UTC.",
        f"The reporting period contains {projection.included_session_count} recorded sessions.",
        "Descriptive educational observations only. "
        "They do not establish causes or assess health or ability.",
        "Evidence is limited to the supplied role projection; unavailable fields are not inferred.",
        "Advisory only. This report never changes support, difficulty or learner settings.",
    ]
    if isinstance(projection, LearnerProgressProjection):
        role: ReportRole = "learner"
        for index, learner_context in enumerate(projection.contexts, start=1):
            if (
                learner_context.task_label not in _TASKS.values()
                or learner_context.difficulty_label not in _DIFFICULTY.values()
                or learner_context.support_label not in _SUPPORT.values()
            ):
                raise ReportEvidenceError()
            text.append(
                f"Context {index}: {learner_context.task_label}; observed "
                f"{learner_context.difficulty_label}; {learner_context.support_label}."
            )
            if {metric.metric_name for metric in learner_context.metrics} != set(_UNITS):
                raise ReportEvidenceError()
            for learner_metric in learner_context.metrics:
                text.extend(_metric_statements(learner_metric, index))
        for observed in projection.difficulty_observations:
            if observed.difficulty_label not in _DIFFICULTY.values():
                raise ReportEvidenceError()
        levels = tuple(
            dict.fromkeys(item.difficulty_label for item in projection.difficulty_observations)
        )
        if levels:
            text.append(
                "Observed difficulty labels: "
                + ", ".join(levels)
                + ". No unlocked levels are inferred."
            )
        for support in projection.support_observations:
            if support.support_label not in _SUPPORT.values():
                raise ReportEvidenceError()
            text.append(
                f"Observed {support.support_label}: {support.session_count} recorded sessions."
            )
    else:
        role = "guardian" if isinstance(projection, GuardianSummaryProjection) else "educator"
        contexts: tuple[GuardianContextSummary | EducatorContextTrend, ...] = (
            projection.contexts
            if isinstance(projection, GuardianSummaryProjection)
            else projection.partitions
        )
        if sum(context.session_count for context in contexts) != projection.included_session_count:
            raise ReportEvidenceError()
        for index, context in enumerate(contexts, start=1):
            text.append(
                f"Context {index}: {_TASKS[context.task_type]}; observed "
                f"{_DIFFICULTY[context.difficulty_tier]}; {_SUPPORT[context.support_mode]}."
            )
            if {metric.metric_name for metric in context.metrics} != set(_UNITS):
                raise ReportEvidenceError()
            for metric in context.metrics:
                if (
                    metric.valid_observation_count + metric.missing_observation_count
                    != context.session_count
                ):
                    raise ReportEvidenceError()
                text.extend(_metric_statements(metric, index))
        history = (
            projection.difficulty_history
            if isinstance(projection, GuardianSummaryProjection)
            else projection.difficulty_timeline
        )
        tiers = tuple(dict.fromkeys(item.difficulty_tier for item in history))
        if tiers:
            text.append(
                "Observed difficulty labels: "
                + ", ".join(_DIFFICULTY[tier] for tier in tiers)
                + ". No unlocked levels are inferred."
            )
        exposures = (
            projection.support_exposures
            if isinstance(projection, GuardianSummaryProjection)
            else projection.support_mode_exposures
        )
        for exposure in exposures:
            text.append(
                f"Observed {_SUPPORT[exposure.support_mode]}: "
                f"{exposure.session_count} recorded sessions."
            )
    # Deduplication keeps shared limitations visible without repeating identical text.
    statements = tuple(
        ReferencedStatement(evidence_ref=f"e{index:04d}", text=value)
        for index, value in enumerate(dict.fromkeys(text), start=1)
    )
    serialized = json.dumps(
        {"role": role, "statements": [item.model_dump() for item in statements]},
        sort_keys=True,
        separators=(",", ":"),
    )
    request = NarrativeRequest(
        schema_version="report-narrative-v1",
        role=role,
        report_fingerprint=hashlib.sha256(serialized.encode()).hexdigest(),
        approved_statements=statements,
    )
    return StructuredEvidenceReport(role=role, projection=projection, narrative_request=request)
