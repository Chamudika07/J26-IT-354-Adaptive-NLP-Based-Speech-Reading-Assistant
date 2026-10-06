"""HTTP contract, privacy, and authorization against disposable PostgreSQL."""

import hashlib
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.modules.auth import repository as auth_repo
from app.modules.auth.models import Role, UserRole
from app.modules.learners.models import (
    ConsentNoticeVersion,
    ConsentRecord,
    EducatorLearnerRelationship,
    GuardianLearnerRelationship,
    LearnerPreferences,
    LearnerProfile,
)

pytestmark = pytest.mark.integration
PASSWORD = "Synthetic accessible passphrase 42"
PREFERENCE_KEYS = {
    "learner_id",
    "row_version",
    "preferred_language_tag",
    "text_scale",
    "line_spacing",
    "theme",
    "reduce_motion",
}
FULL_KEYS = {"id", "display_name", "age_band", "grade_level"}
BASIC_KEYS = {"id", "display_name"}


def add_role(db, user, code):
    role = db.scalar(select(Role).where(Role.code == code))
    grant = UserRole(user_id=user.id, role_id=role.id, granted_by_user_id=user.id)
    db.add(grant)
    db.flush()
    return grant


def add_profile(db, user, **values):
    row = LearnerProfile(
        created_by_user_id=user.id,
        display_name="Synthetic learner",
        age_band=10,
        grade_level=5,
        **values,
    )
    db.add(row)
    db.flush()
    return row


def guardian(db, user, learner, level="viewer"):
    row = GuardianLearnerRelationship(
        guardian_user_id=user.id,
        learner_id=learner.id,
        access_level=level,
        granted_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


def educator(db, user, learner, level="viewer", expired=False):
    now = auth_repo.now(db)
    row = EducatorLearnerRelationship(
        educator_user_id=user.id,
        learner_id=learner.id,
        access_level=level,
        granted_by_user_id=user.id,
        created_at=now - timedelta(days=2),
        expires_at=now + timedelta(days=-1 if expired else 1),
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def path(auth_client, active_user, db_session):
    def setup(kind):
        learner = add_profile(
            db_session, active_user, learner_user_id=active_user.id if kind == "self" else None
        )
        role = "learner" if kind in {"self", "loginless"} else kind.split("_")[0]
        assignment = add_role(db_session, active_user, role)
        relation = None
        if role == "guardian":
            relation = guardian(db_session, active_user, learner, kind.split("_")[1])
        elif role == "educator":
            relation = educator(db_session, active_user, learner, kind.split("_")[1])
        pair = auth_client.post(
            "/api/v1/auth/login",
            json={"login_handle": active_user.login_handle, "password": PASSWORD},
        )
        assert pair.status_code == 200
        headers = {"Authorization": "Bearer " + pair.json()["access_token"]}
        return learner, headers, relation, assignment

    return setup


KINDS = [
    "self",
    "guardian_viewer",
    "guardian_manager",
    "educator_viewer",
    "educator_instructor",
    "administrator",
    "loginless",
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("operation", ["list", "detail", "read_preferences", "update_preferences"])
def test_http_permission_matrix(auth_client, path, kind, operation, db_session, active_user):
    learner, headers, _, _ = path(kind)
    base = f"/api/v1/learners/{learner.id}"
    if operation == "list":
        response = auth_client.get("/api/v1/learners", headers=headers)
        if kind == "administrator":
            assert response.status_code == 403 and response.json()["error"]["code"] == "forbidden"
        else:
            assert response.status_code == 200
            expected = (
                []
                if kind == "loginless"
                else [{"id": str(learner.id), "display_name": learner.display_name}]
            )
            assert response.json() == {"items": expected, "next_cursor": None}
    else:
        allowed = kind not in {"administrator", "loginless"}
        if operation == "detail":
            response = auth_client.get(base, headers=headers)
            if allowed:
                assert set(response.json()) == (
                    BASIC_KEYS if kind.startswith("educator") else FULL_KEYS
                )
        else:
            allowed = kind in (
                {"self", "guardian_viewer", "guardian_manager"}
                if operation == "read_preferences"
                else {"self", "guardian_manager"}
            )
            response = (
                auth_client.get(base + "/preferences", headers=headers)
                if operation == "read_preferences"
                else auth_client.patch(
                    base + "/preferences",
                    headers=headers,
                    json={"row_version": 0, "theme": "light"},
                )
            )
            if allowed:
                assert set(response.json()) == PREFERENCE_KEYS
                assert response.json()["row_version"] == (
                    0 if operation == "read_preferences" else 1
                )
        assert response.status_code == (200 if allowed else 404)
        if not allowed:
            assert response.json() == {
                "error": {"code": "not_found", "message": "Resource not found"}
            }
    assert response.headers["cache-control"] == "no-store"
    if operation == "update_preferences" and response.status_code == 200:
        row = db_session.scalar(
            select(LearnerPreferences).where(LearnerPreferences.learner_id == learner.id)
        )
        assert row.updated_by_user_id == active_user.id


@pytest.mark.parametrize(
    "method,suffix",
    [("get", ""), ("get", "/any"), ("get", "/any/preferences"), ("patch", "/any/preferences")],
)
def test_unauthenticated(auth_client, method, suffix):
    url = "/api/v1/learners" + suffix.replace("any", str(uuid4()))
    response = getattr(auth_client, method)(
        url, **({"json": {"row_version": 0, "theme": "light"}} if method == "patch" else {})
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


@pytest.mark.parametrize("kind", ["self", "guardian_manager", "educator_instructor"])
def test_cross_learner_denial_and_nonexistence(auth_client, path, db_session, active_user, kind):
    _, headers, _, _ = path(kind)
    unrelated = add_profile(db_session, active_user)
    db_session.commit()
    for identity in (unrelated.id, uuid4()):
        base = f"/api/v1/learners/{identity}"
        for response in (
            auth_client.get(base, headers=headers),
            auth_client.get(base + "/preferences", headers=headers),
            auth_client.patch(
                base + "/preferences", headers=headers, json={"row_version": 999, "theme": "light"}
            ),
        ):
            assert response.status_code == 404
            assert response.json() == {
                "error": {"code": "not_found", "message": "Resource not found"}
            }


@pytest.mark.parametrize("kind", ["guardian_manager", "educator_instructor"])
@pytest.mark.parametrize(
    "state", ["revoked", "archived", "role_revoked", "role_inactive", "disabled"]
)
def test_changes_reflected_on_next_request(auth_client, path, db_session, active_user, kind, state):
    learner, headers, relation, assignment = path(kind)
    assert auth_client.get(f"/api/v1/learners/{learner.id}", headers=headers).status_code == 200
    now = auth_repo.now(db_session)
    if state == "revoked":
        relation.revoked_at, relation.revoked_by_user_id = now, active_user.id
    elif state == "archived":
        learner.archived_at = now
    elif state == "role_revoked":
        assignment.revoked_at, assignment.revoked_by_user_id = now, active_user.id
    elif state == "role_inactive":
        db_session.get(Role, assignment.role_id).is_active = False
    else:
        active_user.status = "disabled"
    db_session.commit()
    response = auth_client.get(f"/api/v1/learners/{learner.id}", headers=headers)
    assert response.status_code == (401 if state == "disabled" else 404)
    listing = auth_client.get("/api/v1/learners", headers=headers)
    if state in {"revoked", "archived"}:
        assert listing.json()["items"] == []
    else:
        assert listing.status_code == (401 if state == "disabled" else 403)
    rejected = auth_client.patch(
        f"/api/v1/learners/{learner.id}/preferences",
        headers=headers,
        json={"row_version": 99, "theme": "light"},
    )
    assert rejected.status_code == (401 if state == "disabled" else 404)


def test_expired_educator_excluded(auth_client, path, db_session, active_user):
    _, headers, _, _ = path("educator_viewer")
    target = add_profile(db_session, active_user)
    educator(db_session, active_user, target, expired=True)
    db_session.commit()
    assert str(target.id) not in {
        item["id"] for item in auth_client.get("/api/v1/learners", headers=headers).json()["items"]
    }
    assert auth_client.get(f"/api/v1/learners/{target.id}", headers=headers).status_code == 404


@pytest.mark.parametrize(
    "additional", ["guardian", "learner", "administrator_guardian", "administrator_only"]
)
def test_complete_paths_and_projection_precedence(
    auth_client, path, db_session, active_user, additional
):
    learner, headers, _, _ = path("educator_instructor")
    if additional == "learner":
        add_role(db_session, active_user, "learner")
        learner.learner_user_id = active_user.id
    else:
        # A guardian relationship without the guardian role cannot widen the projection.
        guardian(db_session, active_user, learner, "manager")
        if additional != "administrator_only":
            add_role(db_session, active_user, "guardian")
        if additional.startswith("administrator"):
            add_role(db_session, active_user, "administrator")
    db_session.commit()
    response = auth_client.get(f"/api/v1/learners/{learner.id}", headers=headers)
    assert set(response.json()) == (BASIC_KEYS if additional == "administrator_only" else FULL_KEYS)
    listed = auth_client.get("/api/v1/learners", headers=headers).json()["items"]
    assert [item["id"] for item in listed].count(str(learner.id)) == 1


def test_administrator_with_independent_guardian_grant(auth_client, path, db_session, active_user):
    learner, headers, _, _ = path("administrator")
    add_role(db_session, active_user, "guardian")
    guardian(db_session, active_user, learner, "manager")
    db_session.commit()
    assert auth_client.get(f"/api/v1/learners/{learner.id}", headers=headers).status_code == 200
    assert (
        auth_client.patch(
            f"/api/v1/learners/{learner.id}/preferences",
            headers=headers,
            json={"row_version": 0, "theme": "dark"},
        ).status_code
        == 200
    )


def test_pagination_filters_before_limit_and_forged_cursor_never_authorizes(
    auth_client, path, db_session, active_user
):
    initial, headers, _, _ = path("guardian_manager")
    # Deliberately interleave inaccessible, archived, revoked and eligible UUIDs.
    initial.archived_at = auth_repo.now(db_session)
    allowed = []
    for number in range(1, 33):
        learner = add_profile(db_session, active_user, id=UUID(int=number))
        if number % 2 == 0:
            relation = guardian(db_session, active_user, learner)
            if number == 4:
                learner.archived_at = auth_repo.now(db_session)
            elif number == 8:
                relation.revoked_at = auth_repo.now(db_session)
                relation.revoked_by_user_id = active_user.id
            else:
                allowed.append(str(learner.id))
    db_session.commit()
    seen, cursor = [], None
    while True:
        params = {"limit": 3, **({"cursor": cursor} if cursor else {})}
        response = auth_client.get("/api/v1/learners", params=params, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert set(data) == {"items", "next_cursor"}
        items = [row["id"] for row in data["items"]]
        seen.extend(items)
        cursor = data["next_cursor"]
        if cursor is None:
            break
        assert len(items) == 3 and cursor == items[-1]
    assert seen == allowed
    forged = auth_client.get(
        "/api/v1/learners", params={"cursor": str(UUID(int=7)), "limit": 100}, headers=headers
    ).json()
    assert [row["id"] for row in forged["items"]] == [
        identity for identity in allowed if UUID(identity).int > 7
    ]


def test_default_limit_and_page_revocation(auth_client, path, db_session, active_user):
    first, headers, _, _ = path("guardian_viewer")
    first.archived_at = auth_repo.now(db_session)
    grants = []
    for number in range(1, 28):
        learner = add_profile(db_session, active_user, id=UUID(int=number))
        grants.append(guardian(db_session, active_user, learner))
    db_session.commit()
    page = auth_client.get("/api/v1/learners", headers=headers).json()
    assert len(page["items"]) == 25 and page["next_cursor"] == str(UUID(int=25))
    grants[25].revoked_at = auth_repo.now(db_session)
    grants[25].revoked_by_user_id = active_user.id
    db_session.commit()
    next_page = auth_client.get(
        "/api/v1/learners", params={"cursor": page["next_cursor"]}, headers=headers
    ).json()
    assert next_page == {
        "items": [{"id": str(UUID(int=27)), "display_name": "Synthetic learner"}],
        "next_cursor": None,
    }


@pytest.mark.parametrize(
    "query", [{"limit": 0}, {"limit": 101}, {"limit": "bad"}, {"cursor": "bad"}]
)
def test_invalid_pagination(auth_client, path, query):
    _, headers, _, _ = path("self")
    response = auth_client.get("/api/v1/learners", params=query, headers=headers)
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "validation_error", "message": "Invalid request"}}


def test_preferences_lifecycle_omission_null_versions_and_noop(auth_client, path, db_session):
    learner, headers, _, _ = path("guardian_manager")
    url = f"/api/v1/learners/{learner.id}/preferences"
    empty = auth_client.get(url, headers=headers).json()
    assert empty == {
        "learner_id": str(learner.id),
        "row_version": 0,
        **{key: None for key in PREFERENCE_KEYS - {"learner_id", "row_version"}},
    }
    assert db_session.scalar(select(func.count()).select_from(LearnerPreferences)) == 0
    created = auth_client.patch(
        url,
        headers=headers,
        json={
            "row_version": 0,
            "theme": "dark",
            "text_scale": "1.25",
            "reduce_motion": False,
            "preferred_language_tag": " en ",
        },
    )
    assert created.status_code == 200 and created.json()["row_version"] == 1
    assert created.json()["preferred_language_tag"] == "en"
    assert created.json()["text_scale"] == "1.25"
    reset = auth_client.patch(url, headers=headers, json={"row_version": 1, "theme": None})
    assert reset.status_code == 200 and reset.json()["row_version"] == 2
    assert reset.json()["theme"] is None and reset.json()["text_scale"] == "1.25"
    repeated = auth_client.patch(url, headers=headers, json={"row_version": 2, "theme": None})
    assert repeated.status_code == 200 and repeated.json()["row_version"] == 3
    for stale in (0, 1, 2, 4):
        conflict = auth_client.patch(
            url, headers=headers, json={"row_version": stale, "theme": "light"}
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "error": {
                "code": "version_conflict",
                "message": "Preferences changed. Reload and try again.",
            }
        }
    assert auth_client.get(url, headers=headers).json() == repeated.json()


@pytest.mark.parametrize(
    "payload",
    [
        {"row_version": 0},
        {"theme": "light"},
        {"row_version": 0, "reduce_motion": "false"},
        {"row_version": 0, "text_scale": "1.251"},
        {"row_version": 0, "display_name": "private input"},
        {"row_version": 0, "updated_by_user_id": "private input"},
        {"row_version": 0, "learner_id": "private input"},
    ],
)
def test_patch_validation_is_sanitized_and_atomic(auth_client, path, db_session, payload):
    learner, headers, _, _ = path("self")
    response = auth_client.patch(
        f"/api/v1/learners/{learner.id}/preferences", headers=headers, json=payload
    )
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "validation_error", "message": "Invalid request"}}
    assert response.headers["cache-control"] == "no-store"
    assert db_session.scalar(select(func.count()).select_from(LearnerPreferences)) == 0


def test_consent_evidence_cannot_grant_access(auth_client, path, db_session, active_user):
    _, headers, _, _ = path("guardian_manager")
    unrelated = add_profile(db_session, active_user)
    wording = "Synthetic assent, not approved wording"
    now = auth_repo.now(db_session)
    notice = ConsentNoticeVersion(
        purpose_code="learning_support",
        record_kind="learner_assent",
        version_label="synthetic",
        language_tag="en-x-test",
        notice_text=wording,
        content_sha256=hashlib.sha256(wording.encode()).hexdigest(),
        published_at=now,
        published_by_user_id=active_user.id,
    )
    db_session.add(notice)
    db_session.flush()
    db_session.add(
        ConsentRecord(
            learner_id=unrelated.id,
            notice_version_id=notice.id,
            purpose_code="learning_support",
            record_kind="learner_assent",
            decision="granted",
            sequence_no=1,
            occurred_at=now,
            recorded_by_user_id=active_user.id,
            capture_method="assisted_in_person",
        )
    )
    db_session.commit()
    url = f"/api/v1/learners/{unrelated.id}/preferences"
    assert auth_client.get(url, headers=headers).status_code == 404
    assert (
        auth_client.patch(
            url, headers=headers, json={"row_version": 0, "theme": "light"}
        ).status_code
        == 404
    )


def test_no_profile_edit_or_relationship_endpoints(auth_client, path):
    learner, headers, _, _ = path("self")
    assert (
        auth_client.patch(
            f"/api/v1/learners/{learner.id}", headers=headers, json={"display_name": "New"}
        ).status_code
        == 405
    )
    assert auth_client.post("/api/v1/learners", headers=headers, json={}).status_code == 405


@pytest.mark.parametrize(
    "kind,other_grant", [("guardian_manager", "educator"), ("educator_viewer", "guardian")]
)
def test_unmatched_role_and_relationship_cannot_combine(
    auth_client, path, db_session, active_user, kind, other_grant
):
    _, headers, _, _ = path(kind)
    unrelated = add_profile(db_session, active_user)
    (educator if other_grant == "educator" else guardian)(db_session, active_user, unrelated)
    db_session.commit()
    assert auth_client.get(f"/api/v1/learners/{unrelated.id}", headers=headers).status_code == 404
    assert str(unrelated.id) not in {
        item["id"] for item in auth_client.get("/api/v1/learners", headers=headers).json()["items"]
    }


def test_preferences_do_not_require_research_or_audio_consent(auth_client, path, db_session):
    learner, headers, _, _ = path("self")
    assert db_session.scalar(select(func.count()).select_from(ConsentRecord)) == 0
    url = f"/api/v1/learners/{learner.id}/preferences"
    assert auth_client.get(url, headers=headers).status_code == 200
    assert (
        auth_client.patch(
            url, headers=headers, json={"row_version": 0, "line_spacing": "1.50"}
        ).status_code
        == 200
    )
    assert db_session.scalar(select(func.count()).select_from(ConsentRecord)) == 0


@pytest.mark.parametrize("fault", ["stale", "creation_conflict", "database"])
def test_write_failures_roll_back_and_are_sanitized(
    auth_client, path, db_session, monkeypatch, fault
):
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError, OperationalError
    from sqlalchemy.orm.exc import StaleDataError

    from app.modules.learners import repository as repo

    learner, headers, _, _ = path("self")
    original = repo.save_preferences

    def fail(*args, **kwargs):
        original(*args, **kwargs)  # Simulate failure after flushing a partial change.
        if fault == "stale":
            raise StaleDataError("private SQL detail")
        if fault == "creation_conflict":
            underlying = Exception("private database detail")
            underlying.diag = SimpleNamespace(constraint_name="uq_learner_preferences_learner_id")
            raise IntegrityError("private SQL", {}, underlying)
        raise OperationalError("private SQL", {}, Exception("private credentials"))

    monkeypatch.setattr(repo, "save_preferences", fail)
    response = auth_client.patch(
        f"/api/v1/learners/{learner.id}/preferences",
        headers=headers,
        json={"row_version": 0, "theme": "dark"},
    )
    assert response.status_code == (503 if fault == "database" else 409)
    assert response.json()["error"]["code"] == (
        "service_unavailable" if fault == "database" else "version_conflict"
    )
    assert "private" not in response.text
    assert db_session.scalar(select(func.count()).select_from(LearnerPreferences)) == 0


def test_session_expiry_after_domain_lock_wait_is_rechecked(
    auth_client, path, db_session, monkeypatch
):
    from app.modules.learners import repository as repo

    learner, headers, _, _ = path("self")
    original = repo.preferences
    future = auth_repo.now(db_session) + timedelta(days=8)

    def delayed(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(auth_repo, "now", lambda db: future)
        return result

    monkeypatch.setattr(repo, "preferences", delayed)
    response = auth_client.patch(
        f"/api/v1/learners/{learner.id}/preferences",
        headers=headers,
        json={"row_version": 0, "theme": "dark"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
    assert db_session.scalar(select(func.count()).select_from(LearnerPreferences)) == 0
