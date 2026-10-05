"""Independent committed PostgreSQL connections; never shared ORM sessions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth import service
from app.modules.auth.models import AuthRefreshToken, AuthSession, User

pytestmark = pytest.mark.integration


@pytest.fixture
def committed_account(postgres_engine, password_hash):
    with Session(postgres_engine) as db:
        user = User(
            login_handle="concurrency_" + uuid4().hex[:16],
            status="active",
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        identity, handle = user.id, user.login_handle
        db.commit()
    try:
        yield identity, handle
    finally:
        with Session(postgres_engine) as db:
            db.execute(delete(AuthSession).where(AuthSession.user_id == identity))
            db.execute(delete(User).where(User.id == identity))
            db.commit()


def test_concurrent_refresh_has_one_successor_and_committed_replay_revocation(
    postgres_engine, committed_account, settings
):
    with Session(postgres_engine) as db:
        original = service.login(
            db, settings, committed_account[1], "Synthetic accessible passphrase 42"
        )
    barrier = Barrier(2)

    def attempt():
        with Session(postgres_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '8s'"))
            pid = db.scalar(text("SELECT pg_backend_pid()"))
            barrier.wait(timeout=10)
            try:
                return pid, service.refresh(db, settings, original.refresh_token)
            except SecurityError as error:
                return pid, error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert len({pid for pid, _ in results}) == 2
    successes = [result for _, result in results if not isinstance(result, str)]
    assert len(successes) == 1
    assert [result for _, result in results if isinstance(result, str)] == ["invalid_session"]
    with Session(postgres_engine) as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == committed_account[0]))
        assert session.revocation_reason == "replay" and session.revoked_at is not None
        assert list(
            db.scalars(
                select(AuthRefreshToken.generation)
                .where(AuthRefreshToken.session_id == session.id)
                .order_by(AuthRefreshToken.generation)
            )
        ) == [0, 1]
        with pytest.raises(SecurityError):
            service.resolve_principal(db, settings, successes[0].access_token)
        with pytest.raises(SecurityError):
            service.refresh(db, settings, successes[0].refresh_token)


def test_failed_rotation_rolls_back_consumption(
    postgres_engine, committed_account, settings, monkeypatch
):
    with Session(postgres_engine) as db:
        pair = service.login(
            db, settings, committed_account[1], "Synthetic accessible passphrase 42"
        )
    original = service._credential

    def fail(*args):
        raise RuntimeError("synthetic issuance failure")

    monkeypatch.setattr(service, "_credential", fail)
    with pytest.raises(RuntimeError), Session(postgres_engine) as db:
        service.refresh(db, settings, pair.refresh_token)
    monkeypatch.setattr(service, "_credential", original)
    with Session(postgres_engine) as db:
        assert service.refresh(db, settings, pair.refresh_token).refresh_token != pair.refresh_token
