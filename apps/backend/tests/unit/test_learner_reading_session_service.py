"""Unit tests for reading-session service, authorization, consent, and idempotency.

Verifies:
- Default fail-closed consent behavior denies persistence when consent interface is missing.
- Consent denial or withdrawal denies persistence.
- Action-scoped authorization gating precedes data access.
- Successful ingestion only when an approved test consent checker permits it.
- Deterministic idempotency: identical retries return existing session without recalculating.
- Conflicting retries raise 409 digest_conflict.
- Concurrent insert conflicts recover safely via savepoints.
- Unrelated integrity errors are never masked.
- Repositories and service never commit autonomously.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.learner_modelling import repository as repo
from app.modules.learner_modelling.models import ReadingSession
from app.modules.learner_modelling.schemas import (
    ReadingSessionIngest,
    compute_canonical_session_digest,
)
from app.modules.learner_modelling.service import (
    CONSENT_PURPOSE_LEARNING_SUPPORT,
    ingest_reading_session,
)


def _make_principal(
    user_id: UUID | None = None,
    roles: frozenset[str] = frozenset({"learner"}),
    status: str = "active",
) -> Principal:
    """Generate an immutable synthetic test principal."""
    now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC)
    return Principal(
        user_id=user_id or uuid4(),
        login_handle="synthetic_learner",
        roles=roles,
        session_id=uuid4(),
        authenticated_at=now,
        token_id=uuid4(),
        issued_at=now,
        expires_at=now + datetime.resolution,
        status=status,  # type: ignore[arg-type]
    )


def _make_ingest_payload(
    learner_id: UUID | None = None,
    client_session_id: UUID | None = None,
    **overrides: object,
) -> ReadingSessionIngest:
    """Generate a valid synthetic ReadingSessionIngest payload."""
    start_time = datetime(2026, 10, 16, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2026, 10, 16, 10, 5, 0, tzinfo=UTC)
    data: dict[str, object] = {
        "learner_id": str(learner_id or uuid4()),
        "client_session_id": str(client_session_id or uuid4()),
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
    data.update(overrides)
    return ReadingSessionIngest.model_validate(data)


# ============================================================================
# 1. Consent Gating and Fail-Closed Tests
# ============================================================================


def test_missing_consent_dependency_denies_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default service call without approved consent checker must fail closed with 403."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    principal = _make_principal(user_id=learner_id)
    payload = _make_ingest_payload(learner_id=learner_id)

    # Mock auth and authorization to succeed
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        lambda _db, _p, _lid, _act: MagicMock(),
    )

    with pytest.raises(SecurityError) as exc_info:
        ingest_reading_session(db, principal, payload)

    assert exc_info.value.status == 403
    assert exc_info.value.code == "consent_required"
    # Ensure no repository write or flush was invoked
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_consent_denial_denies_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    """An injected consent checker that rejects consent must abort ingestion before writes."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    principal = _make_principal(user_id=learner_id)
    payload = _make_ingest_payload(learner_id=learner_id)

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        lambda _db, _p, _lid, _act: MagicMock(),
    )

    def rejecting_consent_checker(_db: Session, _lid: UUID, purpose: str) -> None:
        assert purpose == CONSENT_PURPOSE_LEARNING_SUPPORT
        raise SecurityError(403, "consent_denied", "Consent not granted for learning_support")

    with pytest.raises(SecurityError) as exc_info:
        ingest_reading_session(db, principal, payload, consent_checker=rejecting_consent_checker)

    assert exc_info.value.status == 403
    assert exc_info.value.code == "consent_denied"
    db.add.assert_not_called()


# ============================================================================
# 2. Authorization and Protected Write Tests
# ============================================================================


def test_inactive_principal_denies_persistence() -> None:
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    principal = _make_principal(user_id=learner_id, status="suspended")
    payload = _make_ingest_payload(learner_id=learner_id)

    with pytest.raises(SecurityError) as exc_info:
        ingest_reading_session(db, principal, payload)

    assert exc_info.value.status == 401
    assert exc_info.value.code == "authentication_required"


def test_authorization_failure_denies_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lacking action-scoped authority on the learner profile aborts before consent or queries."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    other_user_id = uuid4()
    principal = _make_principal(user_id=other_user_id)
    payload = _make_ingest_payload(learner_id=learner_id)

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )

    def failing_authorize(_db: Session, _p: Principal, _lid: UUID, _act: object) -> None:
        raise SecurityError(404, "not_found", "Resource not found")

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        failing_authorize,
    )

    consent_mock = MagicMock()
    with pytest.raises(SecurityError) as exc_info:
        ingest_reading_session(db, principal, payload, consent_checker=consent_mock)

    assert exc_info.value.status == 404
    # Consent was never evaluated because authorization failed first
    consent_mock.assert_not_called()
    db.add.assert_not_called()


def test_no_unauthorized_reading_of_existing_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Possession of client_session_id does not disclose existing session without authority."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    unauthorized_principal = _make_principal(user_id=uuid4())
    payload = _make_ingest_payload(learner_id=learner_id)

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        MagicMock(side_effect=SecurityError(404, "not_found", "Resource not found")),
    )

    get_session_mock = MagicMock()
    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.get_session_by_client_id", get_session_mock
    )

    with pytest.raises(SecurityError) as exc_info:
        ingest_reading_session(db, unauthorized_principal, payload, consent_checker=MagicMock())

    assert exc_info.value.status == 404
    # Repository was never queried for the existing session
    get_session_mock.assert_not_called()


# ============================================================================
# 3. Successful Ingestion, Analytics, and Idempotency Tests
# ============================================================================


def test_successful_processing_with_approved_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    """When authorization and approved consent pass, session is persisted with analytics."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    principal = _make_principal(user_id=learner_id)
    payload = _make_ingest_payload(
        learner_id=learner_id,
        words_attempted=100,
        words_correct=92,
        active_duration_ms=240000,
        total_duration_ms=300000,
        hesitation_count=3,
    )

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        lambda _db, _p, _lid, _act: MagicMock(),
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.assert_protected_session_live",
        lambda _db, _p: None,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.get_session_by_client_id",
        lambda _db, _lid, _csid, lock=False: None,
    )

    inserted_records: list[ReadingSession] = []

    def fake_insert(_db: Session, session: ReadingSession) -> ReadingSession:
        inserted_records.append(session)
        return session

    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.insert_reading_session",
        fake_insert,
    )

    approved_consent_checker = MagicMock()
    session, is_new = ingest_reading_session(
        db, principal, payload, consent_checker=approved_consent_checker
    )

    approved_consent_checker.assert_called_once_with(
        db, payload.learner_id, CONSENT_PURPOSE_LEARNING_SUPPORT
    )
    assert is_new is True
    assert len(inserted_records) == 1
    assert session.learner_id == payload.learner_id
    assert session.client_session_id == payload.client_session_id
    assert session.request_digest == compute_canonical_session_digest(payload)
    assert session.calculated_accuracy == Decimal("0.9200")
    assert session.calculated_wpm == Decimal("25.00")
    assert session.calculated_hesitation_rate == Decimal("0.0300")
    assert session.calculated_engagement_score is not None
    assert session.engagement_formula_version == "v0.1-research-heuristic"

    # Verify no autonomous commit was issued
    db.commit.assert_not_called()


def test_identical_retries_return_existing_session_without_recalculation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Idempotent retry with identical canonical digest returns existing row without writing."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    client_session_id = uuid4()
    principal = _make_principal(user_id=learner_id)
    payload = _make_ingest_payload(learner_id=learner_id, client_session_id=client_session_id)
    digest = compute_canonical_session_digest(payload)

    existing_orm = payload.to_orm_model(
        request_digest=digest,
        calculated_accuracy=Decimal("0.9200"),
        calculated_wpm=Decimal("25.00"),
    )

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        lambda _db, _p, _lid, _act: MagicMock(),
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.assert_protected_session_live",
        lambda _db, _p: None,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.get_session_by_client_id",
        lambda _db, _lid, _csid, lock=False: existing_orm,
    )

    insert_mock = MagicMock()
    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.insert_reading_session", insert_mock
    )

    session, is_new = ingest_reading_session(
        db, principal, payload, consent_checker=lambda _d, _l, _p: None
    )

    assert is_new is False
    assert session is existing_orm
    insert_mock.assert_not_called()
    db.add.assert_not_called()


def test_conflicting_retries_raise_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """Submitting different data for an existing client_session_id raises 409 digest_conflict."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    client_session_id = uuid4()
    principal = _make_principal(user_id=learner_id)
    payload = _make_ingest_payload(learner_id=learner_id, client_session_id=client_session_id)

    # Existing session has a different digest
    existing_orm = payload.to_orm_model(
        request_digest="0" * 64,
        calculated_accuracy=Decimal("0.9200"),
    )

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        lambda _db, _p, _lid, _act: MagicMock(),
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.assert_protected_session_live",
        lambda _db, _p: None,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.get_session_by_client_id",
        lambda _db, _lid, _csid, lock=False: existing_orm,
    )

    with pytest.raises(SecurityError) as exc_info:
        ingest_reading_session(db, principal, payload, consent_checker=lambda _d, _l, _p: None)

    assert exc_info.value.status == 409
    assert exc_info.value.code == "digest_conflict"


def test_concurrent_insert_savepoint_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concurrent race condition recovers via savepoint rollback and returns winner's row."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    client_session_id = uuid4()
    principal = _make_principal(user_id=learner_id)
    payload = _make_ingest_payload(learner_id=learner_id, client_session_id=client_session_id)
    digest = compute_canonical_session_digest(payload)

    winner_orm = payload.to_orm_model(request_digest=digest)

    # Initial check returned None (both requests raced past initial SELECT)
    query_count = 0

    def fake_get(
        _db: Session, _lid: UUID, _csid: UUID, lock: bool = False
    ) -> ReadingSession | None:
        nonlocal query_count
        query_count += 1
        if query_count == 1:
            return None
        return winner_orm

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        lambda _db, _p, _lid, _act: MagicMock(),
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.assert_protected_session_live",
        lambda _db, _p: None,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.get_session_by_client_id", fake_get
    )

    # Simulate IntegrityError on insert
    orig_error = Exception()
    orig_error.diag = MagicMock(constraint_name="uq_reading_sessions_client_session")  # type: ignore[attr-defined]
    integrity_error = IntegrityError("duplicate key", params={}, orig=orig_error)

    def failing_insert(_db: Session, _s: ReadingSession) -> ReadingSession:
        raise integrity_error

    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.insert_reading_session", failing_insert
    )

    session, is_new = ingest_reading_session(
        db, principal, payload, consent_checker=lambda _d, _l, _p: None
    )

    assert is_new is False
    assert session is winner_orm
    assert query_count == 2


def test_unrelated_integrity_error_is_not_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unrelated database errors (e.g., check constraints) are re-raised without masking."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    principal = _make_principal(user_id=learner_id)
    payload = _make_ingest_payload(learner_id=learner_id)

    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write",
        lambda _db, p: p,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action",
        lambda _db, _p, _lid, _act: MagicMock(),
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.assert_protected_session_live",
        lambda _db, _p: None,
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.get_session_by_client_id",
        lambda _db, _l, _c, lock=False: None,
    )

    orig_error = Exception()
    orig_error.diag = MagicMock(constraint_name="ck_unrelated_constraint")  # type: ignore[attr-defined]
    check_error = IntegrityError("check violation", params={}, orig=orig_error)

    monkeypatch.setattr(
        "app.modules.learner_modelling.repository.insert_reading_session",
        MagicMock(side_effect=check_error),
    )

    with pytest.raises(IntegrityError):
        ingest_reading_session(db, principal, payload, consent_checker=lambda _d, _l, _p: None)


# ============================================================================
# 4. Repository Method Invariants
# ============================================================================


def test_repository_methods_never_commit() -> None:
    """Verify repository functions use session.add/flush and never call session.commit."""
    db = MagicMock(spec=Session)
    learner_id = uuid4()
    client_session_id = uuid4()

    repo.get_session_by_client_id(db, learner_id, client_session_id)
    db.commit.assert_not_called()

    payload = _make_ingest_payload(learner_id=learner_id, client_session_id=client_session_id)
    orm_instance = payload.to_orm_model(request_digest="a" * 64)

    result = repo.insert_reading_session(db, orm_instance)
    assert result is orm_instance
    db.add.assert_called_once_with(orm_instance)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"words_attempted": 1000000, "words_correct": 0, "active_duration_ms": 1000},
        {"words_attempted": 1, "words_correct": 1, "hesitation_count": 100},
    ],
)
def test_unrepresentable_metrics_fail_before_database_write(monkeypatch, overrides):
    """Storage limits are not educational thresholds; never clamp or invent values."""
    db = MagicMock(spec=Session)
    principal = _make_principal()
    payload = _make_ingest_payload(**overrides)
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write", lambda db, p: p
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action", lambda *a: None
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.assert_protected_session_live", lambda *a: None
    )
    monkeypatch.setattr(repo, "get_session_by_client_id", lambda *a, **k: None)
    insert = MagicMock()
    monkeypatch.setattr(repo, "insert_reading_session", insert)
    with pytest.raises(SecurityError) as error:
        ingest_reading_session(db, principal, payload, consent_checker=lambda *a: None)
    assert error.value.status == 422
    assert error.value.code == "measurement_out_of_range"
    insert.assert_not_called()
    db.begin_nested.assert_not_called()


def test_unexpected_consent_failure_is_sanitized_before_repository_access(monkeypatch):
    db = MagicMock(spec=Session)
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write", lambda db, p: p
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action", lambda *a: None
    )
    read = MagicMock()
    monkeypatch.setattr(repo, "get_session_by_client_id", read)

    def unavailable(*args):
        raise RuntimeError("private consent provider details")

    with pytest.raises(SecurityError) as error:
        ingest_reading_session(
            db, _make_principal(), _make_ingest_payload(), consent_checker=unavailable
        )
    assert error.value.status == 503
    assert "private" not in str(error.value)
    read.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize(
    "overrides, expected_wpm, expected_hesitation",
    [
        (
            {"words_attempted": 99999, "words_correct": 0, "active_duration_ms": 60000},
            Decimal("99999.00"),
            Decimal("0.0000"),
        ),
        (
            {"words_attempted": 1, "words_correct": 1, "hesitation_count": 99},
            Decimal("0.25"),
            Decimal("99.0000"),
        ),
    ],
)
def test_representable_large_metrics_are_not_clamped(
    monkeypatch, overrides, expected_wpm, expected_hesitation
):
    db = MagicMock(spec=Session)
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.protect_principal_for_write", lambda db, p: p
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.authorize_learner_action", lambda *a: None
    )
    monkeypatch.setattr(
        "app.modules.learner_modelling.service.assert_protected_session_live", lambda *a: None
    )
    monkeypatch.setattr(repo, "get_session_by_client_id", lambda *a, **k: None)
    insert = MagicMock()
    monkeypatch.setattr(repo, "insert_reading_session", insert)
    payload = _make_ingest_payload(**{**{"hesitation_count": 0}, **overrides})
    record, created = ingest_reading_session(
        db, _make_principal(), payload, consent_checker=lambda *a: None
    )
    assert created
    assert record.calculated_wpm == expected_wpm
    assert record.calculated_hesitation_rate == expected_hesitation
    insert.assert_called_once()
    db.commit.assert_not_called()
