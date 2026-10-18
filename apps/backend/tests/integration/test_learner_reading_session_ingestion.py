"""PostgreSQL 17 integration tests for reading-session ingestion service.

Verifies real database persistence, constraint enforcement, savepoint recovery,
and distinction between production fail-closed consent and simulated test approval.
"""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import SecurityError
from app.modules.auth import service as auth_service
from app.modules.auth.contracts import Principal
from app.modules.auth.models import AuthSession, Role, User, UserRole
from app.modules.learner_modelling import repository as repo
from app.modules.learner_modelling import service
from app.modules.learner_modelling.models import ReadingSession
from app.modules.learner_modelling.schemas import ReadingSessionIngest
from app.modules.learners.models import LearnerProfile

pytestmark = pytest.mark.integration


@pytest.fixture
def learner_environment(
    postgres_engine: Engine, password_hash: str, settings: Settings
) -> Iterator[tuple[UUID, Principal]]:
    user_id = uuid4()
    learner_id = uuid4()
    with Session(postgres_engine) as db:
        user = User(
            id=user_id,
            login_handle="session_learner_" + user_id.hex[:12],
            status="active",
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()

        role = db.scalar(select(Role).where(Role.code == "learner"))
        assert role is not None
        db.add(UserRole(user_id=user_id, role_id=role.id, granted_by_user_id=user_id))

        profile = LearnerProfile(
            id=learner_id,
            learner_user_id=user_id,
            display_name="Synthetic Reading Learner",
            created_by_user_id=user_id,
        )
        db.add(profile)
        db.commit()

        assert user.login_handle is not None
        tokens = auth_service.login(
            db, settings, user.login_handle, "Synthetic accessible passphrase 42"
        )
        principal = auth_service.resolve_principal(db, settings, tokens.access_token)

    try:
        yield learner_id, principal
    finally:
        with Session(postgres_engine) as db:
            db.execute(delete(ReadingSession).where(ReadingSession.learner_id == learner_id))
            db.execute(delete(LearnerProfile).where(LearnerProfile.id == learner_id))
            db.execute(delete(UserRole).where(UserRole.user_id == user_id))
            db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id))
            db.commit()


def _make_ingest_payload(
    learner_id: UUID, client_session_id: UUID | None = None
) -> ReadingSessionIngest:
    start_time = datetime(2026, 10, 16, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2026, 10, 16, 10, 5, 0, tzinfo=UTC)
    return ReadingSessionIngest.model_validate(
        {
            "learner_id": str(learner_id),
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
    )


def test_missing_consent_fails_closed_in_postgres(
    postgres_engine: Engine, learner_environment: tuple[UUID, Principal]
) -> None:
    learner_id, principal = learner_environment
    payload = _make_ingest_payload(learner_id)

    with Session(postgres_engine) as db:
        with pytest.raises(SecurityError) as exc_info:
            # Default production service call without approved consent checker
            service.ingest_reading_session(db, principal, payload)

        assert exc_info.value.status == 403
        assert exc_info.value.code == "consent_required"

        # Ensure no row was persisted in PostgreSQL
        stored = repo.get_session_by_client_id(db, learner_id, payload.client_session_id)
        assert stored is None


def test_simulated_approved_consent_persists_session(
    postgres_engine: Engine, learner_environment: tuple[UUID, Principal]
) -> None:
    learner_id, principal = learner_environment
    payload = _make_ingest_payload(learner_id)

    def simulated_test_consent(_db: Session, lid: UUID, purpose: str) -> None:
        assert lid == learner_id
        assert purpose == "learning_support"

    with Session(postgres_engine) as db:
        session, is_new = service.ingest_reading_session(
            db, principal, payload, consent_checker=simulated_test_consent
        )
        assert is_new is True
        accuracy = session.calculated_accuracy
        wpm = session.calculated_wpm
        hesitation = session.calculated_hesitation_rate
        engagement = session.calculated_engagement_score
        db.commit()

    with Session(postgres_engine) as db:
        stored = repo.get_session_by_client_id(db, learner_id, payload.client_session_id)
        assert stored is not None
        assert stored.words_attempted == 100
        assert stored.words_correct == 92
        assert stored.calculated_accuracy == accuracy
        assert stored.calculated_wpm == wpm
        assert stored.calculated_hesitation_rate == hesitation
        assert stored.calculated_engagement_score == engagement


def test_uncommitted_ingestion_is_removed_by_caller_rollback(
    postgres_engine: Engine, learner_environment: tuple[UUID, Principal]
) -> None:
    learner_id, principal = learner_environment
    payload = _make_ingest_payload(learner_id)

    def allow_synthetic_consent(_db: Session, lid: UUID, purpose: str) -> None:
        assert lid == learner_id
        assert purpose == "learning_support"

    with Session(postgres_engine) as db:
        stored, is_new = service.ingest_reading_session(
            db,
            principal,
            payload,
            consent_checker=allow_synthetic_consent,
        )

        assert is_new is True
        assert stored.client_session_id == payload.client_session_id
        assert db.in_transaction()
        assert repo.get_session_by_client_id(db, learner_id, payload.client_session_id) is not None
        db.rollback()

    with Session(postgres_engine) as fresh_db:
        assert (
            repo.get_session_by_client_id(
                fresh_db,
                learner_id,
                payload.client_session_id,
            )
            is None
        )


def test_idempotent_replay_and_conflict_in_postgres(
    postgres_engine: Engine, learner_environment: tuple[UUID, Principal]
) -> None:
    learner_id, principal = learner_environment
    client_session_id = uuid4()
    payload = _make_ingest_payload(learner_id, client_session_id)

    def allow_consent(_db: Session, _l: UUID, _p: str) -> None:
        pass

    with Session(postgres_engine) as db:
        s1, is_new1 = service.ingest_reading_session(
            db, principal, payload, consent_checker=allow_consent
        )
        assert is_new1 is True
        s1_id = s1.id
        db.commit()

    # Identical replay returns existing without error or duplicate row
    with Session(postgres_engine) as db:
        s2, is_new2 = service.ingest_reading_session(
            db, principal, payload, consent_checker=allow_consent
        )
        assert is_new2 is False
        assert s2.id == s1_id

    # Conflicting replay raises 409
    conflicting_payload = _make_ingest_payload(learner_id, client_session_id)
    # Alter a meaningful field
    conflicting_dict = conflicting_payload.model_dump()
    conflicting_dict["words_attempted"] = 120
    conflicting_dict["words_correct"] = 100
    conflicting_payload = ReadingSessionIngest.model_validate(conflicting_dict)

    with Session(postgres_engine) as db:
        with pytest.raises(SecurityError) as exc_info:
            service.ingest_reading_session(
                db, principal, conflicting_payload, consent_checker=allow_consent
            )
        assert exc_info.value.status == 409
        assert exc_info.value.code == "digest_conflict"


def test_concurrent_idempotent_inserts_race_safety(
    postgres_engine: Engine, learner_environment: tuple[UUID, Principal]
) -> None:
    """Two concurrent threads inserting the same client_session_id both succeed with 1 row."""
    learner_id, principal = learner_environment
    client_session_id = uuid4()
    payload = _make_ingest_payload(learner_id, client_session_id)
    barrier = Barrier(2)

    def worker(idx: int) -> tuple[UUID, bool]:
        with Session(postgres_engine) as db:
            barrier.wait(timeout=5)
            session, is_new = service.ingest_reading_session(
                db, principal, payload, consent_checker=lambda _d, _l, _p: None
            )
            db.commit()
            return session.id, is_new

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker, 0)
        f2 = executor.submit(worker, 1)
        r1 = f1.result(timeout=10)
        r2 = f2.result(timeout=10)

    # Both got the same session ID
    assert r1[0] == r2[0]
    # Exactly one was newly persisted
    assert {r1[1], r2[1]} == {True, False}

    # Exactly 1 row in the database
    with Session(postgres_engine) as db:
        rows = db.scalars(
            select(ReadingSession).where(
                ReadingSession.learner_id == learner_id,
                ReadingSession.client_session_id == client_session_id,
            )
        ).all()
        assert len(rows) == 1
