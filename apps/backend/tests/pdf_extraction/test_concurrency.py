"""Committed synthetic identities and independent database connections."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import sleep
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.models import AuthSession, User
from app.modules.learners.models import EducatorLearnerRelationship, LearnerProfile
from app.modules.reading_materials import service as material_service
from app.modules.reading_materials.pdf import contracts, service
from app.modules.reading_materials.pdf.extractor import extract
from app.modules.reading_materials.pdf.models import ExtractionRun, Source
from app.modules.reading_materials.pdf.schemas import UploadMetadata
from app.modules.reading_materials.pdf.storage import LocalStorage
from app.modules.reading_materials.schemas import RevisionCreate

from .conftest import pdf_bytes

pytestmark = pytest.mark.integration


@pytest.fixture
def work(context, postgres_engine, tmp_path):
    learner, _, _, principals, _ = context
    storage = LocalStorage(tmp_path / "private")
    data = pdf_bytes()
    metadata = UploadMetadata(title="Synthetic PDF", language_tag="en", upload_request_id=uuid4())
    with Session(postgres_engine) as db, storage.store(data) as obj:
        claim = service.register(db, principals[0], learner, metadata, obj)
    return learner, principals, storage, claim, data, metadata


def test_duplicate_claim_and_source_binding(work, postgres_engine):
    learner, principals, storage, claim, data, _ = work
    with Session(postgres_engine) as db:
        with pytest.raises(SecurityError) as exc:
            service.claim(db, principals[1], learner, claim.source_id, None)
        assert exc.value.code == "extraction_conflict"
        result = service.finish(db, principals[0], learner, storage, claim)[0]
    with Session(postgres_engine) as db:
        repeated = service.claim(db, principals[1], learner, claim.source_id, None)
        assert repeated.id == result.id
        assert (
            db.scalar(select(Source.material_id).where(Source.id == claim.source_id))
            == result.material_id
        )
        assert (
            db.scalar(select(ExtractionRun.attempt_number).where(ExtractionRun.id == claim.run_id))
            == 1
        )


def test_expired_recovery_rejects_late_publisher(context, postgres_engine, tmp_path, monkeypatch):
    learner, _, _, principals, _ = context
    storage = LocalStorage(tmp_path / "private")
    data = pdf_bytes()
    metadata = UploadMetadata(title="Synthetic", language_tag="en", upload_request_id=uuid4())
    monkeypatch.setattr(contracts, "LEASE_SECONDS", 1)
    with Session(postgres_engine) as db, storage.store(data) as obj:
        old = service.register(db, principals[0], learner, metadata, obj)
    sleep(1.05)
    monkeypatch.setattr(contracts, "LEASE_SECONDS", 90)
    with Session(postgres_engine) as db:
        new = service.claim(db, principals[1], learner, old.source_id, None)
        assert new.run_id != old.run_id
        service.finish(db, principals[1], learner, storage, new)
    with Session(postgres_engine) as db:
        with pytest.raises(SecurityError) as exc:
            service.publish(db, principals[0], learner, old, extract(data))
        assert exc.value.code == "extraction_conflict"
        assert db.get(ExtractionRun, old.run_id).outcome_code == "extraction_interrupted"


@pytest.mark.parametrize("change", ["relationship", "learner", "session", "user", "source"])
def test_reauthorization_and_no_locks_during_child(work, postgres_engine, monkeypatch, change):
    learner, principals, storage, claim, data, _ = work
    entered = Event()
    resume = Event()

    def paused(stream, digest, size):
        entered.set()
        assert resume.wait(10)
        return extract(data)

    monkeypatch.setattr(service.runner, "run", paused)

    def finish():
        with Session(postgres_engine) as db:
            try:
                service.finish(db, principals[0], learner, storage, claim)
            except SecurityError as exc:
                return exc.status

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(finish)
        assert entered.wait(5)
        try:
            with Session(postgres_engine) as db:
                db.execute(text("SET LOCAL lock_timeout='2s'"))
                now = material_service.repo.now(db)
                user = db.get(User, principals[0].user_id, with_for_update=True)
                profile = db.get(LearnerProfile, learner, with_for_update=True)
                if change == "relationship":
                    row = db.scalar(
                        select(EducatorLearnerRelationship)
                        .where(
                            EducatorLearnerRelationship.learner_id == learner,
                            EducatorLearnerRelationship.educator_user_id == principals[0].user_id,
                        )
                        .with_for_update()
                    )
                    row.revoked_at = now
                    row.revoked_by_user_id = principals[0].user_id
                elif change == "learner":
                    profile.archived_at = now
                elif change == "session":
                    session = db.get(AuthSession, principals[0].session_id)
                    session.revoked_at, session.revocation_reason = now, "logout"
                elif change == "user":
                    user.status = "disabled"
                else:
                    source = db.get(Source, claim.source_id, with_for_update=True)
                    source.archived_at = now
                db.commit()
        finally:
            resume.set()
        assert future.result(timeout=10) in (401, 404, 409)
    with Session(postgres_engine) as db:
        assert db.get(Source, claim.source_id).material_id is None
        assert db.get(ExtractionRun, claim.run_id).status == "running"


def test_new_fingerprint_and_concurrent_revision(work, postgres_engine, monkeypatch):
    learner, principals, storage, first, data, _ = work
    with Session(postgres_engine) as db:
        original = service.finish(db, principals[0], learner, storage, first)[0]
        old_text = db.get(ExtractionRun, original.id).assembled_text
    original_fp = contracts.fingerprint()
    monkeypatch.setattr(contracts, "fingerprint", lambda: "f" * 64)
    with Session(postgres_engine) as db:
        with pytest.raises(SecurityError):
            service.claim(db, principals[0], learner, first.source_id, None)
        work2 = service.claim(db, principals[0], learner, first.source_id, 1)
    with Session(postgres_engine) as db:
        material_service.revise(
            db,
            principals[1],
            learner,
            original.material_id,
            RevisionCreate(
                row_version=1, title="Synthetic manual", language_tag="en", text="A bird sings."
            ),
        )
    with Session(postgres_engine) as db:
        with pytest.raises(SecurityError) as exc:
            service.publish(db, principals[0], learner, work2, extract(data))
        assert exc.value.code == "version_conflict"
        assert db.get(ExtractionRun, original.id).extraction_fingerprint == original_fp
        assert db.get(ExtractionRun, original.id).assembled_text == old_text


def test_lost_response_same_request_concurrent(work, postgres_engine):
    learner, principals, storage, claim, data, metadata = work
    with Session(postgres_engine) as db:
        accepted = service.finish(db, principals[0], learner, storage, claim)[0]

    def retry():
        with Session(postgres_engine) as db:
            return service.upload(db, principals[0], learner, metadata, data, storage)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: retry(), range(2)))
    assert all(
        status == 200 and result.extraction.id == accepted.id for result, status in responses
    )


def test_new_extractor_appends_revision(work, postgres_engine, monkeypatch):
    learner, principals, storage, first, data, _ = work
    with Session(postgres_engine) as db:
        original = service.finish(db, principals[0], learner, storage, first)[0]
    monkeypatch.setattr(contracts, "fingerprint", lambda: "b" * 64)
    with Session(postgres_engine) as db:
        second = service.claim(db, principals[1], learner, first.source_id, 1)
        new = service.finish(db, principals[1], learner, storage, second)[0]
        assert new.material_id == original.material_id
        assert new.revision_id != original.revision_id
        assert material_service.repo.latest(db, new.material_id).revision_number == 2


@pytest.mark.parametrize("context", [3], indirect=True)
def test_expiry_after_source_lock_wait(work, postgres_engine, context):
    from queue import Queue

    from tests.reading_materials.test_concurrency import wait_blocked

    learner, principals, storage, first, data, _ = work
    expiry = context[4]
    pids = Queue()

    def waiting():
        with Session(postgres_engine) as db:
            pids.put(db.scalar(text("SELECT pg_backend_pid()")))
            try:
                service.claim(db, principals[0], learner, first.source_id, None)
            except SecurityError as exc:
                return exc.code

    with Session(postgres_engine) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.get(Source, first.source_id, with_for_update=True)
        future = pool.submit(waiting)
        wait_blocked(blocker, pids.get(timeout=5))
        while material_service.repo.now(blocker) <= expiry:
            sleep(0.02)
        blocker.commit()
        assert future.result(timeout=10) == "not_found"
