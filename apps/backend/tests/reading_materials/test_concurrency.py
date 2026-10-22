"""Independent PostgreSQL connections exercise claims, leases, and authorization."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from queue import Queue
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth import repository as auth_repo
from app.modules.auth import service as auth_service
from app.modules.auth.models import AuthSession, Role, User, UserRole
from app.modules.learners.models import EducatorLearnerRelationship, LearnerProfile
from app.modules.reading_materials import pipeline, service
from app.modules.reading_materials import repository as repo
from app.modules.reading_materials.models import ReadingMaterial as Material
from app.modules.reading_materials.models import ReadingMaterialProcessingRun as Run
from app.modules.reading_materials.schemas import MaterialCreate, RevisionCreate

pytestmark = pytest.mark.integration


@pytest.fixture
def context(postgres_engine, password_hash, settings, request):
    identities = [uuid4(), uuid4()]
    learner_id = uuid4()
    with Session(postgres_engine) as db:
        for identity in identities:
            db.add(
                User(
                    id=identity,
                    login_handle="material_" + identity.hex,
                    password_hash=password_hash,
                    status="active",
                )
            )
        db.flush()
        role = db.scalar(select(Role).where(Role.code == "educator"))
        db.add(
            LearnerProfile(
                id=learner_id,
                display_name="Synthetic concurrency",
                created_by_user_id=identities[0],
            )
        )
        db.flush()
        expiry = auth_repo.now(db) + timedelta(seconds=getattr(request, "param", 86400))
        for identity in identities:
            db.add(UserRole(user_id=identity, role_id=role.id, granted_by_user_id=identity))
            db.add(
                EducatorLearnerRelationship(
                    educator_user_id=identity,
                    learner_id=learner_id,
                    access_level="instructor",
                    granted_by_user_id=identity,
                    expires_at=expiry,
                )
            )
        db.commit()
        principals = []
        for identity in identities:
            token = auth_service.login(
                db, settings, "material_" + identity.hex, "Synthetic accessible passphrase 42"
            )
            principals.append(auth_service.resolve_principal(db, settings, token.access_token))
        material = service.create(
            db,
            principals[0],
            learner_id,
            MaterialCreate(title="Synthetic", language_tag="en", text="A cat rests. A dog runs!"),
        )
    try:
        yield learner_id, material.id, material.latest_revision.id, principals, expiry
    finally:
        with Session(postgres_engine) as db:
            db.execute(
                text(
                    "TRUNCATE reading_material_sources, reading_material_extraction_runs, "
                    "reading_material_extraction_reviews, "
                    "reading_material_extraction_review_pages, "
                    "reading_material_extraction_pages, reading_material_sentence_features, "
                    "reading_material_processing_runs, "
                    "reading_material_revisions, reading_materials"
                )
            )
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


def wait_blocked(db, pid):
    deadline = monotonic() + 8
    while monotonic() < deadline:
        if db.scalar(text("SELECT cardinality(pg_blocking_pids(:pid))>0"), {"pid": pid}):
            return
        sleep(0.01)
    pytest.fail("Expected PostgreSQL lock wait")


def test_concurrent_revisions(postgres_engine, context):
    learner, material, _, actors, _ = context
    barrier = Barrier(2)

    def revise(index):
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout='8s'"))
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            barrier.wait(timeout=10)
            try:
                service.revise(
                    db,
                    actors[index],
                    learner,
                    material,
                    RevisionCreate(
                        row_version=1, title="Revised", language_tag="en", text="A bird flies."
                    ),
                )
                return pid, "success"
            except SecurityError as exc:
                return pid, exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(revise, i) for i in range(2)]
        values = [f.result(timeout=15) for f in results]
    assert len({pid for pid, _ in values}) == 2
    assert sorted(code for _, code in values) == ["success", "version_conflict"]
    with Session(postgres_engine) as db:
        assert repo.latest(db, material).revision_number == 2


def test_duplicate_processing_and_compute_has_no_authority_locks(
    postgres_engine, context, monkeypatch
):
    learner, material, revision, actors, _ = context
    entered, release = Event(), Event()
    original = pipeline.process

    def compute(source):
        entered.set()
        assert release.wait(timeout=10)
        return original(source)

    monkeypatch.setattr(pipeline, "process", compute)

    def process():
        with Session(postgres_engine) as db:
            return service.process(db, actors[0], learner, material, revision)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(process)
        try:
            assert entered.wait(timeout=5)
            with Session(postgres_engine) as db:
                # A separate connection can acquire the auth/domain locks while CPU work runs.
                db.execute(text("SET LOCAL lock_timeout='1s'"))
                db.scalar(select(User).where(User.id == actors[0].user_id).with_for_update())
                db.scalar(
                    select(LearnerProfile).where(LearnerProfile.id == learner).with_for_update()
                )
                db.rollback()
                with pytest.raises(SecurityError) as exc:
                    service.process(db, actors[1], learner, material, revision)
                assert exc.value.code == "processing_conflict"
        finally:
            release.set()
        assert future.result(timeout=15)[1] == 201
    with Session(postgres_engine) as db:
        assert service.process(db, actors[1], learner, material, revision)[1] == 200


def test_expired_attempt_recovery_rejects_late_publication(postgres_engine, context, monkeypatch):
    learner, material, revision, actors, _ = context
    monkeypatch.setattr(pipeline, "LEASE_SECONDS", 1)
    with Session(postgres_engine) as db:
        old = service.claim(db, actors[0], learner, material, revision)
        deadline = db.get(Run, old.id).lease_expires_at
        db.rollback()
        while repo.now(db) <= deadline:
            sleep(0.02)
        db.rollback()
        replacement = service.claim(db, actors[1], learner, material, revision)
        assert replacement.id != old.id
        output = pipeline.process(replacement.source)
        service.publish(db, actors[1], learner, material, revision, replacement, output)
        with pytest.raises(SecurityError) as exc:
            service.publish(db, actors[0], learner, material, revision, old, output)
        assert exc.value.code == "processing_conflict"
        assert db.get(Run, old.id).failure_code == "processing_interrupted"
        assert db.get(Run, replacement.id).status == "succeeded"


@pytest.mark.parametrize("context", [3], indirect=True)
def test_educator_expiry_after_material_lock_wait(postgres_engine, context):
    learner, material, revision, actors, expiry = context
    pids = Queue()

    def claim():
        with Session(postgres_engine) as db:
            pids.put(db.scalar(text("SELECT pg_backend_pid()")))
            try:
                service.claim(db, actors[0], learner, material, revision)
            except SecurityError as exc:
                return exc.code

    with Session(postgres_engine) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.scalar(select(Material).where(Material.id == material).with_for_update())
        future = pool.submit(claim)
        wait_blocked(blocker, pids.get(timeout=5))
        while repo.now(blocker) <= expiry:
            sleep(0.02)
        blocker.commit()
        assert future.result(timeout=10) == "not_found"


@pytest.mark.parametrize("change", ["relationship", "archive", "account", "session"])
def test_publication_rechecks_authority_after_compute(postgres_engine, context, change):
    learner, material, revision, actors, _ = context
    with Session(postgres_engine) as db:
        work = service.claim(db, actors[0], learner, material, revision)
    with Session(postgres_engine) as other:
        if change == "relationship":
            r = other.scalar(
                select(EducatorLearnerRelationship).where(
                    EducatorLearnerRelationship.learner_id == learner,
                    EducatorLearnerRelationship.educator_user_id == actors[0].user_id,
                )
            )
            r.revoked_at, r.revoked_by_user_id = repo.now(other), actors[0].user_id
        elif change == "archive":
            other.get(LearnerProfile, learner).archived_at = repo.now(other)
        elif change == "account":
            other.get(User, actors[0].user_id).status = "disabled"
        else:
            session = other.get(AuthSession, actors[0].session_id)
            session.revoked_at, session.revocation_reason = repo.now(other), "logout"
        other.commit()
    with Session(postgres_engine) as db:
        with pytest.raises(SecurityError) as exc:
            service.publish(
                db, actors[0], learner, material, revision, work, pipeline.process(work.source)
            )
        assert exc.value.code == (
            "authentication_required" if change in {"account", "session"} else "not_found"
        )
        assert db.get(Run, work.id).status == "running"
