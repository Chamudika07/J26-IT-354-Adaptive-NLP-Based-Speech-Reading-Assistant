"""Committed, independent PostgreSQL sessions for provisioning races."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth import provisioning, repository, service
from app.modules.auth.models import AuthSession, Role, User, UserRole
from app.modules.auth.provisioning_schemas import AccountCreate
from app.modules.learners import onboarding
from app.modules.learners.models import EducatorLearnerRelationship, LearnerProfile
from app.modules.learners.onboarding_schemas import EducatorGrantCreate

pytestmark = pytest.mark.integration
PASSWORD = "Synthetic accessible passphrase 42"


@pytest.fixture
def committed_setup(postgres_engine, password_hash, settings):
    prefix = "onboard_" + uuid4().hex[:12]
    with Session(postgres_engine) as db:
        users = [
            User(login_handle=f"{prefix}_{i}", password_hash=password_hash, status="active")
            for i in range(3)
        ]
        db.add_all(users)
        db.flush()
        ids = [user.id for user in users]
        for index, user in enumerate(users):
            code = "administrator" if index < 2 else "educator"
            role = db.scalar(select(Role).where(Role.code == code))
            db.add(UserRole(user_id=user.id, role_id=role.id, granted_by_user_id=ids[0]))
        learner = LearnerProfile(
            display_name="Synthetic concurrency reader", created_by_user_id=ids[0]
        )
        db.add(learner)
        db.flush()
        learner_id = learner.id
        db.commit()
        principals = []
        for index in range(2):
            pair = service.login(db, settings, f"{prefix}_{index}", PASSWORD)
            principals.append(service.resolve_principal(db, settings, pair.access_token))
        db.rollback()
    try:
        yield prefix, ids, learner_id, principals
    finally:
        with Session(postgres_engine) as db:
            all_ids = list(db.scalars(select(User.id).where(User.login_handle.startswith(prefix))))
            db.execute(
                delete(EducatorLearnerRelationship).where(
                    EducatorLearnerRelationship.learner_id == learner_id
                )
            )
            db.execute(delete(LearnerProfile).where(LearnerProfile.id == learner_id))
            db.execute(delete(AuthSession).where(AuthSession.user_id.in_(all_ids)))
            db.execute(delete(UserRole).where(UserRole.user_id.in_(all_ids)))
            db.execute(delete(User).where(User.id.in_(all_ids)))
            db.commit()


@pytest.mark.parametrize("operation", ["account", "grant"])
def test_two_admins_cannot_duplicate_creation(postgres_engine, committed_setup, operation):
    prefix, ids, learner_id, principals = committed_setup
    barrier = Barrier(2)
    with Session(postgres_engine) as db:
        expiry = repository.now(db) + timedelta(days=1)

    def attempt(index):
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
            barrier.wait(timeout=10)
            try:
                if operation == "account":
                    provisioning.create_educator(
                        db,
                        principals[index],
                        AccountCreate(login_handle=prefix + "_new", password=PASSWORD),
                    )
                else:
                    onboarding.create_grant(
                        db,
                        principals[index],
                        learner_id,
                        EducatorGrantCreate(
                            educator_user_id=ids[2], access_level="instructor", expires_at=expiry
                        ),
                    )
                return "created"
            except SecurityError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt, i) for i in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert results.count("created") == 1
    assert results.count("handle_unavailable" if operation == "account" else "grant_exists") == 1


def test_bootstrap_race_has_only_one_administrator(postgres_engine):
    prefix = "bootstrap_race_" + uuid4().hex[:10]
    barrier = Barrier(2)

    def attempt(index):
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
            barrier.wait(timeout=10)
            try:
                provisioning.bootstrap_administrator(
                    db, AccountCreate(login_handle=f"{prefix}_{index}", password=PASSWORD)
                )
                return "created"
            except SecurityError as exc:
                return exc.code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(attempt, i) for i in range(2)]
            results = [future.result(timeout=20) for future in futures]
        assert sorted(results) == ["administrator_exists", "created"]
    finally:
        with Session(postgres_engine) as db:
            ids = list(db.scalars(select(User.id).where(User.login_handle.startswith(prefix))))
            db.execute(delete(UserRole).where(UserRole.user_id.in_(ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
            db.commit()
