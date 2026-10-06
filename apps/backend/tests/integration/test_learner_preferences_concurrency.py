"""Real committed PostgreSQL connections exercise versions and revocation races."""

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth import repository as auth_repo
from app.modules.auth import service as auth_service
from app.modules.auth.models import AuthSession, Role, User, UserRole
from app.modules.learners import repository as repo
from app.modules.learners import service
from app.modules.learners.models import (
    GuardianLearnerRelationship,
    LearnerPreferences,
    LearnerProfile,
)
from app.modules.learners.schemas import LearnerPreferenceUpdate

pytestmark = pytest.mark.integration


@pytest.fixture
def family(postgres_engine, password_hash, settings):
    users = [uuid4(), uuid4()]
    learner_id = uuid4()
    with Session(postgres_engine) as db:
        for identity in users:
            db.add(
                User(
                    id=identity,
                    login_handle="race_" + identity.hex,
                    status="active",
                    password_hash=password_hash,
                )
            )
        db.flush()
        role = db.scalar(select(Role).where(Role.code == "guardian"))
        role_id = role.id
        db.add(
            LearnerProfile(
                id=learner_id,
                display_name="Synthetic concurrent learner",
                created_by_user_id=users[0],
            )
        )
        db.flush()
        for identity in users:
            db.add(UserRole(user_id=identity, role_id=role_id, granted_by_user_id=identity))
            db.add(
                GuardianLearnerRelationship(
                    guardian_user_id=identity,
                    learner_id=learner_id,
                    access_level="manager",
                    granted_by_user_id=identity,
                )
            )
        db.commit()
        principals = []
        for identity in users:
            pair = auth_service.login(
                db, settings, "race_" + identity.hex, "Synthetic accessible passphrase 42"
            )
            principals.append(auth_service.resolve_principal(db, settings, pair.access_token))
    try:
        yield learner_id, principals
    finally:
        with Session(postgres_engine) as db:
            db.get(Role, role_id).is_active = True
            db.execute(
                delete(GuardianLearnerRelationship).where(
                    GuardianLearnerRelationship.learner_id == learner_id
                )
            )
            db.execute(delete(LearnerProfile).where(LearnerProfile.id == learner_id))
            db.execute(delete(UserRole).where(UserRole.user_id.in_(users)))
            db.execute(delete(AuthSession).where(AuthSession.user_id.in_(users)))
            db.execute(delete(User).where(User.id.in_(users)))
            db.commit()


@pytest.mark.parametrize("version", [0, 1])
@pytest.mark.parametrize("different_actors", [False, True])
def test_concurrent_first_creation_and_updates(postgres_engine, family, version, different_actors):
    learner_id, principals = family
    if version:
        with Session(postgres_engine) as db:
            service.update_preferences(
                db,
                principals[0],
                learner_id,
                LearnerPreferenceUpdate(row_version=0, theme="system"),
            )
    barrier = Barrier(2)

    def attempt(index):
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            actor = principals[index if different_actors else 0]
            barrier.wait(timeout=10)
            try:
                result = service.update_preferences(
                    db,
                    actor,
                    learner_id,
                    LearnerPreferenceUpdate(
                        row_version=version, theme="light" if index == 0 else "dark"
                    ),
                )
                return pid, result, actor.user_id
            except SecurityError as error:
                return pid, error.code, actor.user_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, index) for index in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert len({pid for pid, _, _ in results}) == 2
    success = [(result, actor) for _, result, actor in results if not isinstance(result, str)]
    assert len(success) == 1
    assert [result for _, result, _ in results if isinstance(result, str)] == ["version_conflict"]
    with Session(postgres_engine) as db:
        rows = list(
            db.scalars(
                select(LearnerPreferences).where(LearnerPreferences.learner_id == learner_id)
            )
        )
        assert len(rows) == 1
        assert rows[0].row_version == version + 1
        assert rows[0].theme == success[0][0].theme
        assert rows[0].updated_by_user_id == success[0][1]


def mutate_authority(db, family, case):
    learner_id, principals = family
    actor = principals[0]
    now = auth_repo.now(db)
    if case == "relationship":
        row = db.scalar(
            select(GuardianLearnerRelationship).where(
                GuardianLearnerRelationship.learner_id == learner_id,
                GuardianLearnerRelationship.guardian_user_id == actor.user_id,
            )
        )
        row.revoked_at, row.revoked_by_user_id = now, principals[1].user_id
    elif case == "archive":
        db.get(LearnerProfile, learner_id).archived_at = now
    elif case == "role":
        db.scalar(select(Role).where(Role.code == "guardian")).is_active = False
    elif case == "assignment":
        row = db.scalar(select(UserRole).where(UserRole.user_id == actor.user_id))
        row.revoked_at, row.revoked_by_user_id = now, principals[1].user_id
    elif case == "account":
        db.get(User, actor.user_id).status = "disabled"
    else:
        row = db.get(AuthSession, actor.session_id)
        row.revoked_at, row.revocation_reason = now, "logout"
    db.flush()


def wait_until_blocked(db, pid):
    deadline = monotonic() + 8
    while monotonic() < deadline:
        if db.scalar(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid}):
            return
        Event().wait(0.01)
    pytest.fail("Concurrent statement never waited for the authorization lock")


@pytest.mark.parametrize(
    "case", ["relationship", "archive", "role", "assignment", "account", "session"]
)
def test_revocation_winning_lock_prevents_stale_principal_write(postgres_engine, family, case):
    learner_id, principals = family
    pids = Queue()

    def attempt():
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '10s'"))
            pids.put(db.scalar(text("SELECT pg_backend_pid()")))
            try:
                service.update_preferences(
                    db,
                    principals[0],
                    learner_id,
                    LearnerPreferenceUpdate(row_version=0, theme="dark"),
                )
                return "unexpected success"
            except SecurityError as error:
                return error.code

    with Session(postgres_engine) as revoker:
        mutate_authority(revoker, family, case)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(attempt)
            try:
                wait_until_blocked(revoker, pids.get(timeout=5))
                revoker.commit()
            finally:
                revoker.rollback()
            assert future.result(timeout=15) == (
                "authentication_required" if case in {"account", "session"} else "not_found"
            )
    with Session(postgres_engine) as db:
        assert (
            db.scalar(select(LearnerPreferences).where(LearnerPreferences.learner_id == learner_id))
            is None
        )


@pytest.mark.parametrize(
    "case", ["relationship", "archive", "role", "assignment", "account", "session"]
)
def test_write_holds_authorization_locks_until_commit(postgres_engine, family, monkeypatch, case):
    learner_id, principals = family
    saving, release = Event(), Event()
    pids = Queue()
    original = repo.save_preferences

    def pause(*args, **kwargs):
        result = original(*args, **kwargs)
        saving.set()
        assert release.wait(timeout=10)
        return result

    monkeypatch.setattr(repo, "save_preferences", pause)

    def write():
        with Session(postgres_engine) as db:
            return service.update_preferences(
                db, principals[0], learner_id, LearnerPreferenceUpdate(row_version=0, theme="light")
            )

    def revoke():
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '10s'"))
            pids.put(db.scalar(text("SELECT pg_backend_pid()")))
            mutate_authority(db, family, case)
            db.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(write)
        try:
            assert saving.wait(timeout=5)
            revoker = pool.submit(revoke)
            with Session(postgres_engine) as observer:
                wait_until_blocked(observer, pids.get(timeout=5))
        finally:
            release.set()
        assert writer.result(timeout=15).row_version == 1
        revoker.result(timeout=15)
    with Session(postgres_engine) as db:
        assert (
            db.scalar(
                select(LearnerPreferences).where(LearnerPreferences.learner_id == learner_id)
            ).row_version
            == 1
        )
        with pytest.raises(SecurityError) as error:
            service.update_preferences(
                db, principals[0], learner_id, LearnerPreferenceUpdate(row_version=1, theme="dark")
            )
        assert error.value.code == (
            "authentication_required" if case in {"account", "session"} else "not_found"
        )
