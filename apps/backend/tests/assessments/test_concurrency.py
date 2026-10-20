"""Independent committed PostgreSQL connections: no mocked persistence or SQLite."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from queue import Queue
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.assessments import repository as repo
from app.modules.assessments import service
from app.modules.assessments.models import (
    ReadingAssessmentMaterial as Material,
)
from app.modules.assessments.models import (
    ReadingAssessmentResult as Result,
)
from app.modules.assessments.models import (
    ReadingAssessmentSession as Assessment,
)
from app.modules.assessments.schemas import (
    AssessmentAbandonRequest,
    AssessmentCompletionRequest,
    AssessmentStartRequest,
)
from app.modules.auth import repository as auth_repo
from app.modules.auth import service as auth_service
from app.modules.auth.models import AuthSession, Role, User, UserRole
from app.modules.learners.models import EducatorLearnerRelationship, LearnerProfile

pytestmark = pytest.mark.integration


@pytest.fixture
def race_context(postgres_engine, password_hash, settings, request):
    identities = [uuid4(), uuid4()]
    learner_id, material_id = uuid4(), uuid4()
    with Session(postgres_engine) as db:
        for identity in identities:
            db.add(
                User(
                    id=identity,
                    login_handle="reading_race_" + identity.hex,
                    status="active",
                    password_hash=password_hash,
                )
            )
        db.flush()
        role = db.scalar(select(Role).where(Role.code == "educator"))
        role_id = role.id
        db.add(
            LearnerProfile(
                id=learner_id, display_name="Synthetic race", created_by_user_id=identities[0]
            )
        )
        db.add(
            Material(
                id=material_id,
                code="race_" + material_id.hex,
                version=1,
                title="Synthetic",
                language_tag="en",
                passage_text="One two three four five six seven eight nine ten.",
                word_count=10,
                tokenization_version="synthetic-whitespace-v1",
                administration_instructions="Read once, time reading only.",
                comprehension_question_count=0,
            )
        )
        db.flush()
        expiry = auth_repo.now(db) + timedelta(seconds=getattr(request, "param", 86400))
        for identity in identities:
            db.add(UserRole(user_id=identity, role_id=role_id, granted_by_user_id=identity))
            db.add(
                EducatorLearnerRelationship(
                    educator_user_id=identity,
                    learner_id=learner_id,
                    granted_by_user_id=identity,
                    access_level="instructor",
                    expires_at=expiry,
                )
            )
        db.commit()
        principals = []
        for identity in identities:
            token = auth_service.login(
                db, settings, "reading_race_" + identity.hex, "Synthetic accessible passphrase 42"
            )
            principals.append(auth_service.resolve_principal(db, settings, token.access_token))
    try:
        yield learner_id, material_id, principals, expiry
    finally:
        with Session(postgres_engine) as db:
            # Explicit disposable test database only; production has no truncation path.
            db.execute(
                text(
                    "TRUNCATE reading_assessment_results, reading_assessment_sessions, "
                    "reading_assessment_materials"
                )
            )
            db.get(Role, role_id).is_active = True
            db.execute(
                delete(EducatorLearnerRelationship).where(
                    EducatorLearnerRelationship.learner_id == learner_id
                )
            )
            db.execute(delete(LearnerProfile).where(LearnerProfile.id == learner_id))
            db.execute(delete(UserRole).where(UserRole.user_id.in_(identities)))
            db.execute(delete(AuthSession).where(AuthSession.user_id.in_(identities)))
            db.execute(delete(User).where(User.id.in_(identities)))
            db.commit()


def started(engine, context):
    learner_id, material_id, principals, _ = context
    with Session(engine) as db:
        return service.start(
            db, principals[0], learner_id, AssessmentStartRequest(material_id=material_id)
        )


def blocked(db, pid):
    deadline = monotonic() + 8
    while monotonic() < deadline:
        if db.scalar(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid}):
            return
        sleep(0.01)
    pytest.fail("Expected PostgreSQL lock wait")


@pytest.mark.parametrize("race", ["start/start", "complete/complete", "complete/abandon"])
def test_lifecycle_races(postgres_engine, race_context, observations, race):
    learner_id, material_id, principals, _ = race_context
    row = None if race == "start/start" else started(postgres_engine, race_context)
    barrier = Barrier(2)

    def attempt(index):
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout='8s'"))
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            barrier.wait(timeout=10)
            try:
                if row is None:
                    result = service.start(
                        db,
                        principals[0],
                        learner_id,
                        AssessmentStartRequest(material_id=material_id),
                    )
                else:
                    payload = (
                        AssessmentAbandonRequest(row_version=1)
                        if (race == "complete/abandon" and index == 1)
                        else AssessmentCompletionRequest(**observations)
                    )
                    result = service.finish(db, principals[0], learner_id, row.id, payload)
                return pid, result.status
            except SecurityError as exc:
                return pid, exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, index) for index in range(2)]
        outcomes = [future.result(timeout=15) for future in futures]
    assert len({pid for pid, _ in outcomes}) == 2
    codes = [code for _, code in outcomes]
    assert (
        codes.count("assessment_start_conflict" if row is None else "assessment_state_conflict")
        == 1
    )
    with Session(postgres_engine) as db:
        sessions = list(db.scalars(select(Assessment).where(Assessment.learner_id == learner_id)))
        assert len(sessions) == 1
        results = list(db.scalars(select(Result).where(Result.session_id == sessions[0].id)))
        assert len(results) == (1 if sessions[0].status == "completed" else 0)


@pytest.mark.parametrize("operation", ["complete", "abandon"])
def test_other_instructor_cannot_finish_or_get_rubric(
    postgres_engine, race_context, observations, operation
):
    row = started(postgres_engine, race_context)
    learner_id, _, principals, _ = race_context
    with Session(postgres_engine) as db:
        detail = service.read_assessment(db, principals[1], learner_id, row.id)
        assert "passage_text" not in detail.model_dump()["material"]
        with pytest.raises(SecurityError) as exc:
            service.finish(
                db,
                principals[1],
                learner_id,
                row.id,
                AssessmentCompletionRequest(**observations)
                if operation == "complete"
                else AssessmentAbandonRequest(row_version=1),
            )
        assert exc.value.code == "not_found"


@pytest.mark.parametrize("race_context", [4], indirect=True)
@pytest.mark.parametrize("deadline", ["educator", "auth"])
def test_expiry_after_session_lock_wait(postgres_engine, race_context, observations, deadline):
    row = started(postgres_engine, race_context)
    learner_id, _, principals, expiry = race_context
    principal = replace(principals[0], expires_at=expiry) if deadline == "auth" else principals[0]
    pids = Queue()

    def write():
        with Session(postgres_engine) as db:
            pids.put(db.scalar(text("SELECT pg_backend_pid()")))
            try:
                service.finish(
                    db, principal, learner_id, row.id, AssessmentCompletionRequest(**observations)
                )
            except SecurityError as exc:
                return exc.code

    with Session(postgres_engine) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.scalar(select(Assessment).where(Assessment.id == row.id).with_for_update())
        future = pool.submit(write)
        blocked(blocker, pids.get(timeout=5))
        while auth_repo.now(blocker) <= expiry:
            sleep(0.02)
        blocker.commit()
        assert future.result(timeout=10) == (
            "authentication_required" if deadline == "auth" else "not_found"
        )
    with Session(postgres_engine) as db:
        assert db.get(Assessment, row.id).status == "started"
        assert repo.result(db, row.id) is None


def revoke(db, context, case):
    learner_id, _, principals, _ = context
    actor = principals[0]
    now = auth_repo.now(db)
    if case == "relationship":
        row = db.scalar(
            select(EducatorLearnerRelationship).where(
                EducatorLearnerRelationship.learner_id == learner_id,
                EducatorLearnerRelationship.educator_user_id == actor.user_id,
            )
        )
        row.revoked_at, row.revoked_by_user_id = now, actor.user_id
    elif case == "archive":
        db.get(LearnerProfile, learner_id).archived_at = now
    elif case == "role":
        db.scalar(select(Role).where(Role.code == "educator")).is_active = False
    elif case == "assignment":
        row = db.scalar(select(UserRole).where(UserRole.user_id == actor.user_id))
        row.revoked_at, row.revoked_by_user_id = now, actor.user_id
    elif case == "account":
        db.get(User, actor.user_id).status = "disabled"
    else:
        row = db.get(AuthSession, actor.session_id)
        row.revoked_at, row.revocation_reason = now, "logout"
    db.flush()


@pytest.mark.parametrize(
    "case", ["relationship", "archive", "role", "assignment", "account", "session"]
)
@pytest.mark.parametrize("write_first", [True, False])
def test_authority_locks_until_commit(
    postgres_engine, race_context, observations, monkeypatch, case, write_first
):
    row = started(postgres_engine, race_context)
    learner_id, _, principals, _ = race_context
    pids = Queue()
    saving, release = Event(), Event()
    original = repo.insert_result

    def pause(db, result):
        original(db, result)
        saving.set()
        assert release.wait(timeout=10)

    if write_first:
        monkeypatch.setattr(repo, "insert_result", pause)

    def write():
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout='10s'"))
            pids.put(db.scalar(text("SELECT pg_backend_pid()")))
            try:
                return service.finish(
                    db,
                    principals[0],
                    learner_id,
                    row.id,
                    AssessmentCompletionRequest(**observations),
                ).status
            except SecurityError as exc:
                return exc.code

    def revoker():
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout='10s'"))
            pids.put(db.scalar(text("SELECT pg_backend_pid()")))
            revoke(db, race_context, case)
            db.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        if write_first:
            writer = pool.submit(write)
            pids.get(timeout=5)
            try:
                assert saving.wait(timeout=5)
                other = pool.submit(revoker)
                with Session(postgres_engine) as observer:
                    blocked(observer, pids.get(timeout=5))
            finally:
                release.set()
            assert writer.result(timeout=15) == "completed"
            other.result(timeout=15)
        else:
            with Session(postgres_engine) as holder:
                revoke(holder, race_context, case)
                writer = pool.submit(write)
                blocked(holder, pids.get(timeout=5))
                holder.commit()
            assert writer.result(timeout=15) == (
                "authentication_required" if case in {"account", "session"} else "not_found"
            )
    with Session(postgres_engine) as db:
        assert db.get(Assessment, row.id).status == ("completed" if write_first else "started")
