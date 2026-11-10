"""Managed onboarding against disposable PostgreSQL; synthetic identities only."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.exceptions import SecurityError
from app.modules.auth import provisioning, repository
from app.modules.auth import service as auth_service
from app.modules.auth.models import Role, User, UserRole
from app.modules.auth.passwords import verify_password
from app.modules.auth.provisioning import bootstrap_administrator
from app.modules.auth.provisioning_schemas import AccountCreate
from app.modules.learners import onboarding
from app.modules.learners.models import EducatorLearnerRelationship, LearnerProfile
from app.modules.learners.onboarding_schemas import LearnerCreate

pytestmark = pytest.mark.integration
PASSWORD = "Synthetic accessible passphrase 42"


def login(client, handle):
    result = client.post("/api/v1/auth/login", json={"login_handle": handle, "password": PASSWORD})
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def role(db, user, code):
    definition = db.scalar(select(Role).where(Role.code == code))
    row = UserRole(user_id=user.id, role_id=definition.id, granted_by_user_id=user.id)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def admin(auth_client, active_user, db_session):
    role(db_session, active_user, "administrator")
    return login(auth_client, active_user.login_handle)


def educator(client, admin):
    handle = "synthetic_" + uuid4().hex[:16]
    result = client.post(
        "/api/v1/auth/users", headers=admin, json={"login_handle": handle, "password": PASSWORD}
    )
    assert result.status_code == 201, result.text
    return result.json(), login(client, handle)


def learner(client, admin):
    result = client.post(
        "/api/v1/learners", headers=admin, json={"display_name": "Synthetic Reader"}
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


def grant(client, admin, learner_id, user_id, db, **changes):
    payload = {
        "educator_user_id": str(user_id),
        "access_level": "instructor",
        "expires_at": (repository.now(db) + timedelta(days=7)).isoformat(),
        **changes,
    }
    return client.post(
        f"/api/v1/learners/{learner_id}/educator-grants", headers=admin, json=payload
    )


def test_complete_onboarding_and_revocation(auth_client, admin, db_session, active_user):
    account, headers = educator(auth_client, admin)
    user = db_session.get(User, UUID(account["user_id"]))
    assert verify_password(PASSWORD, user.password_hash)[0]
    assert set(account) == {"user_id", "login_handle", "status", "roles"}
    assert account["roles"] == ["educator"]
    learner_id = learner(auth_client, admin)
    assert auth_client.get("/api/v1/learners", headers=headers).json()["items"] == []
    access = grant(auth_client, admin, learner_id, user.id, db_session)
    assert access.status_code == 201
    access_id = access.json()["id"]
    row = db_session.get(EducatorLearnerRelationship, UUID(access_id))
    assert row.granted_by_user_id == active_user.id
    assert auth_client.get(f"/api/v1/learners/{learner_id}", headers=admin).status_code == 404
    assert auth_client.get(f"/api/v1/learners/{learner_id}", headers=headers).status_code == 200
    assert (
        auth_client.get(f"/api/v1/learners/{learner_id}/preferences", headers=headers).status_code
        == 404
    )
    material = auth_client.post(
        f"/api/v1/learners/{learner_id}/reading-materials",
        headers=headers,
        json={"title": "Synthetic story", "language_tag": "en", "text": "A cat sits on a mat."},
    )
    assert material.status_code == 201
    body = material.json()
    process_path = (
        f"/api/v1/learners/{learner_id}/reading-materials/{body['id']}"
        f"/revisions/{body['latest_revision']['id']}/processing-runs"
    )
    assert auth_client.post(process_path, headers=headers, json={}).status_code == 201
    unrelated = learner(auth_client, admin)
    assert auth_client.get(f"/api/v1/learners/{unrelated}", headers=headers).status_code == 404
    wrong_path = f"/api/v1/learners/{unrelated}/educator-grants/{access_id}/revoke"
    assert auth_client.post(wrong_path, headers=admin).status_code == 404
    path = f"/api/v1/learners/{learner_id}/educator-grants/{access_id}/revoke"
    first = auth_client.post(path, headers=admin)
    assert first.status_code == 200
    assert first.json()["revoked_at"]
    assert auth_client.post(path, headers=admin).json() == first.json()
    assert auth_client.get(f"/api/v1/learners/{learner_id}", headers=headers).status_code == 404
    assert auth_client.post(process_path, headers=headers, json={}).status_code == 404
    replacement = grant(auth_client, admin, learner_id, user.id, db_session)
    assert replacement.status_code == 201
    assert replacement.json()["id"] != access_id


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize("operation", ["account", "learner", "grant", "revoke"])
def test_management_requires_admin(auth_client, active_user, operation, authenticated):
    headers = login(auth_client, active_user.login_handle) if authenticated else {}
    requests = {
        "account": ("/api/v1/auth/users", {"login_handle": "new.educator", "password": PASSWORD}),
        "learner": ("/api/v1/learners", {"display_name": "Synthetic"}),
        "grant": (
            f"/api/v1/learners/{uuid4()}/educator-grants",
            {
                "educator_user_id": str(uuid4()),
                "access_level": "instructor",
                "expires_at": "2099-01-01T00:00:00Z",
            },
        ),
        "revoke": (f"/api/v1/learners/{uuid4()}/educator-grants/{uuid4()}/revoke", None),
    }
    path, payload = requests[operation]
    result = auth_client.post(path, headers=headers, json=payload)
    assert result.status_code == (403 if authenticated else 401)


def test_duplicate_normalized_handle(auth_client, admin):
    handle = "synthetic_" + uuid4().hex[:16]
    payload = {"login_handle": " " + handle.upper() + " ", "password": PASSWORD}
    first = auth_client.post("/api/v1/auth/users", headers=admin, json=payload)
    assert first.status_code == 201
    assert first.json()["login_handle"] == handle
    second = auth_client.post("/api/v1/auth/users", headers=admin, json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "handle_unavailable"
    assert PASSWORD not in second.text


@pytest.mark.parametrize(
    "change",
    [
        {"login_handle": "a"},
        {"login_handle": "bad handle"},
        {"password": "short"},
        {"password": "x" * 129},
        {"role": "administrator"},
        {"status": "active"},
    ],
)
def test_invalid_account_input(auth_client, admin, change):
    result = auth_client.post(
        "/api/v1/auth/users",
        headers=admin,
        json={
            "login_handle": "synthetic.test",
            "password": PASSWORD,
            **change,
        },
    )
    assert result.status_code == 422
    assert PASSWORD not in result.text


@pytest.mark.parametrize(
    "condition",
    [
        "missing_user",
        "disabled_user",
        "no_role",
        "revoked_role",
        "inactive_role",
        "past_expiry",
        "naive_expiry",
        "missing_learner",
        "archived_learner",
    ],
)
def test_invalid_grants(auth_client, admin, db_session, condition):
    account, _ = educator(auth_client, admin)
    user_id = UUID(account["user_id"])
    learner_id = learner(auth_client, admin)
    changes = {}
    expected = 422
    if condition == "missing_user":
        user_id = uuid4()
    elif condition == "disabled_user":
        db_session.get(User, user_id).status = "disabled"
    elif condition in {"no_role", "revoked_role"}:
        assignment = db_session.scalar(select(UserRole).where(UserRole.user_id == user_id))
        if condition == "no_role":
            db_session.delete(assignment)
        else:
            assignment.revoked_at = repository.now(db_session)
            assignment.revoked_by_user_id = user_id
    elif condition == "inactive_role":
        db_session.scalar(select(Role).where(Role.code == "educator")).is_active = False
    elif condition == "past_expiry":
        changes["expires_at"] = "2000-01-01T00:00:00Z"
    elif condition == "naive_expiry":
        changes["expires_at"] = "2099-01-01T00:00:00"
    elif condition == "missing_learner":
        learner_id = str(uuid4())
        expected = 404
    elif condition == "archived_learner":
        db_session.get(LearnerProfile, UUID(learner_id)).archived_at = repository.now(db_session)
        expected = 404
    db_session.flush()
    result = grant(auth_client, admin, learner_id, user_id, db_session, **changes)
    assert result.status_code == expected, result.text


def test_expired_open_grant_requires_explicit_replacement(auth_client, admin, db_session):
    account, headers = educator(auth_client, admin)
    learner_id = learner(auth_client, admin)
    now = repository.now(db_session)
    row = EducatorLearnerRelationship(
        learner_id=UUID(learner_id),
        educator_user_id=UUID(account["user_id"]),
        access_level="instructor",
        granted_by_user_id=UUID(account["user_id"]),
        created_at=now - timedelta(days=2),
        expires_at=now - timedelta(days=1),
    )
    db_session.add(row)
    db_session.flush()
    assert auth_client.get(f"/api/v1/learners/{learner_id}", headers=headers).status_code == 404
    assert grant(auth_client, admin, learner_id, account["user_id"], db_session).status_code == 409


def test_viewer_can_read_but_not_process(auth_client, admin, db_session):
    account, headers = educator(auth_client, admin)
    learner_id = learner(auth_client, admin)
    assert (
        grant(
            auth_client, admin, learner_id, account["user_id"], db_session, access_level="viewer"
        ).status_code
        == 201
    )
    assert auth_client.get(f"/api/v1/learners/{learner_id}", headers=headers).status_code == 200
    assert (
        auth_client.post(
            f"/api/v1/learners/{learner_id}/reading-materials",
            headers=headers,
            json={"title": "Synthetic", "language_tag": "en", "text": "A cat sits."},
        ).status_code
        == 404
    )


def test_account_and_role_rollback_together(auth_client, admin, db_session, monkeypatch):
    handle = "synthetic_rollback_" + uuid4().hex[:10]

    def fail(*args):
        raise SecurityError(401, "authentication_required", "Authentication required")

    monkeypatch.setattr(provisioning, "assert_protected_session_live", fail)
    result = auth_client.post(
        "/api/v1/auth/users", headers=admin, json={"login_handle": handle, "password": PASSWORD}
    )
    assert result.status_code == 401
    assert db_session.scalar(select(User).where(User.login_handle == handle)) is None


def test_bootstrap_first_only_and_no_overwrite(db_session):
    payload = AccountCreate(login_handle="synthetic_bootstrap", password=PASSWORD)
    result = bootstrap_administrator(db_session, payload)
    assert result.roles == ["administrator"]
    count = db_session.scalar(select(func.count()).select_from(User))
    with pytest.raises(SecurityError, match="already provisioned"):
        bootstrap_administrator(
            db_session, AccountCreate(login_handle="synthetic_second", password=PASSWORD)
        )
    assert db_session.scalar(select(func.count()).select_from(User)) == count


def test_bootstrap_does_not_replace_existing_handle(db_session, active_user):
    with pytest.raises(SecurityError) as error:
        bootstrap_administrator(
            db_session, AccountCreate(login_handle=active_user.login_handle, password=PASSWORD)
        )
    assert error.value.code == "handle_unavailable"
    assert repository.active_roles(db_session, active_user.id) == frozenset()


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "   "},
        {"display_name": "x" * 81},
        {"display_name": "Synthetic", "learner_user_id": str(uuid4())},
    ],
)
def test_learner_rejects_invalid_or_extra_fields(auth_client, admin, payload):
    assert auth_client.post("/api/v1/learners", headers=admin, json=payload).status_code == 422


@pytest.mark.parametrize("operation", ["learner", "grant"])
def test_domain_write_rollback(auth_client, admin, db_session, monkeypatch, operation):
    account, _ = educator(auth_client, admin)
    learner_id = learner(auth_client, admin)
    before = db_session.scalar(select(func.count()).select_from(LearnerProfile))

    def fail(*args):
        raise SecurityError(401, "authentication_required", "Authentication required")

    monkeypatch.setattr(onboarding, "assert_protected_session_live", fail)
    if operation == "learner":
        result = auth_client.post(
            "/api/v1/learners", headers=admin, json={"display_name": "Synthetic rollback"}
        )
        assert db_session.scalar(select(func.count()).select_from(LearnerProfile)) == before
    else:
        result = grant(auth_client, admin, learner_id, account["user_id"], db_session)
        assert (
            db_session.scalar(
                select(EducatorLearnerRelationship.id).where(
                    EducatorLearnerRelationship.learner_id == UUID(learner_id)
                )
            )
            is None
        )
    assert result.status_code == 401


def test_stale_admin_principal_rechecked_before_write(
    auth_client, admin, db_session, active_user, settings
):
    principal = auth_service.resolve_principal(db_session, settings, admin["Authorization"][7:])
    assignment = db_session.scalar(select(UserRole).where(UserRole.user_id == active_user.id))
    assignment.revoked_at = repository.now(db_session)
    assignment.revoked_by_user_id = active_user.id
    db_session.flush()
    with pytest.raises(SecurityError) as error:
        onboarding.create_learner(db_session, principal, LearnerCreate(display_name="Synthetic"))
    assert error.value.status == 403


def test_unavailable_educator_role_creates_no_user(auth_client, admin, db_session):
    db_session.scalar(select(Role).where(Role.code == "educator")).is_active = False
    db_session.flush()
    handle = "synthetic_disabled_role"
    result = auth_client.post(
        "/api/v1/auth/users", headers=admin, json={"login_handle": handle, "password": PASSWORD}
    )
    assert result.status_code == 409
    assert db_session.scalar(select(User).where(User.login_handle == handle)) is None
