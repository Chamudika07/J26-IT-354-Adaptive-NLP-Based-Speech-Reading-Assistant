"""Unit tests for reading-session schemas, validation, and canonical hashing.

Verifies strict Pydantic parsing, relational and boundary invariants,
deterministic canonical SHA-256 digest calculation, and schema compatibility
with both ReadingSession ORM models and pure SessionTelemetry analytics.
"""

import re
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Table

from app.modules.learner_modelling.analytics import (
    calculate_experimental_engagement,
    calculate_hesitation_frequency,
    calculate_reading_accuracy,
    calculate_words_per_minute,
)
from app.modules.learner_modelling.models import ReadingSession
from app.modules.learner_modelling.schemas import (
    CANONICAL_DIGEST_VERSION,
    NON_CLINICAL_DISCLAIMER,
    CalculatedMetricsResponse,
    ReadingSessionIngest,
    ReadingSessionResponse,
    build_canonical_payload,
    compute_canonical_session_digest,
)


def _make_valid_payload_dict(**overrides: object) -> dict[str, object]:
    """Generate a valid synthetic dictionary representation of ReadingSessionIngest."""
    start_time = datetime(2026, 10, 16, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2026, 10, 16, 10, 5, 0, tzinfo=UTC)
    payload: dict[str, object] = {
        "learner_id": str(uuid4()),
        "client_session_id": str(uuid4()),
        "document_id": str(uuid4()),
        "session_start_time": start_time.isoformat(),
        "session_end_time": end_time.isoformat(),
        "task_type": "independent_reading",
        "difficulty_tier": "intermediate",
        "support_mode": "adaptive",
        "completion_status": "completed",
        "words_attempted": 100,
        "words_correct": 92,
        "target_word_count": 100,
        "active_duration_ms": 240000,
        "total_duration_ms": 300000,
        "hesitation_count": 3,
        "total_pause_duration_ms": 40000,
        "pause_count": 4,
        "replay_count": 1,
    }
    payload.update(overrides)
    return payload


# ============================================================================
# 1. Validation & Constraint Invariants Tests
# ============================================================================


def test_valid_payload_instantiation() -> None:
    data = _make_valid_payload_dict()
    session = ReadingSessionIngest.model_validate(data)

    assert isinstance(session.learner_id, UUID)
    assert isinstance(session.client_session_id, UUID)
    assert isinstance(session.document_id, UUID)
    assert session.words_attempted == 100
    assert session.words_correct == 92
    assert session.hesitation_count == 3
    assert session.total_pause_duration_ms == 40000
    assert session.pause_count == 4
    assert session.replay_count == 1


def test_missing_nullable_telemetry_remains_none() -> None:
    data = _make_valid_payload_dict(
        document_id=None,
        hesitation_count=None,
        total_pause_duration_ms=None,
        pause_count=None,
        replay_count=None,
    )
    session = ReadingSessionIngest.model_validate(data)
    assert session.document_id is None
    assert session.hesitation_count is None
    assert session.total_pause_duration_ms is None
    assert session.pause_count is None
    assert session.replay_count is None

    # Test when optional keys are completely omitted
    for key in (
        "document_id",
        "hesitation_count",
        "total_pause_duration_ms",
        "pause_count",
        "replay_count",
    ):
        del data[key]
    session_omitted = ReadingSessionIngest.model_validate(data)
    assert session_omitted.document_id is None
    assert session_omitted.hesitation_count is None
    assert session_omitted.total_pause_duration_ms is None
    assert session_omitted.pause_count is None
    assert session_omitted.replay_count is None


def test_reject_naive_datetimes() -> None:
    data = _make_valid_payload_dict(session_start_time="2026-10-16T10:00:00")
    with pytest.raises(ValidationError, match="Input should have timezone info"):
        ReadingSessionIngest.model_validate(data)

    data_end = _make_valid_payload_dict(session_end_time="2026-10-16T10:05:00")
    with pytest.raises(ValidationError, match="Input should have timezone info"):
        ReadingSessionIngest.model_validate(data_end)


def test_reject_unexpected_request_fields() -> None:
    data = _make_valid_payload_dict(unexpected_field="unexpected_value")
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ReadingSessionIngest.model_validate(data)


def test_reject_client_provided_request_digest() -> None:
    """Client is not allowed to pass a request_digest field in the ingestion payload."""
    data = _make_valid_payload_dict(request_digest="a" * 64)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ReadingSessionIngest.model_validate(data)


@pytest.mark.parametrize(
    "field",
    [
        "words_attempted",
        "words_correct",
        "target_word_count",
        "active_duration_ms",
        "total_duration_ms",
        "hesitation_count",
        "total_pause_duration_ms",
        "pause_count",
        "replay_count",
    ],
)
def test_reject_negative_numerics(field: str) -> None:
    data = _make_valid_payload_dict(**{field: -1})
    with pytest.raises(ValidationError):
        ReadingSessionIngest.model_validate(data)


def test_reject_words_correct_exceeding_words_attempted() -> None:
    data = _make_valid_payload_dict(words_attempted=50, words_correct=51)
    with pytest.raises(ValidationError, match="words_correct .* cannot exceed words_attempted"):
        ReadingSessionIngest.model_validate(data)


def test_reject_active_duration_exceeding_total_duration() -> None:
    data = _make_valid_payload_dict(active_duration_ms=60001, total_duration_ms=60000)
    with pytest.raises(
        ValidationError, match="active_duration_ms .* cannot exceed total_duration_ms"
    ):
        ReadingSessionIngest.model_validate(data)


def test_reject_pause_duration_exceeding_total_duration() -> None:
    data = _make_valid_payload_dict(
        active_duration_ms=50000,
        total_pause_duration_ms=70000,
        total_duration_ms=60000,
    )
    with pytest.raises(
        ValidationError, match="total_pause_duration_ms .* cannot exceed total_duration_ms"
    ):
        ReadingSessionIngest.model_validate(data)


def test_reject_session_end_time_before_start_time() -> None:
    start_time = datetime(2026, 10, 16, 10, 5, 0, tzinfo=UTC)
    end_time = datetime(2026, 10, 16, 10, 0, 0, tzinfo=UTC)
    data = _make_valid_payload_dict(
        session_start_time=start_time.isoformat(),
        session_end_time=end_time.isoformat(),
    )
    with pytest.raises(
        ValidationError, match="session_end_time .* cannot be earlier than session_start_time"
    ):
        ReadingSessionIngest.model_validate(data)


# ============================================================================
# 2. Categorical Agreement with ORM Model and Analytics
# ============================================================================


def test_schema_and_orm_categorical_values_agree() -> None:
    """Verify schema literal types match ReadingSession table CHECK constraints."""
    table: Table = ReadingSession.__table__  # type: ignore[assignment]
    check_constraints = {
        c.name: c.sqltext.text
        for c in table.constraints
        if hasattr(c, "sqltext") and hasattr(c.sqltext, "text")
    }

    # Verify task_type
    task_types = {"independent_reading", "assisted_read_aloud", "guided_echo_reading"}
    for val in task_types:
        data = _make_valid_payload_dict(task_type=val)
        session = ReadingSessionIngest.model_validate(data)
        assert session.task_type == val
    assert "ck_reading_sessions_task_type_values" in check_constraints

    # Verify difficulty_tier
    tiers = {"early", "intermediate", "advanced"}
    for val in tiers:
        data = _make_valid_payload_dict(difficulty_tier=val)
        session = ReadingSessionIngest.model_validate(data)
        assert session.difficulty_tier == val
    assert "ck_reading_sessions_difficulty_tier_values" in check_constraints

    # Verify support_mode
    modes = {"baseline_fixed", "adaptive", "manual_override"}
    for val in modes:
        data = _make_valid_payload_dict(support_mode=val)
        session = ReadingSessionIngest.model_validate(data)
        assert session.support_mode == val
    assert "ck_reading_sessions_support_mode_values" in check_constraints

    # Verify completion_status
    statuses = {"completed", "abandoned", "interrupted"}
    for val in statuses:
        data = _make_valid_payload_dict(completion_status=val)
        session = ReadingSessionIngest.model_validate(data)
        assert session.completion_status == val
    assert "ck_reading_sessions_completion_status_values" in check_constraints


# ============================================================================
# 3. Canonical Hashing Tests
# ============================================================================


def test_identical_payloads_with_different_key_ordering_produce_identical_digests() -> None:
    data1 = _make_valid_payload_dict()
    # Reverse key order in data2
    data2 = dict(reversed(list(data1.items())))

    session1 = ReadingSessionIngest.model_validate(data1)
    session2 = ReadingSessionIngest.model_validate(data2)

    digest1 = compute_canonical_session_digest(session1)
    digest2 = compute_canonical_session_digest(session2)

    assert digest1 == digest2
    assert re.fullmatch(r"^[0-9a-f]{64}$", digest1) is not None


def test_identical_instants_with_different_timezone_offsets_produce_identical_digests() -> None:
    start_utc = datetime(2026, 10, 16, 10, 0, 0, tzinfo=UTC)
    end_utc = datetime(2026, 10, 16, 10, 5, 0, tzinfo=UTC)

    # Express identical instants with +05:30 offset
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    start_ist = datetime(2026, 10, 16, 15, 30, 0, tzinfo=tz_ist)
    end_ist = datetime(2026, 10, 16, 15, 35, 0, tzinfo=tz_ist)

    base_data = _make_valid_payload_dict()
    data_utc = dict(
        base_data,
        session_start_time=start_utc.isoformat(),
        session_end_time=end_utc.isoformat(),
    )
    data_ist = dict(
        base_data,
        session_start_time=start_ist.isoformat(),
        session_end_time=end_ist.isoformat(),
    )

    session_utc = ReadingSessionIngest.model_validate(data_utc)
    session_ist = ReadingSessionIngest.model_validate(data_ist)

    assert compute_canonical_session_digest(session_utc) == compute_canonical_session_digest(
        session_ist
    )


def test_uuid_serialization_stability() -> None:
    base_data = _make_valid_payload_dict()
    learner_id_lower = "11111111-2222-3333-4444-555555555555"
    learner_id_upper = "11111111-2222-3333-4444-555555555555".upper()

    session1 = ReadingSessionIngest.model_validate(dict(base_data, learner_id=learner_id_lower))
    session2 = ReadingSessionIngest.model_validate(dict(base_data, learner_id=learner_id_upper))

    assert compute_canonical_session_digest(session1) == compute_canonical_session_digest(session2)


def test_missing_vs_explicit_none_produces_identical_digests() -> None:
    """Omitted optional fields and explicit nulls normalize consistently in canonical hashing."""
    data_explicit_none = _make_valid_payload_dict(
        document_id=None,
        hesitation_count=None,
        total_pause_duration_ms=None,
        pause_count=None,
        replay_count=None,
    )
    data_omitted = dict(data_explicit_none)
    for field in (
        "document_id",
        "hesitation_count",
        "total_pause_duration_ms",
        "pause_count",
        "replay_count",
    ):
        del data_omitted[field]

    session1 = ReadingSessionIngest.model_validate(data_explicit_none)
    session2 = ReadingSessionIngest.model_validate(data_omitted)

    assert compute_canonical_session_digest(session1) == compute_canonical_session_digest(session2)


@pytest.mark.parametrize(
    ("field", "new_val"),
    [
        ("words_attempted", 105),
        ("words_correct", 90),
        ("target_word_count", 110),
        ("active_duration_ms", 239000),
        ("total_duration_ms", 305000),
        ("hesitation_count", 4),
        ("total_pause_duration_ms", 41000),
        ("pause_count", 5),
        ("replay_count", 2),
        ("task_type", "assisted_read_aloud"),
        ("difficulty_tier", "advanced"),
        ("support_mode", "baseline_fixed"),
        ("completion_status", "abandoned"),
    ],
)
def test_changing_any_meaningful_field_changes_digest(field: str, new_val: object) -> None:
    session_orig = ReadingSessionIngest.model_validate(_make_valid_payload_dict())
    session_modified = ReadingSessionIngest.model_validate(
        _make_valid_payload_dict(**{field: new_val})
    )

    assert compute_canonical_session_digest(session_orig) != compute_canonical_session_digest(
        session_modified
    )


def test_canonical_payload_structure_and_version() -> None:
    session = ReadingSessionIngest.model_validate(_make_valid_payload_dict())
    canonical_dict = build_canonical_payload(session)

    assert canonical_dict["canonical_version"] == CANONICAL_DIGEST_VERSION
    assert canonical_dict["canonical_version"] == "v1"
    assert "learner_id" in canonical_dict
    assert "client_session_id" in canonical_dict
    assert "words_attempted" in canonical_dict
    assert "support_mode" in canonical_dict


# ============================================================================
# 4. ORM and Analytics Compatibility Tests
# ============================================================================


def test_ingest_schema_to_session_telemetry_compatibility() -> None:
    """Ensure SessionTelemetry derived from schema executes analytics correctly."""
    session = ReadingSessionIngest.model_validate(
        _make_valid_payload_dict(
            words_attempted=100,
            words_correct=92,
            target_word_count=100,
            active_duration_ms=240000,
            total_duration_ms=300000,
            hesitation_count=3,
            total_pause_duration_ms=40000,
            pause_count=4,
        )
    )

    telemetry = session.to_session_telemetry()
    assert telemetry.session_start_time == session.session_start_time
    assert telemetry.words_attempted == 100
    assert telemetry.words_correct == 92
    assert telemetry.active_duration_ms == 240000

    # Execute deterministic analytics functions
    acc = calculate_reading_accuracy(telemetry.words_attempted, telemetry.words_correct)
    wpm = calculate_words_per_minute(telemetry.words_attempted, telemetry.active_duration_ms)
    hes = calculate_hesitation_frequency(
        telemetry.hesitation_count,
        telemetry.words_attempted,
        telemetry.active_duration_ms,
    )
    eng = calculate_experimental_engagement(telemetry)

    assert acc == 0.92
    assert wpm == 25.0
    assert hes is not None
    assert hes.hesitation_count == 3
    assert eng.score is not None
    assert 0.0 <= eng.score <= 1.0


def test_ingest_schema_to_orm_model_compatibility() -> None:
    session = ReadingSessionIngest.model_validate(_make_valid_payload_dict())
    digest = compute_canonical_session_digest(session)

    orm_instance = session.to_orm_model(
        request_digest=digest,
        calculated_accuracy=Decimal("0.9200"),
        calculated_wpm=Decimal("25.00"),
        calculated_hesitation_rate=Decimal("0.0300"),
        calculated_engagement_score=Decimal("0.8500"),
        engagement_formula_version="v0.1-research-heuristic",
    )

    assert isinstance(orm_instance, ReadingSession)
    assert orm_instance.learner_id == session.learner_id
    assert orm_instance.client_session_id == session.client_session_id
    assert orm_instance.request_digest == digest
    assert orm_instance.calculated_accuracy == Decimal("0.9200")
    assert orm_instance.calculated_wpm == Decimal("25.00")


def test_reading_session_response_from_orm() -> None:
    """Verify ReadingSessionResponse models round-trip from ReadingSession ORM instances."""
    session = ReadingSessionIngest.model_validate(_make_valid_payload_dict())
    digest = compute_canonical_session_digest(session)
    session_id = uuid4()

    orm_instance = session.to_orm_model(
        id=session_id,
        request_digest=digest,
        calculated_accuracy=Decimal("0.9200"),
        calculated_wpm=Decimal("25.00"),
        calculated_hesitation_rate=Decimal("0.0300"),
        calculated_engagement_score=Decimal("0.8500"),
        engagement_formula_version="v0.1-research-heuristic",
    )
    # Populate VersionedReadSchema mixin attributes
    now = datetime(2026, 10, 16, 11, 0, 0, tzinfo=UTC)
    orm_instance.created_at = now
    orm_instance.updated_at = now
    orm_instance.row_version = 1

    response = ReadingSessionResponse.model_validate(orm_instance)
    assert response.id == session_id
    assert response.learner_id == session.learner_id
    assert response.client_session_id == session.client_session_id
    assert response.request_digest == digest
    assert response.calculated_accuracy == Decimal("0.9200")
    assert response.calculated_wpm == Decimal("25.00")
    assert response.disclaimer == NON_CLINICAL_DISCLAIMER

    # Test nested metrics property extraction
    metrics = response.metrics
    assert isinstance(metrics, CalculatedMetricsResponse)
    assert metrics.calculated_accuracy == Decimal("0.9200")
    assert metrics.calculated_wpm == Decimal("25.00")
    assert metrics.disclaimer == NON_CLINICAL_DISCLAIMER

    # Test standalone CalculatedMetricsResponse direct from ORM instance
    direct_metrics = CalculatedMetricsResponse.model_validate(orm_instance)
    assert direct_metrics.calculated_accuracy == Decimal("0.9200")
    assert direct_metrics.calculated_wpm == Decimal("25.00")
    assert direct_metrics.disclaimer == NON_CLINICAL_DISCLAIMER
