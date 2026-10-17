"""Pure, privacy-minimized projections of longitudinal educational observations.

Callers must authorize the learner-scoped read, evaluate applicable consent, and
retrieve only authorized records before building a longitudinal report.  These
projectors are presentation transformations; they are not authorization or consent
boundaries and deliberately carry no learner identity.

Experimental engagement is excluded from every initial projection.  A future
disclosure would require a separately reviewed contract rather than a runtime toggle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, StringConstraints, field_validator

from app.core.schemas import Schema
from app.modules.learner_modelling.analytics import DifficultyTier, SupportMode, TaskType
from app.modules.learner_modelling.longitudinal import (
    ChangeDirection,
    ComparisonBlocker,
    LongitudinalCalculationVersion,
    LongitudinalProgressReport,
    MetricTrend,
    MissingReason,
)

DashboardEvidenceState = Literal["sufficient", "limited", "no_observations"]
DisplayedMetricName = Literal[
    "reading_accuracy",
    "reading_fluency_wpm",
    "hesitation_rate_per_word",
]
DisplayedMetricUnit = Literal[
    "proportion",
    "words_per_minute",
    "hesitations_per_attempted_word",
]

ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
Explanation = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=400),
]
VersionLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=28)]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False, max_digits=28),
]

_DISPLAYED_METRICS: tuple[DisplayedMetricName, ...] = (
    "reading_accuracy",
    "reading_fluency_wpm",
    "hesitation_rate_per_word",
)
_METRIC_LABELS: dict[DisplayedMetricName, str] = {
    "reading_accuracy": "Reading accuracy",
    "reading_fluency_wpm": "Reading speed",
    "hesitation_rate_per_word": "Hesitation rate",
}
_TASK_LABELS: dict[TaskType, str] = {
    "independent_reading": "Independent reading",
    "assisted_read_aloud": "Assisted read-aloud",
    "guided_echo_reading": "Guided echo reading",
}
_DIFFICULTY_LABELS: dict[DifficultyTier, str] = {
    "early": "Early level",
    "intermediate": "Intermediate level",
    "advanced": "Advanced level",
}
_SUPPORT_LABELS: dict[SupportMode, str] = {
    "baseline_fixed": "Fixed support",
    "adaptive": "Adaptive support",
    "manual_override": "Manually selected support",
}

_LEARNER_DISCLAIMER = (
    "These observations describe recorded reading sessions. They do not show why "
    "measurements changed."
)
_GUARDIAN_DISCLAIMER = (
    "These descriptive observations do not show that a support mode caused a change "
    "and should be considered with other educational information."
)
_EDUCATOR_DISCLAIMER = (
    "These descriptive educational observations do not establish causes and should "
    "not be used to assess health or ability."
)
_GUARDIAN_LIMITATIONS: tuple[str, ...] = (
    "Trends require at least six valid observations in one comparable context.",
    "Sessions are compared only when task, difficulty, and observed support mode match.",
    "Observed support and difficulty context do not explain why measurements changed.",
)


class FrozenDashboardModel(Schema):
    """Strict immutable base for disclosure-allowlisted projection contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DashboardWindow(FrozenDashboardModel):
    """Half-open UTC reporting period copied from the longitudinal report."""

    start_at_utc: AwareDatetime
    end_at_utc: AwareDatetime

    @field_validator("start_at_utc", "end_at_utc", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class DisplayTrend(FrozenDashboardModel):
    """Small learner-facing observation without internal evidence details."""

    metric_name: DisplayedMetricName
    display_label: ShortText
    unit: DisplayedMetricUnit
    first_value: NonNegativeDecimal | None
    latest_value: NonNegativeDecimal | None
    change_direction: ChangeDirection
    evidence_state: DashboardEvidenceState
    explanation: Explanation


class LearnerContextObservation(FrozenDashboardModel):
    """Friendly labels and three approved metrics for one comparable context."""

    task_label: ShortText
    difficulty_label: ShortText
    support_label: ShortText
    metrics: Annotated[tuple[DisplayTrend, ...], Field(min_length=3, max_length=3)]


class LearnerSupportObservation(FrozenDashboardModel):
    """Minimized description of sessions recorded with one support mode."""

    support_label: ShortText
    session_count: Annotated[int, Field(ge=1)]
    description: Explanation


class LearnerDifficultyObservation(FrozenDashboardModel):
    """Friendly, descriptive difficulty event without achievement claims."""

    observed_at: AwareDatetime
    task_label: ShortText
    support_label: ShortText
    difficulty_label: ShortText
    description: Explanation

    @field_validator("observed_at", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class LearnerProgressProjection(FrozenDashboardModel):
    """Minimal, supportive projection for the already-authorized learner."""

    reporting_period: DashboardWindow
    included_session_count: Annotated[int, Field(ge=0)]
    contexts: Annotated[tuple[LearnerContextObservation, ...], Field(max_length=27)]
    support_observations: Annotated[tuple[LearnerSupportObservation, ...], Field(max_length=3)]
    difficulty_observations: Annotated[
        tuple[LearnerDifficultyObservation, ...], Field(max_length=1024)
    ]
    evidence_message: Explanation
    disclaimer: Explanation


class GuardianMetricTrend(FrozenDashboardModel):
    """Guardian-facing trend with counts but no internal reason codes or versions."""

    metric_name: DisplayedMetricName
    display_label: ShortText
    unit: DisplayedMetricUnit
    valid_observation_count: Annotated[int, Field(ge=0)]
    missing_observation_count: Annotated[int, Field(ge=0)]
    first_value: NonNegativeDecimal | None
    latest_value: NonNegativeDecimal | None
    change_direction: ChangeDirection
    evidence_sufficient: bool
    fluctuation_detected: bool | None
    explanation: Explanation


class GuardianContextSummary(FrozenDashboardModel):
    """Readable like-for-like context summary for an authorized guardian."""

    task_type: TaskType
    task_label: ShortText
    difficulty_tier: DifficultyTier
    difficulty_label: ShortText
    support_mode: SupportMode
    support_label: ShortText
    session_count: Annotated[int, Field(ge=1)]
    first_session_at: AwareDatetime
    latest_session_at: AwareDatetime
    metrics: Annotated[tuple[GuardianMetricTrend, ...], Field(min_length=3, max_length=3)]

    @field_validator("first_session_at", "latest_session_at", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class GuardianSupportExposure(FrozenDashboardModel):
    """Readable support exposure without raw duration telemetry."""

    support_mode: SupportMode
    support_label: ShortText
    session_count: Annotated[int, Field(ge=1)]
    first_observed_at: AwareDatetime
    latest_observed_at: AwareDatetime
    description: Explanation

    @field_validator("first_observed_at", "latest_observed_at", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class GuardianDifficultyObservation(FrozenDashboardModel):
    """Observed difficulty history described without an achievement inference."""

    observed_at: AwareDatetime
    task_type: TaskType
    task_label: ShortText
    support_mode: SupportMode
    support_label: ShortText
    previous_difficulty_tier: DifficultyTier | None
    difficulty_tier: DifficultyTier
    difficulty_label: ShortText
    description: Explanation

    @field_validator("observed_at", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class GuardianSummaryProjection(FrozenDashboardModel):
    """Privacy-minimized educational summary for an authorized guardian."""

    reporting_period: DashboardWindow
    included_session_count: Annotated[int, Field(ge=0)]
    contexts: Annotated[tuple[GuardianContextSummary, ...], Field(max_length=27)]
    support_exposures: Annotated[tuple[GuardianSupportExposure, ...], Field(max_length=3)]
    difficulty_history: Annotated[tuple[GuardianDifficultyObservation, ...], Field(max_length=1024)]
    evidence_limitations: Annotated[tuple[Explanation, ...], Field(min_length=3, max_length=6)]
    disclaimer: Explanation


class EducatorMissingObservation(FrozenDashboardModel):
    """Educator-visible missingness count for one upstream reason code."""

    reason_code: MissingReason
    count: Annotated[int, Field(ge=1)]


class EducatorMetricTrend(FrozenDashboardModel):
    """Detailed approved metric projection preserving upstream calculations."""

    metric_name: DisplayedMetricName
    unit: DisplayedMetricUnit
    total_relevant_sessions: Annotated[int, Field(ge=0)]
    valid_observation_count: Annotated[int, Field(ge=0)]
    missing_observation_count: Annotated[int, Field(ge=0)]
    missing_observations: Annotated[tuple[EducatorMissingObservation, ...], Field(max_length=8)]
    first_value: NonNegativeDecimal | None
    first_observed_at: AwareDatetime | None
    latest_value: NonNegativeDecimal | None
    latest_observed_at: AwareDatetime | None
    early_window_count: Annotated[int, Field(ge=0, le=3)]
    early_window_mean: NonNegativeDecimal | None
    late_window_count: Annotated[int, Field(ge=0, le=3)]
    late_window_mean: NonNegativeDecimal | None
    numeric_change: FiniteDecimal | None
    change_direction: ChangeDirection
    evidence_sufficient: bool
    fluctuation_detected: bool | None
    metric_calculation_version: VersionLabel | None
    observed_metric_versions: Annotated[tuple[VersionLabel, ...], Field(max_length=8)]
    longitudinal_calculation_version: LongitudinalCalculationVersion
    comparison_blocker: ComparisonBlocker | None
    educational_interpretation: Explanation

    @field_validator(
        "first_observed_at",
        "latest_observed_at",
        mode="after",
    )
    @classmethod
    def normalize_optional_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None


class EducatorContextTrend(FrozenDashboardModel):
    """Detailed metrics for one unchanged task/difficulty/support partition."""

    task_type: TaskType
    difficulty_tier: DifficultyTier
    support_mode: SupportMode
    window: DashboardWindow
    session_count: Annotated[int, Field(ge=1)]
    first_session_at: AwareDatetime
    latest_session_at: AwareDatetime
    metrics: Annotated[tuple[EducatorMetricTrend, ...], Field(min_length=3, max_length=3)]

    @field_validator("first_session_at", "latest_session_at", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class EducatorSupportExposure(FrozenDashboardModel):
    """Complete descriptive support exposure from the upstream report."""

    support_mode: SupportMode
    session_count: Annotated[int, Field(ge=1)]
    total_duration_ms: Annotated[int, Field(ge=0)]
    active_duration_ms: Annotated[int, Field(ge=0)]
    first_observed_at: AwareDatetime
    latest_observed_at: AwareDatetime

    @field_validator("first_observed_at", "latest_observed_at", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class EducatorDifficultyObservation(FrozenDashboardModel):
    """Full descriptive difficulty event without achievement or assignment claims."""

    observed_at: AwareDatetime
    task_type: TaskType
    support_mode: SupportMode
    previous_difficulty_tier: DifficultyTier | None
    difficulty_tier: DifficultyTier

    @field_validator("observed_at", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class EducatorAnalyticsProjection(FrozenDashboardModel):
    """Detailed educational analysis with experimental engagement omitted."""

    reporting_period: DashboardWindow
    included_session_count: Annotated[int, Field(ge=0)]
    partitions: Annotated[tuple[EducatorContextTrend, ...], Field(max_length=27)]
    support_mode_exposures: Annotated[tuple[EducatorSupportExposure, ...], Field(max_length=3)]
    difficulty_timeline: Annotated[
        tuple[EducatorDifficultyObservation, ...], Field(max_length=1024)
    ]
    longitudinal_calculation_version: LongitudinalCalculationVersion
    limitations: Annotated[tuple[Explanation, ...], Field(min_length=3, max_length=8)]
    disclaimer: Explanation


def project_learner_progress(report: LongitudinalProgressReport) -> LearnerProgressProjection:
    """Build the learner allowlist from one already-authorized report."""
    contexts = tuple(
        LearnerContextObservation(
            task_label=_TASK_LABELS[_task_type(partition.key.task_type)],
            difficulty_label=_DIFFICULTY_LABELS[_difficulty_tier(partition.key.difficulty_tier)],
            support_label=_SUPPORT_LABELS[_support_mode(partition.key.support_mode)],
            metrics=tuple(
                _learner_metric(metric) for metric in _approved_metrics(partition.metrics)
            ),
        )
        for partition in report.partitions
    )
    return LearnerProgressProjection(
        reporting_period=_window(report),
        included_session_count=report.included_session_count,
        contexts=contexts,
        support_observations=tuple(
            LearnerSupportObservation(
                support_label=_SUPPORT_LABELS[exposure.support_mode],
                session_count=exposure.session_count,
                description=_support_description(exposure.support_mode),
            )
            for exposure in report.support_mode_exposures
        ),
        difficulty_observations=tuple(
            LearnerDifficultyObservation(
                observed_at=event.observed_at,
                task_label=_TASK_LABELS[event.task_type],
                support_label=_SUPPORT_LABELS[event.support_mode],
                difficulty_label=_DIFFICULTY_LABELS[event.difficulty_tier],
                description=_difficulty_description(
                    event.difficulty_tier, event.task_type, event.support_mode
                ),
            )
            for event in report.difficulty_timeline
        ),
        evidence_message=_learner_evidence_message(contexts),
        disclaimer=_LEARNER_DISCLAIMER,
    )


def project_guardian_summary(report: LongitudinalProgressReport) -> GuardianSummaryProjection:
    """Build the guardian allowlist from one already-authorized report."""
    return GuardianSummaryProjection(
        reporting_period=_window(report),
        included_session_count=report.included_session_count,
        contexts=tuple(
            GuardianContextSummary(
                task_type=_task_type(partition.key.task_type),
                task_label=_TASK_LABELS[_task_type(partition.key.task_type)],
                difficulty_tier=_difficulty_tier(partition.key.difficulty_tier),
                difficulty_label=_DIFFICULTY_LABELS[
                    _difficulty_tier(partition.key.difficulty_tier)
                ],
                support_mode=_support_mode(partition.key.support_mode),
                support_label=_SUPPORT_LABELS[_support_mode(partition.key.support_mode)],
                session_count=partition.session_count,
                first_session_at=partition.first_session_at,
                latest_session_at=partition.latest_session_at,
                metrics=tuple(
                    _guardian_metric(metric) for metric in _approved_metrics(partition.metrics)
                ),
            )
            for partition in report.partitions
        ),
        support_exposures=tuple(
            GuardianSupportExposure(
                support_mode=exposure.support_mode,
                support_label=_SUPPORT_LABELS[exposure.support_mode],
                session_count=exposure.session_count,
                first_observed_at=exposure.first_observed_at,
                latest_observed_at=exposure.latest_observed_at,
                description=_support_description(exposure.support_mode),
            )
            for exposure in report.support_mode_exposures
        ),
        difficulty_history=tuple(
            GuardianDifficultyObservation(
                observed_at=event.observed_at,
                task_type=event.task_type,
                task_label=_TASK_LABELS[event.task_type],
                support_mode=event.support_mode,
                support_label=_SUPPORT_LABELS[event.support_mode],
                previous_difficulty_tier=event.previous_difficulty_tier,
                difficulty_tier=event.difficulty_tier,
                difficulty_label=_DIFFICULTY_LABELS[event.difficulty_tier],
                description=_difficulty_description(
                    event.difficulty_tier, event.task_type, event.support_mode
                ),
            )
            for event in report.difficulty_timeline
        ),
        evidence_limitations=_GUARDIAN_LIMITATIONS,
        disclaimer=_GUARDIAN_DISCLAIMER,
    )


def project_educator_analytics(report: LongitudinalProgressReport) -> EducatorAnalyticsProjection:
    """Build the detailed educator allowlist with engagement structurally excluded."""
    return EducatorAnalyticsProjection(
        reporting_period=_window(report),
        included_session_count=report.included_session_count,
        partitions=tuple(
            EducatorContextTrend(
                task_type=_task_type(partition.key.task_type),
                difficulty_tier=_difficulty_tier(partition.key.difficulty_tier),
                support_mode=_support_mode(partition.key.support_mode),
                window=DashboardWindow(
                    start_at_utc=partition.window.start_at_utc,
                    end_at_utc=partition.window.end_at_utc,
                ),
                session_count=partition.session_count,
                first_session_at=partition.first_session_at,
                latest_session_at=partition.latest_session_at,
                metrics=tuple(
                    _educator_metric(metric) for metric in _approved_metrics(partition.metrics)
                ),
            )
            for partition in report.partitions
        ),
        support_mode_exposures=tuple(
            EducatorSupportExposure(
                support_mode=exposure.support_mode,
                session_count=exposure.session_count,
                total_duration_ms=exposure.total_duration_ms,
                active_duration_ms=exposure.active_duration_ms,
                first_observed_at=exposure.first_observed_at,
                latest_observed_at=exposure.latest_observed_at,
            )
            for exposure in report.support_mode_exposures
        ),
        difficulty_timeline=tuple(
            EducatorDifficultyObservation(
                observed_at=event.observed_at,
                task_type=event.task_type,
                support_mode=event.support_mode,
                previous_difficulty_tier=event.previous_difficulty_tier,
                difficulty_tier=event.difficulty_tier,
            )
            for event in report.difficulty_timeline
        ),
        longitudinal_calculation_version=report.longitudinal_calculation_version,
        limitations=report.limitations,
        disclaimer=_EDUCATOR_DISCLAIMER,
    )


def _window(report: LongitudinalProgressReport) -> DashboardWindow:
    return DashboardWindow(
        start_at_utc=report.window.start_at_utc,
        end_at_utc=report.window.end_at_utc,
    )


def _approved_metrics(metrics: tuple[MetricTrend, ...]) -> tuple[MetricTrend, ...]:
    approved = tuple(metric for metric in metrics if metric.metric_name in _DISPLAYED_METRICS)
    if tuple(metric.metric_name for metric in approved) != _DISPLAYED_METRICS:
        raise ValueError("longitudinal report does not contain the approved metric order")
    return approved


def _learner_metric(metric: MetricTrend) -> DisplayTrend:
    metric_name = _displayed_metric_name(metric)
    return DisplayTrend(
        metric_name=metric_name,
        display_label=_METRIC_LABELS[metric_name],
        unit=_displayed_unit(metric),
        first_value=metric.first_value,
        latest_value=metric.latest_value,
        change_direction=metric.change_direction,
        evidence_state=_evidence_state(metric),
        explanation=_trend_explanation(metric),
    )


def _guardian_metric(metric: MetricTrend) -> GuardianMetricTrend:
    metric_name = _displayed_metric_name(metric)
    return GuardianMetricTrend(
        metric_name=metric_name,
        display_label=_METRIC_LABELS[metric_name],
        unit=_displayed_unit(metric),
        valid_observation_count=metric.valid_observation_count,
        missing_observation_count=metric.missing_observation_count,
        first_value=metric.first_value,
        latest_value=metric.latest_value,
        change_direction=metric.change_direction,
        evidence_sufficient=metric.evidence_sufficient,
        fluctuation_detected=metric.fluctuation_detected,
        explanation=_trend_explanation(metric),
    )


def _educator_metric(metric: MetricTrend) -> EducatorMetricTrend:
    return EducatorMetricTrend(
        metric_name=_displayed_metric_name(metric),
        unit=_displayed_unit(metric),
        total_relevant_sessions=metric.total_relevant_sessions,
        valid_observation_count=metric.valid_observation_count,
        missing_observation_count=metric.missing_observation_count,
        missing_observations=tuple(
            EducatorMissingObservation(reason_code=item.reason_code, count=item.count)
            for item in metric.missing_observations
        ),
        first_value=metric.first_value,
        first_observed_at=metric.first_observed_at,
        latest_value=metric.latest_value,
        latest_observed_at=metric.latest_observed_at,
        early_window_count=metric.early_window_count,
        early_window_mean=metric.early_window_mean,
        late_window_count=metric.late_window_count,
        late_window_mean=metric.late_window_mean,
        numeric_change=metric.numeric_change,
        change_direction=metric.change_direction,
        evidence_sufficient=metric.evidence_sufficient,
        fluctuation_detected=metric.fluctuation_detected,
        metric_calculation_version=metric.metric_calculation_version,
        observed_metric_versions=metric.observed_metric_versions,
        longitudinal_calculation_version=metric.longitudinal_calculation_version,
        comparison_blocker=metric.comparison_blocker,
        educational_interpretation=metric.educational_interpretation,
    )


def _displayed_metric_name(metric: MetricTrend) -> DisplayedMetricName:
    if metric.metric_name not in _DISPLAYED_METRICS:
        raise ValueError("experimental engagement is not approved for dashboard disclosure")
    return metric.metric_name


def _displayed_unit(metric: MetricTrend) -> DisplayedMetricUnit:
    if metric.unit not in {
        "proportion",
        "words_per_minute",
        "hesitations_per_attempted_word",
    }:
        raise ValueError("metric unit is not approved for dashboard disclosure")
    return metric.unit


def _task_type(value: str) -> TaskType:
    if value not in _TASK_LABELS:
        raise ValueError("task type is not approved for dashboard disclosure")
    return value


def _difficulty_tier(value: str) -> DifficultyTier:
    if value not in _DIFFICULTY_LABELS:
        raise ValueError("difficulty tier is not approved for dashboard disclosure")
    return value


def _support_mode(value: str) -> SupportMode:
    if value not in _SUPPORT_LABELS:
        raise ValueError("support mode is not approved for dashboard disclosure")
    return value


def _evidence_state(metric: MetricTrend) -> DashboardEvidenceState:
    if metric.valid_observation_count == 0:
        return "no_observations"
    if metric.evidence_sufficient:
        return "sufficient"
    return "limited"


def _trend_explanation(metric: MetricTrend) -> str:
    if not metric.evidence_sufficient:
        return "There are not enough comparable observations to describe a trend."

    metric_name = _displayed_metric_name(metric)
    labels = {
        "reading_accuracy": "Measured accuracy",
        "reading_fluency_wpm": "Reading-speed measurements",
        "hesitation_rate_per_word": "Measured hesitation frequency",
    }
    endings = {
        "increased": "increased in comparable sessions.",
        "decreased": "decreased in comparable sessions.",
        "no_observed_change": "showed no observed change in comparable sessions.",
    }
    direction = metric.change_direction
    if direction == "insufficient_evidence":
        return "There are not enough comparable observations to describe a trend."
    explanation = f"{labels[metric_name]} {endings[direction]}"
    if metric.fluctuation_detected:
        explanation += " Measurements varied during the selected period."
    return explanation


def _support_description(support_mode: SupportMode) -> str:
    descriptions = {
        "baseline_fixed": "Reading sessions were recorded using fixed support.",
        "adaptive": "Reading sessions were recorded using adaptive support.",
        "manual_override": "Reading sessions were recorded using manually selected support.",
    }
    return descriptions[support_mode]


def _difficulty_description(
    difficulty_tier: DifficultyTier,
    task_type: TaskType,
    support_mode: SupportMode,
) -> str:
    return (
        f"{_DIFFICULTY_LABELS[difficulty_tier]} reading sessions were observed for "
        f"{_TASK_LABELS[task_type].lower()} with {_SUPPORT_LABELS[support_mode].lower()}."
    )


def _learner_evidence_message(
    contexts: tuple[LearnerContextObservation, ...],
) -> str:
    metrics = tuple(metric for context in contexts for metric in context.metrics)
    if not metrics or all(metric.evidence_state == "no_observations" for metric in metrics):
        return "No measured observations are available for this reporting period."
    if all(metric.evidence_state == "sufficient" for metric in metrics):
        return "There are enough comparable observations to describe these trends."
    return "Some observations are available, but more comparable sessions are needed."
