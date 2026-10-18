"""Pure draft bridge from completed longitudinal evidence to adaptation inputs.

This module is intentionally not wired into services, persistence, or HTTP routes.
It maps exactly one comparable task/difficulty/support partition and never combines
evidence across contexts.

``CompletedSessionEvidence`` is the explicit provenance boundary. It can only be
created through validated observations, rejects every completion state except
``completed``, and calculates its own report. A caller therefore cannot pass an
arbitrary ``LongitudinalProgressReport`` and silently assert completed-session
provenance.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.modules.learner_modelling.adaptation import (
    AdaptationInput,
    AdaptationThresholds,
    SupportPreferences,
)
from app.modules.learner_modelling.analytics import PartitionKey
from app.modules.learner_modelling.historical import (
    HistoricalDataIntegrityError,
    HistoricalSessionQuery,
    HistoricalSessionRecord,
    historical_record_to_observation,
)
from app.modules.learner_modelling.longitudinal import (
    ContextPartitionTrend,
    LongitudinalObservation,
    LongitudinalProgressReport,
    LongitudinalWindow,
    MetricTrend,
    calculate_longitudinal_progress,
)

ADAPTATION_MAPPING_VERSION = "v0.2-verified-completed-partition-mean"
_COMPLETION_EVIDENCE_MARKER = object()
_KNOWN_COMPLETION_STATUSES = frozenset({"completed", "abandoned", "interrupted"})


class AdaptationMappingError(ValueError):
    """The supplied report cannot be mapped without inventing or mixing evidence."""


@dataclass(frozen=True, slots=True, init=False)
class CompletedSessionEvidence:
    """A report calculated only from validated, completed session observations.

    Construction is intentionally restricted to :meth:`from_observations`. The
    boundary retains the aggregate report rather than raw session observations.
    """

    report: LongitudinalProgressReport
    _verification_marker: object = field(repr=False, compare=False)

    def __init__(self) -> None:
        raise TypeError("use CompletedSessionEvidence.from_observations")

    @classmethod
    def from_observations(
        cls,
        observations: Sequence[LongitudinalObservation],
        window: LongitudinalWindow,
        *,
        max_wpm: int | None = None,
    ) -> CompletedSessionEvidence:
        """Validate authoritative completion evidence and calculate its report.

        Invalid, incomplete, abandoned, interrupted, duplicate, or otherwise
        ambiguous evidence fails as one sanitized mapping error. No observation is
        dropped or coerced.
        """
        if not isinstance(observations, Sequence):
            raise TypeError("observations must be a sequence")
        if not isinstance(window, LongitudinalWindow):
            raise TypeError("window must be a LongitudinalWindow")

        try:
            for observation in observations:
                if not isinstance(observation, LongitudinalObservation):
                    raise TypeError("all observations must be LongitudinalObservation values")
                observation.__post_init__()
                if observation.telemetry.completion_status != "completed":
                    raise AdaptationMappingError(
                        "completed-session evidence must contain only completed sessions"
                    )
            report = calculate_longitudinal_progress(observations, window, max_wpm=max_wpm)
        except AdaptationMappingError:
            raise
        except (TypeError, ValueError, OverflowError) as exc:
            raise AdaptationMappingError("completed-session evidence is invalid") from exc

        evidence = object.__new__(cls)
        object.__setattr__(evidence, "report", report)
        object.__setattr__(evidence, "_verification_marker", _COMPLETION_EVIDENCE_MARKER)
        return evidence


def select_completed_session_evidence(
    records: Sequence[HistoricalSessionRecord],
    query: HistoricalSessionQuery,
    *,
    max_wpm: int | None = None,
) -> CompletedSessionEvidence:
    """Select completed evidence from an already-authorized bounded result.

    ``query`` preserves the repository's validated window and result limit. Every
    record is validated before selection, identities must be unique across all
    completion states, and records outside the half-open query window are rejected.
    This function performs no retrieval, authorization, consent, or persistence.
    """
    if not isinstance(records, Sequence):
        raise TypeError("records must be a sequence")
    if not isinstance(query, HistoricalSessionQuery):
        raise TypeError("query must be a HistoricalSessionQuery")
    if len(records) > query.session_limit:
        raise AdaptationMappingError("historical evidence exceeds its bounded result limit")

    window = LongitudinalWindow(
        start_at_utc=query.start_at_utc,
        end_at_utc=query.end_at_utc,
    )
    completed_observations: list[LongitudinalObservation] = []
    seen_ids: set[object] = set()

    try:
        for record in records:
            if not isinstance(record, HistoricalSessionRecord):
                raise TypeError("all records must be HistoricalSessionRecord values")
            if (
                not isinstance(record.completion_status, str)
                or record.completion_status not in _KNOWN_COMPLETION_STATUSES
            ):
                raise AdaptationMappingError("historical completion state is invalid")

            observation = historical_record_to_observation(record)
            if record.id in seen_ids:
                raise AdaptationMappingError("historical session identities must be unique")
            seen_ids |= {record.id}

            observed_at = observation.telemetry.session_start_time
            if not window.start_at_utc <= observed_at < window.end_at_utc:
                raise AdaptationMappingError(
                    "historical evidence falls outside its bounded reporting window"
                )
            if record.completion_status == "completed":
                completed_observations.append(observation)
    except AdaptationMappingError:
        raise
    except (HistoricalDataIntegrityError, TypeError, ValueError, OverflowError) as exc:
        raise AdaptationMappingError("historical session evidence is invalid") from exc

    return CompletedSessionEvidence.from_observations(
        tuple(completed_observations),
        window,
        max_wpm=max_wpm,
    )


def map_longitudinal_partition_to_adaptation_input(
    evidence: CompletedSessionEvidence,
    partition_key: PartitionKey,
    *,
    support_preferences: SupportPreferences,
    manual_override_locked: bool,
    thresholds: AdaptationThresholds | None = None,
) -> AdaptationInput:
    """Map one exact comparable partition to an advisory-engine input.

    Safeguards:
    - ``evidence`` must be factory-created from validated completed observations;
      raw longitudinal reports are rejected.
    - support preferences and manual-lock state are explicit authoritative inputs;
      neither is inferred from session telemetry.
    - a core metric is usable only when every session in the selected partition has a
      valid observation for it. Missing core measurements force an insufficient
      evidence window rather than being imputed.
    - engagement remains optional and is omitted when measurements are incomplete or
      formula versions are mixed.
    - longitudinal trend sufficiency and adaptation sufficiency are separate. The
      latter uses the supplied, versioned adaptation threshold session minimum.
    """
    if (
        not isinstance(evidence, CompletedSessionEvidence)
        or getattr(evidence, "_verification_marker", None) is not _COMPLETION_EVIDENCE_MARKER
    ):
        raise TypeError("evidence must be verified CompletedSessionEvidence")
    if not isinstance(partition_key, PartitionKey):
        raise TypeError("partition_key must be a PartitionKey")
    if not isinstance(support_preferences, SupportPreferences):
        raise TypeError("support_preferences must be SupportPreferences")
    if type(manual_override_locked) is not bool:
        raise TypeError("manual_override_locked must be bool")

    applied_thresholds = thresholds if thresholds is not None else AdaptationThresholds()
    if not isinstance(applied_thresholds, AdaptationThresholds):
        raise TypeError("thresholds must be AdaptationThresholds")

    partition = _select_exact_partition(evidence.report, partition_key)
    metrics = {metric.metric_name: metric for metric in partition.metrics}

    accuracy = _complete_partition_mean(metrics["reading_accuracy"], partition)
    wpm = _complete_partition_mean(metrics["reading_fluency_wpm"], partition)
    hesitation = _complete_partition_mean(metrics["hesitation_rate_per_word"], partition)
    engagement = _complete_partition_mean(
        metrics["engagement_score"],
        partition,
        require_single_version=True,
    )

    core_means = (accuracy, wpm, hesitation)
    evidence_window_sufficient = (
        partition.session_count >= applied_thresholds.min_sessions_for_recommendation
        and all(value is not None for value in core_means)
    )

    return AdaptationInput(
        current_difficulty_tier=partition.key.difficulty_tier,
        current_support_mode=partition.key.support_mode,
        manual_override_locked=manual_override_locked,
        support_preferences=support_preferences,
        mean_accuracy=accuracy,
        mean_wpm=wpm,
        mean_hesitation_rate_per_word=hesitation,
        mean_engagement_score=engagement,
        session_count=partition.session_count,
        evidence_window_sufficient=evidence_window_sufficient,
    )


def _select_exact_partition(
    report: LongitudinalProgressReport,
    partition_key: PartitionKey,
) -> ContextPartitionTrend:
    matches = tuple(partition for partition in report.partitions if partition.key == partition_key)
    if len(matches) != 1:
        raise AdaptationMappingError("report must contain exactly one matching partition")
    return matches[0]


def _complete_partition_mean(
    metric: MetricTrend,
    partition: ContextPartitionTrend,
    *,
    require_single_version: bool = False,
) -> float | None:
    if (
        metric.total_relevant_sessions != partition.session_count
        or metric.valid_observation_count != partition.session_count
        or metric.missing_observation_count != 0
        or metric.mean_value is None
    ):
        return None
    if require_single_version and (
        metric.metric_calculation_version is None or metric.comparison_blocker is not None
    ):
        return None
    return float(metric.mean_value)
