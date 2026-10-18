"""Pure longitudinal progress analytics for already-authorized session observations.

The caller is responsible for learner-level authorization, consent evaluation, and
record retrieval. This module performs no persistence, HTTP, authentication, consent,
or network operations and deliberately carries no learner identity.

Trend comparisons use two non-overlapping windows of three valid observations. Values
come from the existing session metric functions. Aggregation converts those rounded
source values to :class:`~decimal.Decimal` and uses ROUND_HALF_EVEN at the source
metric precision: four decimal places for accuracy, hesitation, and engagement, and
two decimal places for WPM.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from math import isfinite
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.schemas import Schema
from app.modules.learner_modelling.analytics import (
    DifficultyTier,
    PartitionKey,
    SessionTelemetry,
    SupportMode,
    TaskType,
    calculate_experimental_engagement,
    calculate_hesitation_frequency,
    calculate_reading_accuracy,
    calculate_words_per_minute,
)

LongitudinalCalculationVersion = Literal["v0.1-early-late-3"]
LONGITUDINAL_CALCULATION_VERSION: LongitudinalCalculationVersion = "v0.1-early-late-3"
READING_ACCURACY_CALCULATION_VERSION = "analytics.calculate_reading_accuracy-v1"
WPM_CALCULATION_VERSION = "analytics.calculate_words_per_minute-v1"
HESITATION_CALCULATION_VERSION = "analytics.calculate_hesitation_frequency-v1"

NON_CLINICAL_LONGITUDINAL_DISCLAIMER = (
    "These descriptive educational observations do not establish causality and do not "
    "constitute a clinical assessment, diagnosis, severity estimate, or treatment advice."
)
ENGAGEMENT_RESEARCH_DISCLAIMER = (
    "Engagement is an experimental educational research heuristic; it does not measure "
    "or infer attention, psychology, or a clinical condition."
)

EARLY_LATE_WINDOW_SIZE = 3
MIN_TREND_OBSERVATIONS = EARLY_LATE_WINDOW_SIZE * 2
MIN_WPM_DURATION_MS = 1000

MetricName = Literal[
    "reading_accuracy",
    "reading_fluency_wpm",
    "hesitation_rate_per_word",
    "engagement_score",
]
MetricUnit = Literal[
    "proportion",
    "words_per_minute",
    "hesitations_per_attempted_word",
]
ChangeDirection = Literal[
    "increased",
    "decreased",
    "no_observed_change",
    "insufficient_evidence",
]
MissingReason = Literal[
    "zero_words_attempted",
    "insufficient_active_duration",
    "hesitation_not_measured",
    "engagement_inputs_missing",
    "wpm_above_configured_ceiling",
]
ComparisonBlocker = Literal["mixed_metric_versions"]

_TASK_TYPES = {"independent_reading", "assisted_read_aloud", "guided_echo_reading"}
_DIFFICULTY_TIERS = {"early", "intermediate", "advanced"}
_SUPPORT_MODES = {"baseline_fixed", "adaptive", "manual_override"}
_COMPLETION_STATUSES = {"completed", "abandoned", "interrupted"}

_METRIC_ORDER: tuple[MetricName, ...] = (
    "reading_accuracy",
    "reading_fluency_wpm",
    "hesitation_rate_per_word",
    "engagement_score",
)
_METRIC_UNITS: dict[MetricName, MetricUnit] = {
    "reading_accuracy": "proportion",
    "reading_fluency_wpm": "words_per_minute",
    "hesitation_rate_per_word": "hesitations_per_attempted_word",
    "engagement_score": "proportion",
}
_METRIC_QUANTA: dict[MetricName, Decimal] = {
    "reading_accuracy": Decimal("0.0001"),
    "reading_fluency_wpm": Decimal("0.01"),
    "hesitation_rate_per_word": Decimal("0.0001"),
    "engagement_score": Decimal("0.0001"),
}

BoundedText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
VersionLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=28)]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False, max_digits=28),
]


@dataclass(frozen=True, slots=True)
class LongitudinalObservation:
    """Immutable input pairing session telemetry with versioned engagement output."""

    telemetry: SessionTelemetry
    engagement_score: Decimal | None
    engagement_formula_version: str | None

    def __post_init__(self) -> None:
        self.telemetry.__post_init__()
        session_id = self.telemetry.session_id
        if session_id is None or not session_id.strip() or len(session_id) > 128:
            raise ValueError(
                "session_id must be a non-empty stable identifier of at most 128 chars"
            )
        if self.telemetry.task_type not in _TASK_TYPES:
            raise ValueError(f"unsupported task_type: {self.telemetry.task_type!r}")
        if self.telemetry.difficulty_tier not in _DIFFICULTY_TIERS:
            raise ValueError(f"unsupported difficulty_tier: {self.telemetry.difficulty_tier!r}")
        if self.telemetry.support_mode not in _SUPPORT_MODES:
            raise ValueError(f"unsupported support_mode: {self.telemetry.support_mode!r}")
        if self.telemetry.completion_status not in _COMPLETION_STATUSES:
            raise ValueError(f"unsupported completion_status: {self.telemetry.completion_status!r}")
        if self.engagement_score is not None:
            if not isinstance(self.engagement_score, Decimal):
                raise TypeError("engagement_score must be Decimal when supplied")
            if not self.engagement_score.is_finite() or not (
                Decimal("0") <= self.engagement_score <= Decimal("1")
            ):
                raise ValueError("engagement_score must be finite and in [0, 1]")
            if not self.engagement_formula_version or not self.engagement_formula_version.strip():
                raise ValueError("engagement score requires a formula version")
        if self.engagement_formula_version is not None and (
            not self.engagement_formula_version.strip()
            or len(self.engagement_formula_version) > 128
        ):
            raise ValueError("engagement_formula_version must be 1-128 non-whitespace chars")

    @classmethod
    def from_telemetry(cls, telemetry: SessionTelemetry) -> LongitudinalObservation:
        """Calculate engagement through the existing versioned analytics function."""
        engagement = calculate_experimental_engagement(telemetry)
        score = Decimal(str(engagement.score)) if engagement.score is not None else None
        return cls(
            telemetry=telemetry,
            engagement_score=score,
            engagement_formula_version=engagement.formula_version,
        )


class FrozenLongitudinalModel(Schema):
    """Strict immutable base for longitudinal report contracts."""

    model_config = ConfigDict(from_attributes=True, extra="forbid", frozen=True)


class LongitudinalWindow(FrozenLongitudinalModel):
    """Required half-open UTC interval ``[start_at_utc, end_at_utc)``."""

    start_at_utc: AwareDatetime
    end_at_utc: AwareDatetime

    @field_validator("start_at_utc", "end_at_utc", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_order(self) -> LongitudinalWindow:
        if self.start_at_utc >= self.end_at_utc:
            raise ValueError("start_at_utc must be earlier than end_at_utc")
        return self


class MissingObservationCount(FrozenLongitudinalModel):
    """Count of missing metric observations with one deterministic reason code."""

    reason_code: MissingReason
    count: Annotated[int, Field(ge=1)]


class MetricTrend(FrozenLongitudinalModel):
    """One metric's descriptive values and non-overlapping window comparison."""

    metric_name: MetricName
    unit: MetricUnit
    total_relevant_sessions: Annotated[int, Field(ge=0)]
    valid_observation_count: Annotated[int, Field(ge=0)]
    missing_observation_count: Annotated[int, Field(ge=0)]
    missing_observations: Annotated[tuple[MissingObservationCount, ...], Field(max_length=8)]
    mean_value: NonNegativeDecimal | None
    first_value: NonNegativeDecimal | None
    first_observed_at: AwareDatetime | None
    latest_value: NonNegativeDecimal | None
    latest_observed_at: AwareDatetime | None
    early_window_count: Annotated[int, Field(ge=0, le=EARLY_LATE_WINDOW_SIZE)]
    early_window_mean: NonNegativeDecimal | None
    late_window_count: Annotated[int, Field(ge=0, le=EARLY_LATE_WINDOW_SIZE)]
    late_window_mean: NonNegativeDecimal | None
    numeric_change: FiniteDecimal | None
    change_direction: ChangeDirection
    evidence_sufficient: bool
    fluctuation_detected: bool | None
    metric_calculation_version: VersionLabel | None
    observed_metric_versions: Annotated[tuple[VersionLabel, ...], Field(max_length=8)]
    longitudinal_calculation_version: LongitudinalCalculationVersion = (
        LONGITUDINAL_CALCULATION_VERSION
    )
    comparison_blocker: ComparisonBlocker | None = None
    educational_interpretation: BoundedText
    metric_disclaimer: BoundedText | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> MetricTrend:
        if self.valid_observation_count + self.missing_observation_count != (
            self.total_relevant_sessions
        ):
            raise ValueError("valid and missing observations must equal relevant sessions")
        if sum(item.count for item in self.missing_observations) != self.missing_observation_count:
            raise ValueError("missing reason counts must equal missing_observation_count")
        if (self.first_value is None) != (self.first_observed_at is None):
            raise ValueError("first value and timestamp must be present together")
        if (self.latest_value is None) != (self.latest_observed_at is None):
            raise ValueError("latest value and timestamp must be present together")
        if self.valid_observation_count == 0 and self.first_value is not None:
            raise ValueError("zero valid observations cannot expose descriptive values")
        if self.valid_observation_count > 0 and self.first_value is None:
            raise ValueError("valid observations require first and latest values")
        if (self.valid_observation_count == 0) != (self.mean_value is None):
            raise ValueError("mean value must be present exactly when valid observations exist")
        if self.evidence_sufficient:
            if self.comparison_blocker is not None:
                raise ValueError("sufficient evidence cannot have a comparison blocker")
            if self.early_window_count != EARLY_LATE_WINDOW_SIZE or (
                self.late_window_count != EARLY_LATE_WINDOW_SIZE
            ):
                raise ValueError("sufficient evidence requires two complete windows")
            if None in (
                self.early_window_mean,
                self.late_window_mean,
                self.numeric_change,
                self.fluctuation_detected,
            ):
                raise ValueError("sufficient evidence requires complete trend fields")
            if self.change_direction == "insufficient_evidence":
                raise ValueError("sufficient evidence requires an observed direction")
        elif (
            any(
                value is not None
                for value in (
                    self.early_window_mean,
                    self.late_window_mean,
                    self.numeric_change,
                    self.fluctuation_detected,
                )
            )
            or self.early_window_count != 0
            or self.late_window_count != 0
        ):
            raise ValueError("insufficient evidence must not expose trend-window results")
        elif self.change_direction != "insufficient_evidence":
            raise ValueError("insufficient evidence requires the matching direction")
        return self


class ContextPartitionTrend(FrozenLongitudinalModel):
    """Four metric trends for one comparable task/difficulty/support context."""

    key: PartitionKey
    window: LongitudinalWindow
    session_count: Annotated[int, Field(ge=1)]
    first_session_at: AwareDatetime
    latest_session_at: AwareDatetime
    metrics: Annotated[tuple[MetricTrend, ...], Field(min_length=4, max_length=4)]

    @model_validator(mode="after")
    def validate_metric_set(self) -> ContextPartitionTrend:
        if tuple(metric.metric_name for metric in self.metrics) != _METRIC_ORDER:
            raise ValueError("partition metrics must use the canonical four-metric order")
        return self


class SupportModeExposure(FrozenLongitudinalModel):
    """Descriptive observed-session exposure; never a research assignment."""

    support_mode: SupportMode
    session_count: Annotated[int, Field(ge=1)]
    total_duration_ms: Annotated[int, Field(ge=0)]
    active_duration_ms: Annotated[int, Field(ge=0)]
    first_observed_at: AwareDatetime
    latest_observed_at: AwareDatetime

    @model_validator(mode="after")
    def validate_durations(self) -> SupportModeExposure:
        if self.active_duration_ms > self.total_duration_ms:
            raise ValueError("active duration cannot exceed total duration")
        return self


class DifficultyTierObservation(FrozenLongitudinalModel):
    """Observed initial tier or transition within task and support-mode context."""

    observed_at: AwareDatetime
    task_type: TaskType
    support_mode: SupportMode
    previous_difficulty_tier: DifficultyTier | None
    difficulty_tier: DifficultyTier


class LongitudinalProgressReport(FrozenLongitudinalModel):
    """Deterministic learner-free projection for future authorized dashboards."""

    window: LongitudinalWindow
    included_session_count: Annotated[int, Field(ge=0)]
    partitions: tuple[ContextPartitionTrend, ...]
    support_mode_exposures: tuple[SupportModeExposure, ...]
    difficulty_timeline: tuple[DifficultyTierObservation, ...]
    longitudinal_calculation_version: LongitudinalCalculationVersion = (
        LONGITUDINAL_CALCULATION_VERSION
    )
    limitations: Annotated[tuple[BoundedText, ...], Field(min_length=3, max_length=8)]
    disclaimer: BoundedText = NON_CLINICAL_LONGITUDINAL_DISCLAIMER


@dataclass(frozen=True, slots=True)
class _MetricObservation:
    observed_at: datetime
    session_id: str
    value: Decimal
    version: str


def calculate_longitudinal_progress(
    observations: Sequence[LongitudinalObservation],
    window: LongitudinalWindow,
    *,
    max_wpm: int | None = None,
) -> LongitudinalProgressReport:
    """Build a pure report for one learner's already-authorized observations."""
    if max_wpm is not None and max_wpm < 0:
        raise ValueError("max_wpm cannot be negative")
    _validate_unique_session_ids(observations)

    included = [
        observation
        for observation in observations
        if window.start_at_utc
        <= observation.telemetry.session_start_time.astimezone(UTC)
        < window.end_at_utc
    ]
    included.sort(key=_observation_sort_key)

    grouped: dict[PartitionKey, list[LongitudinalObservation]] = defaultdict(list)
    for observation in included:
        telemetry = observation.telemetry
        grouped[
            PartitionKey(
                task_type=telemetry.task_type,
                difficulty_tier=telemetry.difficulty_tier,
                support_mode=telemetry.support_mode,
            )
        ].append(observation)

    partitions = tuple(
        _build_partition(key, grouped[key], window, max_wpm=max_wpm)
        for key in sorted(
            grouped,
            key=lambda item: (item.task_type, item.difficulty_tier, item.support_mode),
        )
    )

    return LongitudinalProgressReport(
        window=window,
        included_session_count=len(included),
        partitions=partitions,
        support_mode_exposures=_build_support_exposures(included),
        difficulty_timeline=_build_difficulty_timeline(included),
        limitations=(
            "Results are descriptive and do not establish that support caused a change.",
            "Task, difficulty tier, and observed support mode are analyzed separately.",
            "Observed support mode does not represent randomized research assignment.",
            "Exact historical support-setting values are not available in session telemetry.",
        ),
    )


def _validate_unique_session_ids(observations: Sequence[LongitudinalObservation]) -> None:
    identifiers = [observation.telemetry.session_id for observation in observations]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("session_id values must be unique")


def _observation_sort_key(observation: LongitudinalObservation) -> tuple[datetime, str]:
    session_id = observation.telemetry.session_id
    if session_id is None:  # guarded by LongitudinalObservation
        raise ValueError("session_id is required")
    return observation.telemetry.session_start_time.astimezone(UTC), session_id


def _build_partition(
    key: PartitionKey,
    observations: list[LongitudinalObservation],
    window: LongitudinalWindow,
    *,
    max_wpm: int | None,
) -> ContextPartitionTrend:
    metric_values: dict[MetricName, list[_MetricObservation]] = {name: [] for name in _METRIC_ORDER}
    missing: dict[MetricName, Counter[MissingReason]] = {name: Counter() for name in _METRIC_ORDER}

    for observation in observations:
        _collect_metric_observations(observation, metric_values, missing, max_wpm=max_wpm)

    metrics = tuple(
        _build_metric_trend(
            metric_name,
            len(observations),
            metric_values[metric_name],
            missing[metric_name],
        )
        for metric_name in _METRIC_ORDER
    )
    times = [item.telemetry.session_start_time.astimezone(UTC) for item in observations]
    return ContextPartitionTrend(
        key=key,
        window=window,
        session_count=len(observations),
        first_session_at=min(times),
        latest_session_at=max(times),
        metrics=metrics,
    )


def _collect_metric_observations(
    observation: LongitudinalObservation,
    values: dict[MetricName, list[_MetricObservation]],
    missing: dict[MetricName, Counter[MissingReason]],
    *,
    max_wpm: int | None,
) -> None:
    telemetry = observation.telemetry
    observed_at, session_id = _observation_sort_key(observation)

    accuracy = calculate_reading_accuracy(telemetry.words_attempted, telemetry.words_correct)
    if accuracy is None:
        missing["reading_accuracy"]["zero_words_attempted"] += 1
    else:
        values["reading_accuracy"].append(
            _metric_observation(
                observed_at,
                session_id,
                accuracy,
                READING_ACCURACY_CALCULATION_VERSION,
                "reading_accuracy",
            )
        )

    wpm = calculate_words_per_minute(
        telemetry.words_attempted,
        telemetry.active_duration_ms,
        min_duration_ms=MIN_WPM_DURATION_MS,
        max_wpm=max_wpm,
    )
    if wpm is None:
        reason: MissingReason = (
            "insufficient_active_duration"
            if telemetry.active_duration_ms < MIN_WPM_DURATION_MS
            else "wpm_above_configured_ceiling"
        )
        missing["reading_fluency_wpm"][reason] += 1
    else:
        values["reading_fluency_wpm"].append(
            _metric_observation(
                observed_at,
                session_id,
                wpm,
                WPM_CALCULATION_VERSION,
                "reading_fluency_wpm",
            )
        )

    hesitation = calculate_hesitation_frequency(
        telemetry.hesitation_count,
        telemetry.words_attempted,
        telemetry.active_duration_ms,
    )
    if hesitation is None:
        missing["hesitation_rate_per_word"]["hesitation_not_measured"] += 1
    elif hesitation.rate_per_word is None:
        missing["hesitation_rate_per_word"]["zero_words_attempted"] += 1
    else:
        values["hesitation_rate_per_word"].append(
            _metric_observation(
                observed_at,
                session_id,
                hesitation.rate_per_word,
                HESITATION_CALCULATION_VERSION,
                "hesitation_rate_per_word",
            )
        )

    if observation.engagement_score is None:
        missing["engagement_score"]["engagement_inputs_missing"] += 1
    else:
        version = observation.engagement_formula_version
        if version is None:  # guarded by LongitudinalObservation
            raise ValueError("engagement score requires a formula version")
        values["engagement_score"].append(
            _MetricObservation(
                observed_at=observed_at,
                session_id=session_id,
                value=_quantize("engagement_score", observation.engagement_score),
                version=version,
            )
        )


def _metric_observation(
    observed_at: datetime,
    session_id: str,
    value: float,
    version: str,
    metric_name: MetricName,
) -> _MetricObservation:
    if not isfinite(value):
        raise ValueError(f"{metric_name} produced a non-finite value")
    return _MetricObservation(
        observed_at=observed_at,
        session_id=session_id,
        value=_quantize(metric_name, Decimal(str(value))),
        version=version,
    )


def _build_metric_trend(
    metric_name: MetricName,
    total_sessions: int,
    observations: list[_MetricObservation],
    missing: Counter[MissingReason],
) -> MetricTrend:
    observations.sort(key=lambda item: (item.observed_at, item.session_id))
    versions = tuple(sorted({item.version for item in observations}))
    mixed_versions = metric_name == "engagement_score" and len(versions) > 1
    sufficient = len(observations) >= MIN_TREND_OBSERVATIONS and not mixed_versions

    first = observations[0] if observations else None
    latest = observations[-1] if observations else None
    early_mean: Decimal | None = None
    late_mean: Decimal | None = None
    change: Decimal | None = None
    direction: ChangeDirection = "insufficient_evidence"
    fluctuation: bool | None = None
    early_count = 0
    late_count = 0

    if sufficient:
        early = observations[:EARLY_LATE_WINDOW_SIZE]
        late = observations[-EARLY_LATE_WINDOW_SIZE:]
        early_count = len(early)
        late_count = len(late)
        early_mean = _mean(metric_name, early)
        late_mean = _mean(metric_name, late)
        change = _quantize(metric_name, late_mean - early_mean)
        direction = _direction(change)
        fluctuation = _has_fluctuation(observations)

    metric_version = versions[0] if len(versions) == 1 else None
    return MetricTrend(
        metric_name=metric_name,
        unit=_METRIC_UNITS[metric_name],
        total_relevant_sessions=total_sessions,
        valid_observation_count=len(observations),
        missing_observation_count=sum(missing.values()),
        missing_observations=tuple(
            MissingObservationCount(reason_code=reason, count=count)
            for reason, count in sorted(missing.items())
        ),
        mean_value=_mean(metric_name, observations) if observations else None,
        first_value=first.value if first else None,
        first_observed_at=first.observed_at if first else None,
        latest_value=latest.value if latest else None,
        latest_observed_at=latest.observed_at if latest else None,
        early_window_count=early_count,
        early_window_mean=early_mean,
        late_window_count=late_count,
        late_window_mean=late_mean,
        numeric_change=change,
        change_direction=direction,
        evidence_sufficient=sufficient,
        fluctuation_detected=fluctuation,
        metric_calculation_version=metric_version,
        observed_metric_versions=versions,
        comparison_blocker="mixed_metric_versions" if mixed_versions else None,
        educational_interpretation=_interpretation(metric_name, direction, mixed_versions),
        metric_disclaimer=(
            ENGAGEMENT_RESEARCH_DISCLAIMER if metric_name == "engagement_score" else None
        ),
    )


def _quantize(metric_name: MetricName, value: Decimal) -> Decimal:
    return value.quantize(_METRIC_QUANTA[metric_name], rounding=ROUND_HALF_EVEN)


def _mean(metric_name: MetricName, observations: list[_MetricObservation]) -> Decimal:
    total = sum((item.value for item in observations), start=Decimal("0"))
    return _quantize(metric_name, total / Decimal(len(observations)))


def _direction(change: Decimal) -> ChangeDirection:
    if change > 0:
        return "increased"
    if change < 0:
        return "decreased"
    return "no_observed_change"


def _has_fluctuation(observations: list[_MetricObservation]) -> bool:
    deltas = [
        current.value - previous.value
        for previous, current in zip(observations, observations[1:], strict=False)
    ]
    return any(delta > 0 for delta in deltas) and any(delta < 0 for delta in deltas)


def _interpretation(
    metric_name: MetricName,
    direction: ChangeDirection,
    mixed_versions: bool,
) -> str:
    if mixed_versions:
        return "Engagement observations use different formula versions and cannot be compared."
    if direction == "insufficient_evidence":
        return "Insufficient comparable observations are available."

    labels = {
        "reading_accuracy": "Measured reading accuracy",
        "reading_fluency_wpm": "Measured reading speed",
        "hesitation_rate_per_word": "Measured hesitation frequency",
        "engagement_score": "The experimental engagement score",
    }
    endings = {
        "increased": "increased across the selected observations.",
        "decreased": "decreased across the selected observations.",
        "no_observed_change": "showed no observed change across the selected observations.",
    }
    return f"{labels[metric_name]} {endings[direction]}"


def _build_support_exposures(
    observations: list[LongitudinalObservation],
) -> tuple[SupportModeExposure, ...]:
    grouped: dict[str, list[LongitudinalObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.telemetry.support_mode].append(observation)

    exposures: list[SupportModeExposure] = []
    for mode in sorted(grouped):
        items = grouped[mode]
        times = [item.telemetry.session_start_time.astimezone(UTC) for item in items]
        exposures.append(
            SupportModeExposure(
                support_mode=mode,
                session_count=len(items),
                total_duration_ms=sum(item.telemetry.total_duration_ms for item in items),
                active_duration_ms=sum(item.telemetry.active_duration_ms for item in items),
                first_observed_at=min(times),
                latest_observed_at=max(times),
            )
        )
    return tuple(exposures)


def _build_difficulty_timeline(
    observations: list[LongitudinalObservation],
) -> tuple[DifficultyTierObservation, ...]:
    grouped: dict[tuple[str, str], list[LongitudinalObservation]] = defaultdict(list)
    for observation in observations:
        telemetry = observation.telemetry
        grouped[(telemetry.task_type, telemetry.support_mode)].append(observation)

    timeline: list[tuple[datetime, str, DifficultyTierObservation]] = []
    for context in sorted(grouped):
        previous: str | None = None
        for observation in sorted(grouped[context], key=_observation_sort_key):
            telemetry = observation.telemetry
            if telemetry.difficulty_tier == previous:
                continue
            observed_at, session_id = _observation_sort_key(observation)
            event = DifficultyTierObservation(
                observed_at=observed_at,
                task_type=telemetry.task_type,
                support_mode=telemetry.support_mode,
                previous_difficulty_tier=previous,
                difficulty_tier=telemetry.difficulty_tier,
            )
            timeline.append((observed_at, session_id, event))
            previous = telemetry.difficulty_tier
    timeline.sort(key=lambda item: (item[0], item[1], item[2].task_type, item[2].support_mode))
    return tuple(item[2] for item in timeline)
