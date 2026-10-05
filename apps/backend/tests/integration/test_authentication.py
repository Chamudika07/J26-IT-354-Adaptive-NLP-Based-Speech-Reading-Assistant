"""Real PostgreSQL auth/API tests; transaction fixture isolates synthetic rows."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import SecurityError
from app.modules.auth import repository as repo
from app.modules.auth import service
from app.modules.auth.models import AuthRefreshToken, AuthSession, Role, UserRole
from app.modules.auth.tokens import issue_access_token

pytestmark = pytest.mark.integration
PASSWORD = "Synthetic accessible passphrase 42"


def login(client, user):
    response = client.post(
        "/api/v1/auth/login", json={"login_handle": user.login_handle.upper(), "password": PASSWORD}
    )
    assert response.status_code == 200
    return response.json()


def test_login_me_no_email_and_safe_projection(auth_client, active_user, db_session):
    pair = login(auth_client, active_user)
    assert pair["expires_in"] == 300 and pair["token_type"] == "bearer"
    response = auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + pair["access_token"]}
    )
    assert response.json() == {
        "user_id": str(active_user.id),
        "login_handle": active_user.login_handle,
        "roles": [],
        "status": "active",
    }
    assert response.headers["cache-control"] == "no-store"
    stored = db_session.scalar(select(AuthRefreshToken))
    session = db_session.get(AuthSession, stored.session_id)
    assert stored.token_digest == service.refresh_digest(pair["refresh_token"])
    assert stored.token_digest != pair["refresh_token"].encode()
    assert session.expires_at - session.authenticated_at == timedelta(days=7)
    assert session.idle_expires_at - session.authenticated_at == timedelta(hours=24)
    assert "password" not in response.text and "digest" not in response.text


@pytest.mark.parametrize("case", ["unknown", "wrong", "disabled", "anonymized", "malformed"])
def test_login_failures_are_identical(auth_client, active_user, db_session, case):
    handle = active_user.login_handle
    if case == "disabled":
        active_user.status = "disabled"
    if case == "anonymized":
        active_user.status = "anonymized"
        active_user.login_handle = None
        active_user.password_hash = None
        active_user.deleted_at = repo.now(db_session)
    if case == "malformed":
        active_user.password_hash = "$argon2id$bad"
    db_session.flush()
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "login_handle": "unknown" if case == "unknown" else handle,
            "password": "Wrong synthetic password" if case == "wrong" else PASSWORD,
        },
    )
    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "invalid_credentials", "message": "Invalid login credentials"}
    }


def test_rotation_replay_revokes_access_and_replacement(auth_client, active_user, db_session):
    old = login(auth_client, active_user)
    response = auth_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}
    )
    assert response.status_code == 200
    new = response.json()
    assert new["refresh_token"] != old["refresh_token"]
    assert new["access_token"] != old["access_token"]
    assert len(list(db_session.scalars(select(AuthRefreshToken)))) == 2
    replay = auth_client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    assert replay.status_code == 401 and replay.json()["error"]["code"] == "invalid_session"
    db_session.expire_all()
    assert db_session.scalar(select(AuthSession)).revocation_reason == "replay"
    for pair in (old, new):
        assert (
            auth_client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer " + pair["access_token"]}
            ).status_code
            == 401
        )
    assert (
        auth_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}
        ).status_code
        == 401
    )


def test_logout_is_idempotent_and_session_scoped(auth_client, active_user):
    first, other = login(auth_client, active_user), login(auth_client, active_user)
    for _ in range(2):
        response = auth_client.post(
            "/api/v1/auth/logout", json={"refresh_token": first["refresh_token"]}
        )
        assert response.status_code == 204 and response.content == b""
    assert (
        auth_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + first["access_token"]}
        ).status_code
        == 401
    )
    assert (
        auth_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + other["access_token"]}
        ).status_code
        == 200
    )
    assert (
        auth_client.post("/api/v1/auth/logout", json={"refresh_token": "unknown"}).status_code
        == 204
    )


def test_revoke_all_sessions_internal_contract(auth_client, active_user, db_session):
    pairs = [login(auth_client, active_user), login(auth_client, active_user)]
    service.revoke_all_sessions(db_session, active_user.id)
    active_user.status = "disabled"
    db_session.commit()
    active_user.status = "active"
    db_session.commit()
    for pair in pairs:
        assert (
            auth_client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer " + pair["access_token"]}
            ).status_code
            == 401
        )
        assert (
            auth_client.post(
                "/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
            ).status_code
            == 401
        )


def test_roles_are_current_not_token_claims(auth_client, active_user, db_session):
    role = db_session.scalar(select(Role).where(Role.code == "guardian"))
    grant = UserRole(user_id=active_user.id, role_id=role.id, granted_by_user_id=active_user.id)
    db_session.add(grant)
    db_session.flush()
    pair = login(auth_client, active_user)
    headers = {"Authorization": "Bearer " + pair["access_token"]}
    assert auth_client.get("/api/v1/auth/me", headers=headers).json()["roles"] == ["guardian"]
    role.is_active = False
    db_session.flush()
    assert auth_client.get("/api/v1/auth/me", headers=headers).json()["roles"] == []
    role.is_active = True
    grant.revoked_at = repo.now(db_session)
    grant.revoked_by_user_id = active_user.id
    db_session.flush()
    assert auth_client.get("/api/v1/auth/me", headers=headers).json()["roles"] == []


@pytest.mark.parametrize("case", ["disabled", "idle", "absolute", "subject", "missing_session"])
def test_principal_rechecks_session_and_account(
    auth_client, active_user, db_session, settings, monkeypatch, case
):
    pair = login(auth_client, active_user)
    session = db_session.scalar(select(AuthSession))
    if case == "disabled":
        active_user.status = "disabled"
        db_session.flush()
    if case in {"idle", "absolute"}:
        deadline = session.idle_expires_at if case == "idle" else session.expires_at
        monkeypatch.setattr(repo, "now", lambda db: deadline)
    if case in {"subject", "missing_session"}:
        pair["access_token"] = issue_access_token(
            uuid4() if case == "subject" else active_user.id,
            uuid4() if case == "missing_session" else session.id,
            settings,
            repo.now(db_session),
        )
    response = auth_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer " + pair["access_token"]}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("case", ["unknown", "disabled", "idle", "absolute", "token_expiry"])
def test_refresh_failure_states(auth_client, active_user, db_session, monkeypatch, case):
    pair = login(auth_client, active_user)
    session = db_session.scalar(select(AuthSession))
    now = repo.now(db_session)
    if case == "disabled":
        active_user.status = "disabled"
        db_session.flush()
    if case in {"idle", "absolute"}:
        deadline = session.idle_expires_at if case == "idle" else session.expires_at
        monkeypatch.setattr(repo, "now", lambda db: deadline)
    if case == "token_expiry":
        token = db_session.scalar(select(AuthRefreshToken))
        token.expires_at = now
        db_session.flush()
    response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "unknown" if case == "unknown" else pair["refresh_token"]},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_session"


def test_refresh_never_extends_absolute_deadline(
    auth_client, active_user, db_session, settings, monkeypatch
):
    pair = login(auth_client, active_user)
    session = db_session.scalar(select(AuthSession))
    absolute = session.expires_at
    # Simulate successive timely refreshes, then approach the fixed absolute deadline.
    raw = pair["refresh_token"]
    for day in range(1, 8):
        moment = session.created_at + timedelta(hours=23 * day)
        monkeypatch.setattr(repo, "now", lambda db, moment=moment: moment)
        raw = service.refresh(db_session, settings, raw).refresh_token
    assert session.expires_at == absolute
    assert session.idle_expires_at == absolute
    monkeypatch.setattr(repo, "now", lambda db: absolute)
    with pytest.raises(SecurityError):
        service.refresh(db_session, settings, raw)


def test_input_errors_hide_passwords(auth_client):
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"login_handle": "synthetic", "password": {"secret": "do-not-echo"}},
    )
    assert response.status_code == 422 and "do-not-echo" not in response.text
    assert auth_client.get("/api/v1/auth/me").status_code == 401
    assert (
        auth_client.get("/api/v1/auth/me", headers={"Authorization": "Basic invalid"}).status_code
        == 401
    )


def test_login_rechecks_account_after_password_verification(
    active_user, db_session, settings, monkeypatch
):
    original = service.verify_password

    def change_account(password, encoded):
        result = original(password, encoded)
        active_user.status = "disabled"
        db_session.flush()
        return result

    monkeypatch.setattr(service, "verify_password", change_account)
    with pytest.raises(SecurityError) as error:
        service.login(db_session, settings, active_user.login_handle, PASSWORD)
    assert error.value.code == "invalid_credentials"
    assert db_session.scalar(select(AuthSession)) is None


def test_login_upgrades_password_hash(active_user, db_session, settings):
    from pwdlib import PasswordHash
    from pwdlib.hashers.argon2 import Argon2Hasher

    old = PasswordHash((Argon2Hasher(memory_cost=19456, time_cost=2, parallelism=1),)).hash(
        PASSWORD
    )
    active_user.password_hash = old
    db_session.flush()
    service.login(db_session, settings, active_user.login_handle, PASSWORD)
    assert active_user.password_hash != old


def test_global_guard_http_and_failure_sanitization(
    application, auth_client, active_user, db_session
):
    from typing import Annotated

    from fastapi import Depends
    from sqlalchemy.exc import OperationalError

    from app.modules.auth.contracts import Principal
    from app.modules.auth.dependencies import require_administrator

    @application.get("/test-only/administrator")
    def guarded(principal: Annotated[Principal, Depends(require_administrator)]):
        return {"allowed": True}

    @application.get("/test-only/database-error")
    def database_error():
        raise OperationalError("sensitive SQL", {}, Exception("private credentials"))

    pair = login(auth_client, active_user)
    headers = {"Authorization": "Bearer " + pair["access_token"]}
    assert auth_client.get("/test-only/administrator").status_code == 401
    denied = auth_client.get("/test-only/administrator", headers=headers)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "forbidden"
    role = db_session.scalar(select(Role).where(Role.code == "administrator"))
    db_session.add(
        UserRole(user_id=active_user.id, role_id=role.id, granted_by_user_id=active_user.id)
    )
    db_session.flush()
    assert auth_client.get("/test-only/administrator", headers=headers).status_code == 200
    unavailable = auth_client.get("/test-only/database-error")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "error": {"code": "service_unavailable", "message": "Service unavailable"}
    }
