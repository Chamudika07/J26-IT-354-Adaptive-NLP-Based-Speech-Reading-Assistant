"""Synthetic tests for the completed-evidence adaptation draft mapper."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

import app.modules.learner_modelling.adaptation_mapping as mapping_module
from app.modules.learner_modelling.adaptation import (
    AdaptationInput,
    AdaptationThresholds,
    SupportPreferences,
    recommend_adaptation,
)
from app.modules.learner_modelling.adaptation_mapping import (
    AdaptationMappingError,
    CompletedSessionEvidence,
    map_longitudinal_partition_to_adaptation_input,
    select_completed_session_evidence,
)
from app.modules.learner_modelling.analytics import PartitionKey, SessionTelemetry
from app.modules.learner_modelling.historical import (
    HistoricalSessionQuery,
    HistoricalSessionRecord,
)
from app.modules.learner_modelling.longitudinal import (
    LongitudinalObservation,
    LongitudinalProgressReport,
    LongitudinalWindow,
    calculate_longitudinal_progress,
)


def _window() -> LongitudinalWindow:
    return LongitudinalWindow(
        start_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        end_at_utc=datetime(2026, 2, 1, tzinfo=UTC),
    )


def _query(*, session_limit: int = 1000) -> HistoricalSessionQuery:
    window = _window()
    return HistoricalSessionQuery(
        learner_id=UUID("10000000-0000-0000-0000-000000000001"),
        start_at_utc=window.start_at_utc,
        end_at_utc=window.end_at_utc,
        session_limit=session_limit,
    )


def _key(
    *,
    task_type: str = "independent_reading",
    difficulty_tier: str = "intermediate",
    support_mode: str = "adaptive",
) -> PartitionKey:
    return PartitionKey(
        task_type=task_type,
        difficulty_tier=difficulty_tier,
        support_mode=support_mode,
    )


def _observation(
    day: int,
    *,
    key: PartitionKey | None = None,
    words_correct: int = 96,
    active_duration_ms: int = 60_000,
    hesitation_count: int | None = 2,
) -> LongitudinalObservation:
    selected = key or _key()
    telemetry = SessionTelemetry(
        session_start_time=datetime(2026, 1, day, 9, tzinfo=UTC),
        session_id=f"session-{selected.task_type}-{day}",
        words_attempted=100,
        words_correct=words_correct,
        target_word_count=100,
        active_duration_ms=active_duration_ms,
        total_duration_ms=active_duration_ms + 10_000,
        hesitation_count=hesitation_count,
        total_pause_duration_ms=5_000,
        completion_status="completed",
        task_type=selected.task_type,
        difficulty_tier=selected.difficulty_tier,
        support_mode=selected.support_mode,
    )
    return LongitudinalObservation.from_telemetry(telemetry)


def _record(
    day: int,
    *,
    identity: UUID | None = None,
    key: PartitionKey | None = None,
    completion_status: object = "completed",
    words_correct: int = 96,
    active_duration_ms: int = 60_000,
    hesitation_count: int | None = 2,
) -> HistoricalSessionRecord:
    selected = key or _key()
    return HistoricalSessionRecord(
        id=identity or UUID(int=day),
        session_start_time=datetime(2026, 1, day, 9, tzinfo=UTC),
        task_type=selected.task_type,
        difficulty_tier=selected.difficulty_tier,
        support_mode=selected.support_mode,
        completion_status=completion_status,  # type: ignore[arg-type]
        words_attempted=100,
        words_correct=words_correct,
        target_word_count=100,
        active_duration_ms=active_duration_ms,
        total_duration_ms=active_duration_ms + 10_000,
        hesitation_count=hesitation_count,
        total_pause_duration_ms=5_000,
    )


def _report(*observations: LongitudinalObservation) -> LongitudinalProgressReport:
    return calculate_longitudinal_progress(observations, _window())


def _evidence(*observations: LongitudinalObservation) -> CompletedSessionEvidence:
    return CompletedSessionEvidence.from_observations(observations, _window())


def _map(
    evidence: CompletedSessionEvidence,
    key: PartitionKey | None = None,
    *,
    manual_override_locked: bool = False,
    preferences: SupportPreferences | None = None,
) -> AdaptationInput:
    thresholds = AdaptationThresholds()
    return map_longitudinal_partition_to_adaptation_input(
        evidence,
        key or _key(),
        support_preferences=preferences or SupportPreferences(),
        manual_override_locked=manual_override_locked,
        thresholds=thresholds,
    )


def test_sufficient_complete_partition_maps_authoritative_means() -> None:
    evidence = _evidence(*(_observation(day) for day in range(1, 4)))

    adaptation_input = _map(evidence)
    decision = recommend_adaptation(adaptation_input)

    assert adaptation_input.session_count == 3
    assert adaptation_input.evidence_window_sufficient is True
    assert adaptation_input.mean_accuracy == 0.96
    assert adaptation_input.mean_wpm == 100.0
    assert adaptation_input.mean_hesitation_rate_per_word == 0.02
    assert decision.action == "increase_difficulty"
    assert decision.is_advisory is True
    assert decision.safe_to_apply_automatically is False


def test_too_few_sessions_maps_to_insufficient_evidence() -> None:
    adaptation_input = _map(_evidence(_observation(1), _observation(2)))
    decision = recommend_adaptation(adaptation_input)

    assert adaptation_input.session_count == 2
    assert adaptation_input.evidence_window_sufficient is False
    assert decision.action == "insufficient_evidence"
    assert decision.reason_codes == ("insufficient_session_count",)


def test_missing_core_measurement_is_not_imputed() -> None:
    evidence = _evidence(
        _observation(1),
        _observation(2, hesitation_count=None),
        _observation(3),
    )

    adaptation_input = _map(evidence)
    decision = recommend_adaptation(adaptation_input)

    assert adaptation_input.mean_accuracy == 0.96
    assert adaptation_input.mean_wpm == 100.0
    assert adaptation_input.mean_hesitation_rate_per_word is None
    assert adaptation_input.evidence_window_sufficient is False
    assert decision.action == "insufficient_evidence"
    assert decision.reason_codes == ("insufficient_evidence_window",)


def test_invalid_observation_is_rejected_before_mapping() -> None:
    with pytest.raises(ValueError, match="words_correct"):
        _observation(1, words_correct=101)


def test_missing_partition_is_rejected() -> None:
    evidence = _evidence(*(_observation(day) for day in range(1, 4)))

    with pytest.raises(AdaptationMappingError, match="exactly one"):
        _map(evidence, _key(task_type="guided_echo_reading"))


def test_exact_partition_selection_never_combines_contexts() -> None:
    selected_key = _key()
    other_key = _key(
        task_type="assisted_read_aloud",
        difficulty_tier="early",
        support_mode="baseline_fixed",
    )
    evidence = _evidence(
        *(_observation(day, key=selected_key) for day in range(1, 4)),
        *(
            _observation(
                day,
                key=other_key,
                words_correct=60,
                active_duration_ms=150_000,
                hesitation_count=15,
            )
            for day in range(4, 7)
        ),
    )

    selected = _map(evidence, selected_key)
    other = _map(evidence, other_key)

    assert selected.current_difficulty_tier == "intermediate"
    assert selected.current_support_mode == "adaptive"
    assert selected.mean_accuracy == 0.96
    assert other.current_difficulty_tier == "early"
    assert other.current_support_mode == "baseline_fixed"
    assert other.mean_accuracy == 0.6


def test_mapping_is_stable_for_reordered_source_observations() -> None:
    observations = tuple(_observation(day) for day in range(1, 5))

    first = _map(_evidence(*observations))
    second = _map(_evidence(*reversed(observations)))

    assert first == second


def test_explicit_preferences_and_manual_override_are_preserved() -> None:
    key = _key(support_mode="manual_override")
    preferences = SupportPreferences(
        enable_speech_cues=False,
        simplification_level=3,
        pause_threshold_ms=3_000,
    )
    evidence = _evidence(*(_observation(day, key=key) for day in range(1, 4)))

    adaptation_input = _map(
        evidence,
        key,
        manual_override_locked=True,
        preferences=preferences,
    )
    decision = recommend_adaptation(adaptation_input)

    assert adaptation_input.support_preferences is preferences
    assert adaptation_input.manual_override_locked is True
    assert decision.action == "maintain"
    assert decision.blocked_by_manual_override is True
    assert decision.safe_to_apply_automatically is False


def test_fixed_support_partition_remains_fixed_and_advisory() -> None:
    key = _key(support_mode="baseline_fixed")
    evidence = _evidence(*(_observation(day, key=key) for day in range(1, 4)))

    decision = recommend_adaptation(_map(evidence, key))

    assert decision.action == "maintain"
    assert decision.recommended_support_mode == "baseline_fixed"
    assert decision.reason_codes == ("baseline_fixed_mode",)
    assert decision.is_advisory is True
    assert decision.safe_to_apply_automatically is False


@pytest.mark.parametrize("completion_status", ["abandoned", "interrupted"])
def test_noncompleted_session_evidence_is_rejected(completion_status: str) -> None:
    observation = _observation(1)
    object.__setattr__(observation.telemetry, "completion_status", completion_status)

    with pytest.raises(AdaptationMappingError, match="only completed"):
        _evidence(observation)


def test_unknown_completion_state_is_rejected_without_exposing_evidence() -> None:
    observation = _observation(1)
    object.__setattr__(observation.telemetry, "completion_status", "unknown")

    with pytest.raises(AdaptationMappingError, match="evidence is invalid") as captured:
        _evidence(observation)

    assert "session-" not in str(captured.value)
    assert "unknown" not in str(captured.value)


def test_conflicting_duplicate_session_evidence_is_rejected() -> None:
    first = _observation(1)
    conflicting = _observation(1, words_correct=60)

    with pytest.raises(AdaptationMappingError, match="evidence is invalid"):
        _evidence(first, conflicting)


def test_raw_longitudinal_report_cannot_assert_completion_provenance() -> None:
    report = _report(*(_observation(day) for day in range(1, 4)))

    with pytest.raises(TypeError, match="verified CompletedSessionEvidence"):
        map_longitudinal_partition_to_adaptation_input(
            report,  # type: ignore[arg-type]
            _key(),
            support_preferences=SupportPreferences(),
            manual_override_locked=False,
        )


def test_completion_evidence_cannot_be_constructed_from_a_report() -> None:
    with pytest.raises(TypeError, match="from_observations"):
        CompletedSessionEvidence()

    unverified = object.__new__(CompletedSessionEvidence)
    object.__setattr__(unverified, "report", _report(_observation(1)))
    with pytest.raises(TypeError, match="verified CompletedSessionEvidence"):
        _map(unverified)


def test_completed_history_selection_excludes_known_noncompleted_sessions() -> None:
    records = (
        _record(1),
        _record(2, completion_status="abandoned"),
        _record(3),
        _record(4, completion_status="interrupted"),
        _record(5),
    )

    evidence = select_completed_session_evidence(records, _query())
    adaptation_input = _map(evidence)

    assert evidence.report.included_session_count == 3
    assert adaptation_input.session_count == 3
    assert adaptation_input.mean_accuracy == 0.96
    assert adaptation_input.evidence_window_sufficient is True


@pytest.mark.parametrize("completion_status", ["unknown", "", None, 1])
def test_history_selection_rejects_unknown_or_invalid_completion_states(
    completion_status: object,
) -> None:
    record = _record(1, completion_status=completion_status)

    with pytest.raises(AdaptationMappingError, match="completion state is invalid") as captured:
        select_completed_session_evidence((record,), _query())

    assert str(record.id) not in str(captured.value)
    assert repr(completion_status) not in str(captured.value)


def test_history_selection_rejects_duplicate_and_conflicting_identities() -> None:
    identity = UUID("20000000-0000-0000-0000-000000000002")
    duplicate = _record(1, identity=identity)
    conflicting = _record(2, identity=identity, words_correct=60)

    with pytest.raises(AdaptationMappingError, match="identities must be unique"):
        select_completed_session_evidence((duplicate, duplicate), _query())
    with pytest.raises(AdaptationMappingError, match="identities must be unique"):
        select_completed_session_evidence((duplicate, conflicting), _query())


def test_history_selection_with_no_completed_sessions_preserves_empty_evidence() -> None:
    query = _query()
    evidence = select_completed_session_evidence(
        (
            _record(1, completion_status="abandoned"),
            _record(2, completion_status="interrupted"),
        ),
        query,
    )

    assert evidence.report.window.start_at_utc == query.start_at_utc
    assert evidence.report.window.end_at_utc == query.end_at_utc
    assert evidence.report.included_session_count == 0
    assert evidence.report.partitions == ()
    with pytest.raises(AdaptationMappingError, match="exactly one"):
        _map(evidence)


def test_history_selection_never_manufactures_sufficient_evidence() -> None:
    evidence = select_completed_session_evidence(
        (
            _record(1),
            _record(2),
            _record(3, completion_status="abandoned"),
        ),
        _query(),
    )

    adaptation_input = _map(evidence)
    decision = recommend_adaptation(adaptation_input)

    assert adaptation_input.session_count == 2
    assert adaptation_input.evidence_window_sufficient is False
    assert decision.action == "insufficient_evidence"


def test_completed_history_selection_preserves_partition_isolation() -> None:
    selected_key = _key()
    other_key = _key(
        task_type="assisted_read_aloud",
        difficulty_tier="early",
        support_mode="baseline_fixed",
    )
    records = (
        *(_record(day, key=selected_key) for day in range(1, 4)),
        *(
            _record(
                day,
                key=other_key,
                words_correct=60,
                active_duration_ms=150_000,
                hesitation_count=15,
            )
            for day in range(4, 7)
        ),
    )

    evidence = select_completed_session_evidence(records, _query())
    selected = _map(evidence, selected_key)
    other = _map(evidence, other_key)

    assert selected.mean_accuracy == 0.96
    assert selected.current_support_mode == "adaptive"
    assert other.mean_accuracy == 0.6
    assert other.current_support_mode == "baseline_fixed"


def test_completed_history_selection_is_stable_across_input_order() -> None:
    records = tuple(_record(day) for day in range(1, 5))

    first = select_completed_session_evidence(records, _query())
    second = select_completed_session_evidence(tuple(reversed(records)), _query())

    assert first.report == second.report
    assert _map(first) == _map(second)


def test_history_selection_preserves_and_enforces_exact_reporting_window() -> None:
    query = _query()
    evidence = select_completed_session_evidence((_record(1),), query)

    assert evidence.report.window.start_at_utc == query.start_at_utc
    assert evidence.report.window.end_at_utc == query.end_at_utc

    at_exclusive_end = replace(_record(1), session_start_time=query.end_at_utc)
    with pytest.raises(AdaptationMappingError, match="outside.*reporting window"):
        select_completed_session_evidence((at_exclusive_end,), query)


def test_history_selection_enforces_existing_result_limit() -> None:
    query = _query(session_limit=2)

    with pytest.raises(AdaptationMappingError, match="bounded result limit"):
        select_completed_session_evidence(
            (_record(1), _record(2), _record(3)),
            query,
        )


def test_history_selection_validates_excluded_records_without_silent_coercion() -> None:
    invalid_abandoned = replace(
        _record(1, completion_status="abandoned"),
        words_correct=101,
    )

    with pytest.raises(AdaptationMappingError, match="session evidence is invalid"):
        select_completed_session_evidence((invalid_abandoned,), _query())


def test_mapper_has_no_database_http_or_persistence_dependencies() -> None:
    source = inspect.getsource(mapping_module)
    tree = ast.parse(source)
    imported_roots = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_roots.update(
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert imported_roots.isdisjoint({"fastapi", "httpx", "requests", "sqlalchemy"})
    assert ".add(" not in source
    assert ".commit(" not in source
    assert ".flush(" not in source
    assert "APIRouter" not in source
