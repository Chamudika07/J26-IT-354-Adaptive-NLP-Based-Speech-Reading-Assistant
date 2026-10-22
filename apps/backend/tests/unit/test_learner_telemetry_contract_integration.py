"""Test-only integration boundary for a future reading/speech telemetry producer.

The Speech module does not yet expose an approved producer output contract, so these
tests deliberately begin at Component 4's existing ``ReadingSessionIngest`` schema.
They do not define a production adapter, authorize a caller, evaluate consent, access
the database, or duplicate the analytics formulas.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.modules.learner_modelling.analytics import (
    calculate_hesitation_frequency,
    calculate_reading_accuracy,
    calculate_words_per_minute,
)
from app.modules.learner_modelling.schemas import (
    ReadingSessionIngest,
    compute_canonical_session_digest,
)

LEARNER_ID = UUID("11111111-1111-4111-8111-111111111111")
SESSION_ID = UUID("22222222-2222-4222-8222-222222222222")
DOCUMENT_ID = UUID("33333333-3333-4333-8333-333333333333")
SESSION_START = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)
SESSION_END = datetime(2026, 10, 18, 8, 5, tzinfo=UTC)


def _synthetic_candidate(**overrides: object) -> dict[str, object]:
    """Return deterministic synthetic fields shaped only for the validated ingest schema."""
    candidate: dict[str, object] = {
        "learner_id": LEARNER_ID,
        "client_session_id": SESSION_ID,
        "document_id": DOCUMENT_ID,
        "session_start_time": SESSION_START,
        "session_end_time": SESSION_END,
        "task_type": "independent_reading",
        "difficulty_tier": "intermediate",
        "support_mode": "adaptive",
        "completion_status": "completed",
        "words_attempted": 100,
        "words_correct": 90,
        "target_word_count": 120,
        "active_duration_ms": 240_000,
        "total_duration_ms": 300_000,
        "hesitation_count": 3,
        "total_pause_duration_ms": 30_000,
        "pause_count": 4,
        "replay_count": 1,
    }
    candidate.update(overrides)
    return candidate


def _validate_test_candidate(candidate: Mapping[str, object]) -> ReadingSessionIngest:
    """Use the existing Component 4 boundary without defining a producer contract."""
    return ReadingSessionIngest.model_validate(candidate)


def test_valid_candidate_preserves_authoritative_fields_and_uses_existing_analytics() -> None:
    ingest = _validate_test_candidate(_synthetic_candidate())
    telemetry = ingest.to_session_telemetry()

    assert ingest.learner_id == LEARNER_ID
    assert ingest.client_session_id == SESSION_ID
    assert ingest.document_id == DOCUMENT_ID
    assert ingest.session_start_time == SESSION_START
    assert ingest.session_end_time == SESSION_END
    assert ingest.replay_count == 1
    assert telemetry.session_id == str(SESSION_ID)
    assert telemetry.session_start_time == SESSION_START
    assert telemetry.task_type == "independent_reading"
    assert telemetry.difficulty_tier == "intermediate"
    assert telemetry.support_mode == "adaptive"
    assert telemetry.completion_status == "completed"
    assert telemetry.words_attempted == 100
    assert telemetry.words_correct == 90
    assert telemetry.target_word_count == 120
    assert telemetry.active_duration_ms == 240_000
    assert telemetry.total_duration_ms == 300_000
    assert telemetry.hesitation_count == 3
    assert telemetry.total_pause_duration_ms == 30_000
    assert telemetry.pause_count == 4

    assert calculate_reading_accuracy(telemetry.words_attempted, telemetry.words_correct) == 0.9
    assert (
        calculate_words_per_minute(telemetry.words_attempted, telemetry.active_duration_ms) == 25.0
    )
    hesitation = calculate_hesitation_frequency(
        telemetry.hesitation_count,
        telemetry.words_attempted,
        telemetry.active_duration_ms,
    )
    assert hesitation is not None
    assert hesitation.hesitation_count == 3
    assert hesitation.rate_per_word == 0.03
    assert hesitation.rate_per_minute == 0.75


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("words_attempted", -1),
        ("words_correct", -1),
        ("target_word_count", -1),
        ("active_duration_ms", -1),
        ("total_duration_ms", -1),
        ("hesitation_count", -1),
        ("total_pause_duration_ms", -1),
        ("pause_count", -1),
        ("replay_count", -1),
    ],
)
def test_negative_producer_measurements_are_rejected(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        _validate_test_candidate(_synthetic_candidate(**{field: value}))


@pytest.mark.parametrize(
    "overrides",
    [
        {"words_attempted": 10, "words_correct": 11},
        {"active_duration_ms": 300_001, "total_duration_ms": 300_000},
        {"total_pause_duration_ms": 300_001, "total_duration_ms": 300_000},
        {"session_start_time": SESSION_END, "session_end_time": SESSION_START},
    ],
)
def test_inconsistent_producer_measurements_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _validate_test_candidate(_synthetic_candidate(**overrides))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_type", "unclassified"),
        ("difficulty_tier", "expert"),
        ("support_mode", "automatic"),
        ("completion_status", "unknown"),
    ],
)
def test_unsupported_context_or_completion_values_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        _validate_test_candidate(_synthetic_candidate(**{field: value}))


@pytest.mark.parametrize(
    "missing_field",
    [
        "learner_id",
        "client_session_id",
        "session_start_time",
        "session_end_time",
        "words_attempted",
        "words_correct",
        "target_word_count",
        "active_duration_ms",
        "total_duration_ms",
    ],
)
def test_missing_required_ingest_fields_are_rejected(missing_field: str) -> None:
    candidate = _synthetic_candidate()
    del candidate[missing_field]

    with pytest.raises(ValidationError):
        _validate_test_candidate(candidate)


def test_ambiguous_precalculated_or_recognized_word_fields_are_rejected() -> None:
    candidate = _synthetic_candidate()
    candidate.update(
        {
            "recognized_words": ["synthetic", "content"],
            "calculated_accuracy": 0.9,
        }
    )

    with pytest.raises(ValidationError):
        _validate_test_candidate(candidate)


@pytest.mark.parametrize("completion_status", ["abandoned", "interrupted"])
def test_supported_incomplete_session_status_is_preserved(completion_status: str) -> None:
    ingest = _validate_test_candidate(_synthetic_candidate(completion_status=completion_status))

    assert ingest.completion_status == completion_status
    assert ingest.to_session_telemetry().completion_status == completion_status


def test_zero_attempted_words_remain_zero_without_manufacturing_results() -> None:
    ingest = _validate_test_candidate(
        _synthetic_candidate(
            words_attempted=0,
            words_correct=0,
            target_word_count=0,
            hesitation_count=0,
        )
    )
    telemetry = ingest.to_session_telemetry()

    assert calculate_reading_accuracy(telemetry.words_attempted, telemetry.words_correct) is None
    assert (
        calculate_words_per_minute(telemetry.words_attempted, telemetry.active_duration_ms) == 0.0
    )
    hesitation = calculate_hesitation_frequency(
        telemetry.hesitation_count,
        telemetry.words_attempted,
        telemetry.active_duration_ms,
    )
    assert hesitation is not None
    assert hesitation.rate_per_word is None
    assert hesitation.rate_per_minute == 0.0


def test_missing_hesitation_measurement_remains_missing() -> None:
    telemetry = _validate_test_candidate(
        _synthetic_candidate(hesitation_count=None)
    ).to_session_telemetry()

    assert telemetry.hesitation_count is None
    assert (
        calculate_hesitation_frequency(
            telemetry.hesitation_count,
            telemetry.words_attempted,
            telemetry.active_duration_ms,
        )
        is None
    )


def test_duplicate_identity_is_deterministic_and_conflicting_payload_changes_digest() -> None:
    first = _validate_test_candidate(_synthetic_candidate())
    exact_retry = _validate_test_candidate(_synthetic_candidate())
    conflicting_retry = _validate_test_candidate(_synthetic_candidate(words_correct=89))

    assert first.client_session_id == exact_retry.client_session_id
    assert first.client_session_id == conflicting_retry.client_session_id
    assert compute_canonical_session_digest(first) == compute_canonical_session_digest(exact_retry)
    assert compute_canonical_session_digest(first) != compute_canonical_session_digest(
        conflicting_retry
    )


@pytest.mark.parametrize("client_session_id", [None, "", "not-a-uuid"])
def test_missing_or_malformed_session_identity_is_rejected(client_session_id: object) -> None:
    with pytest.raises(ValidationError):
        _validate_test_candidate(_synthetic_candidate(client_session_id=client_session_id))
