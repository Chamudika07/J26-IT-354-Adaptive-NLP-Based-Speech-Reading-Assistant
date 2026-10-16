"""Reading API policy, privacy, history, and atomic failure paths on PostgreSQL."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from app.modules.assessments import repository as repo
from app.modules.assessments.models import (
    ReadingAssessmentResult as Result,
)
from app.modules.assessments.models import (
    ReadingAssessmentSession as Assessment,
)
from app.modules.auth import repository as auth_repo
from app.modules.auth.models import Role, UserRole
from app.modules.learners.models import (
    EducatorLearnerRelationship,
    GuardianLearnerRelationship,
    LearnerProfile,
)

pytestmark = pytest.mark.integration
KINDS = [
    "self",
    "guardian_viewer",
    "guardian_manager",
    "educator_viewer",
    "educator_instructor",
    "administrator",
]


def start(client, context):
    return client.post(
        context["base"],
        headers=context["headers"],
        json={"material_id": str(context["material"].id)},
    )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "operation", ["catalog", "start", "history", "detail", "complete", "abandon"]
)
def test_full_http_matrix(
    auth_client, assessment_setup, stored_session, observations, kind, operation
):
    c = assessment_setup(kind)
    row = stored_session(c) if operation in {"detail", "complete", "abandon"} else None
    if operation == "catalog":
        res = auth_client.get("/api/v1/assessment-materials", headers=c["headers"])
    elif operation == "start":
        res = start(auth_client, c)
    elif operation == "history":
        res = auth_client.get(c["base"], headers=c["headers"])
    elif operation == "detail":
        res = auth_client.get(f"{c['base']}/{row.id}", headers=c["headers"])
    else:
        res = auth_client.post(
            f"{c['base']}/{row.id}/{operation}",
            headers=c["headers"],
            json=observations if operation == "complete" else {"row_version": 1},
        )
    allowed = kind == "educator_instructor" or (
        kind != "administrator" and operation in {"history", "detail"}
    )
    expected = (
        (201 if operation == "start" else 200)
        if allowed
        else (403 if operation == "catalog" else 404)
    )
    assert res.status_code == expected, res.text
    assert res.headers["cache-control"] == "no-store"
    if allowed and kind != "educator_instructor":
        assert "rubric" not in res.text
        assert "passage_text" not in res.text
    for forbidden in (
        "administered_by_user_id",
        "submitted_by_user_id",
        "auth_session_id",
        "relationship_id",
        "learner_user_id",
        "consent",
    ):
        assert forbidden not in res.text


@pytest.mark.parametrize(
    "operation", ["catalog", "start", "history", "detail", "complete", "abandon"]
)
def test_unauthenticated(client, operation, observations):
    base = f"/api/v1/learners/{uuid4()}/reading-assessments"
    if operation == "catalog":
        res = client.get("/api/v1/assessment-materials")
    elif operation == "history":
        res = client.get(base)
    elif operation == "detail":
        res = client.get(f"{base}/{uuid4()}")
    elif operation == "start":
        res = client.post(base, json={"material_id": str(uuid4())})
    else:
        res = client.post(
            f"{base}/{uuid4()}/{operation}",
            json=observations if operation == "complete" else {"row_version": 1},
        )
    assert res.status_code == 401


def test_start_complete_and_immutable_history(
    auth_client, assessment_setup, observations, db_session
):
    c = assessment_setup()
    res = start(auth_client, c)
    assert res.status_code == 201
    data = res.json()
    assert data["material"]["passage_text"] == c["material"].passage_text
    assert data["protocol_version"] == "reading-observation-v1"
    assert data["collection_mode"] == "instructor_observed"
    assert start(auth_client, c).json()["error"]["code"] == "assessment_start_conflict"
    uri = f"{c['base']}/{data['id']}"
    completed = auth_client.post(uri + "/complete", headers=c["headers"], json=observations)
    assert completed.status_code == 200, completed.text
    result = completed.json()
    assert result["row_version"] == 2
    assert result["status"] == "completed"
    assert result["result"]["attempted_words_per_minute"] == "16.00"
    assert result["result"]["scoring_version"] == "reading-scoring-v1"
    assert result["result"]["unfamiliar_word_count"] is None
    db_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    for operation in ("complete", "abandon"):
        repeat = auth_client.post(
            uri + "/" + operation,
            headers=c["headers"],
            json=observations if operation == "complete" else {"row_version": 2},
        )
        assert repeat.json()["error"]["code"] == "assessment_state_conflict"
    assert len(auth_client.get(c["base"], headers=c["headers"]).json()["items"]) == 1
    assert start(auth_client, c).status_code == 201


def test_abandonment_and_stale_version(auth_client, assessment_setup, observations):
    c = assessment_setup()
    row = start(auth_client, c).json()
    uri = f"{c['base']}/{row['id']}"
    stale = auth_client.post(uri + "/abandon", headers=c["headers"], json={"row_version": 2})
    assert stale.json()["error"]["code"] == "version_conflict"
    res = auth_client.post(uri + "/abandon", headers=c["headers"], json={"row_version": 1})
    assert res.status_code == 200
    assert res.json()["status"] == "abandoned" and res.json()["result"] is None
    assert (
        auth_client.post(uri + "/complete", headers=c["headers"], json=observations).status_code
        == 409
    )


@pytest.mark.parametrize("state", ["revoked", "expired", "archived", "viewer", "role_revoked"])
@pytest.mark.parametrize("operation", ["start", "complete", "abandon", "history"])
def test_current_access_rechecked(
    auth_client,
    assessment_setup,
    stored_session,
    observations,
    db_session,
    active_user,
    state,
    operation,
):
    c = assessment_setup()
    row = stored_session(c)
    if state == "revoked":
        c["relation"].revoked_at = auth_repo.now(db_session)
        c["relation"].revoked_by_user_id = active_user.id
    elif state in {"expired", "viewer"}:
        c["relation"].revoked_at = auth_repo.now(db_session)
        c["relation"].revoked_by_user_id = active_user.id
        db_session.flush()
        db_session.add(
            EducatorLearnerRelationship(
                educator_user_id=active_user.id,
                learner_id=c["learner"].id,
                granted_by_user_id=active_user.id,
                access_level="viewer" if state == "viewer" else "instructor",
                created_at=auth_repo.now(db_session) - timedelta(days=2),
                expires_at=auth_repo.now(db_session)
                + timedelta(days=1 if state == "viewer" else -1),
            )
        )
    elif state == "archived":
        c["learner"].archived_at = auth_repo.now(db_session)
    else:
        assignment = db_session.scalar(select(UserRole).where(UserRole.user_id == active_user.id))
        assignment.revoked_at = auth_repo.now(db_session)
        assignment.revoked_by_user_id = active_user.id
    db_session.flush()
    if operation == "start":
        res = start(auth_client, c)
    elif operation == "history":
        res = auth_client.get(c["base"], headers=c["headers"])
    else:
        res = auth_client.post(
            f"{c['base']}/{row.id}/{operation}",
            headers=c["headers"],
            json=observations if operation == "complete" else {"row_version": 1},
        )
    assert res.status_code == (200 if state == "viewer" and operation == "history" else 404)


@pytest.mark.parametrize("kind", KINDS)
def test_cross_learner_scope(
    auth_client, assessment_setup, stored_session, observations, db_session, active_user, kind
):
    c = assessment_setup(kind)
    row = stored_session(c)
    other = LearnerProfile(display_name="Other synthetic", created_by_user_id=active_user.id)
    db_session.add(other)
    db_session.flush()
    alien = stored_session(c, learner_id=other.id)
    db_session.commit()
    base = f"/api/v1/learners/{other.id}/reading-assessments"
    assert auth_client.get(base, headers=c["headers"]).status_code == 404
    assert auth_client.get(f"{base}/{row.id}", headers=c["headers"]).status_code == 404
    assert (
        auth_client.post(
            f"{base}/{row.id}/complete", headers=c["headers"], json=observations
        ).status_code
        == 404
    )
    # An accessible learner path must not resolve another learner's assessment ID.
    assert auth_client.get(f"{c['base']}/{alien.id}", headers=c["headers"]).status_code == 404


@pytest.mark.parametrize(
    "values",
    [
        {"reading_duration_ms": 0},
        {"reading_duration_ms": -1},
        {"correct_word_count": 9},
        {"attempted_word_count": 12},
        {"omission_count": 4},
        {"unfamiliar_word_count": 9},
        {"comprehension_correct": 1, "comprehension_total": 2},
        {"insertion_count": True},
        {"row_version": "1"},
        {"scoring_version": "forged"},
    ],
)
def test_invalid_measurements_are_atomic_and_sanitized(
    auth_client, assessment_setup, observations, db_session, values
):
    c = assessment_setup()
    row = start(auth_client, c).json()
    res = auth_client.post(
        f"{c['base']}/{row['id']}/complete", headers=c["headers"], json=observations | values
    )
    assert res.status_code == 422
    assert res.json() == {"error": {"code": "validation_error", "message": "Invalid request"}}
    assert db_session.get(Assessment, UUID(row["id"])).status == "started"
    assert db_session.scalar(select(func.count()).select_from(Result)) == 0


@pytest.mark.parametrize(
    "correct,total,expected", [(None, None, 422), (1, 3, 422), (3, 2, 422), (1, 2, 200)]
)
def test_material_comprehension_requirements(
    auth_client, assessment_setup, observations, correct, total, expected
):
    c = assessment_setup(
        comprehension_question_count=2,
        comprehension_prompt_text="Two questions",
        comprehension_rubric_text="Private synthetic rubric",
    )
    row = start(auth_client, c).json()
    res = auth_client.post(
        f"{c['base']}/{row['id']}/complete",
        headers=c["headers"],
        json=observations | {"comprehension_correct": correct, "comprehension_total": total},
    )
    assert res.status_code == expected
    if expected == 200:
        assert res.json()["result"]["comprehension_percentage"] == "50.00"


@pytest.mark.parametrize("inactive", [True, False])
def test_unknown_or_inactive_material(auth_client, assessment_setup, inactive):
    c = assessment_setup(is_active=False)
    res = auth_client.post(
        c["base"],
        headers=c["headers"],
        json={
            "material_id": str(c["material"].id if inactive else uuid4()),
        },
    )
    assert res.status_code == 404


def test_bound_material_version_and_retirement(
    auth_client, assessment_setup, material_factory, observations, db_session
):
    c = assessment_setup()
    original_id = c["material"].id
    row = start(auth_client, c).json()
    material_factory(code=c["material"].code, version=2, word_count=20)
    c["material"].is_active = False
    db_session.flush()
    catalog = auth_client.get("/api/v1/assessment-materials", headers=c["headers"])
    assert all(item["id"] != str(original_id) for item in catalog.json()["items"])
    assert "passage_text" not in catalog.text and "rubric" not in catalog.text
    res = auth_client.post(
        f"{c['base']}/{row['id']}/complete", headers=c["headers"], json=observations
    )
    assert res.status_code == 200
    assert res.json()["material"]["id"] == str(original_id)
    assert res.json()["material"]["version"] == 1


def test_history_pagination_ties_empty_and_forged_cursor(auth_client, assessment_setup, db_session):
    c = assessment_setup()
    assert auth_client.get(c["base"], headers=c["headers"]).json() == {
        "items": [],
        "next_cursor": None,
    }
    identities = []
    for _ in range(4):
        row = start(auth_client, c).json()
        identities.append(row["id"])
        auth_client.post(
            f"{c['base']}/{row['id']}/abandon", headers=c["headers"], json={"row_version": 1}
        )
    page = auth_client.get(c["base"], headers=c["headers"], params={"limit": 2}).json()
    next_page = auth_client.get(
        c["base"], headers=c["headers"], params={"limit": 2, "cursor": page["next_cursor"]}
    ).json()
    assert [i["id"] for i in page["items"] + next_page["items"]] == identities[::-1]
    assert next_page["next_cursor"] is None
    assert "passage_text" not in str(page)
    assert "rubric" not in str(page)
    forged = "2999-01-01T00:00:00+00:00|" + str(uuid4())
    assert (
        len(
            auth_client.get(c["base"], headers=c["headers"], params={"cursor": forged}).json()[
                "items"
            ]
        )
        == 4
    )
    for params in ({"limit": 0}, {"limit": 101}, {"cursor": "bad"}):
        assert auth_client.get(c["base"], headers=c["headers"], params=params).status_code == 422


def test_atomic_database_failure_after_result_insert(
    auth_client, assessment_setup, observations, monkeypatch, db_session
):
    c = assessment_setup()
    row = start(auth_client, c).json()
    original = repo.insert_result

    def fail(db, result):
        original(db, result)
        raise OperationalError("sensitive statement", {"private": "content"}, Exception("private"))

    monkeypatch.setattr(repo, "insert_result", fail)
    res = auth_client.post(
        f"{c['base']}/{row['id']}/complete", headers=c["headers"], json=observations
    )
    assert res.status_code == 503
    assert res.json() == {
        "error": {"code": "service_unavailable", "message": "Service unavailable"}
    }
    assert db_session.get(Assessment, UUID(row["id"])).status == "started"
    assert db_session.scalar(select(func.count()).select_from(Result)) == 0


def test_mixed_role_paths_do_not_grant_write(
    auth_client, assessment_setup, stored_session, observations, db_session, active_user
):
    c = assessment_setup("educator_viewer")
    guardian_role = db_session.scalar(select(Role).where(Role.code == "guardian"))
    db_session.add(
        UserRole(
            user_id=active_user.id, role_id=guardian_role.id, granted_by_user_id=active_user.id
        )
    )
    db_session.add(
        GuardianLearnerRelationship(
            guardian_user_id=active_user.id,
            learner_id=c["learner"].id,
            access_level="manager",
            granted_by_user_id=active_user.id,
        )
    )
    db_session.flush()
    row = stored_session(c)
    assert start(auth_client, c).status_code == 404
    assert (
        auth_client.post(
            f"{c['base']}/{row.id}/complete", headers=c["headers"], json=observations
        ).status_code
        == 404
    )


def test_unknown_scoring_version_fails_closed(
    auth_client, assessment_setup, stored_session, db_session, observations, active_user
):
    c = assessment_setup()
    row = stored_session(c)
    now = auth_repo.now(db_session)
    db_session.add(
        Result(
            session_id=row.id,
            submitted_by_user_id=active_user.id,
            submitted_at=now,
            scoring_version="future-version",
            **{k: v for k, v in observations.items() if k != "row_version"},
        )
    )
    db_session.flush()
    row.status, row.completed_at = "completed", now
    db_session.flush()
    res = auth_client.get(f"{c['base']}/{row.id}", headers=c["headers"])
    assert res.status_code == 503


def test_consent_evidence_does_not_grant_assessment_access(
    auth_client, assessment_setup, db_session, active_user, observations
):
    import hashlib

    from app.modules.learners.models import ConsentNoticeVersion, ConsentRecord

    c = assessment_setup()
    unrelated = LearnerProfile(
        display_name="Synthetic unrelated", created_by_user_id=active_user.id
    )
    db_session.add(unrelated)
    now = auth_repo.now(db_session)
    wording = "Synthetic assent, not approved wording"
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
    base = f"/api/v1/learners/{unrelated.id}/reading-assessments"
    assert auth_client.get(base, headers=c["headers"]).status_code == 404
    assert (
        auth_client.post(
            base, headers=c["headers"], json={"material_id": str(c["material"].id)}
        ).status_code
        == 404
    )
    # Ordinary assessment needs no research/audio consent record.
    row = start(auth_client, c).json()
    assert (
        auth_client.post(
            f"{c['base']}/{row['id']}/complete", headers=c["headers"], json=observations
        ).status_code
        == 200
    )


def test_start_and_abandon_forbid_extra_fields(auth_client, assessment_setup):
    c = assessment_setup()
    res = auth_client.post(
        c["base"],
        headers=c["headers"],
        json={
            "material_id": str(c["material"].id),
            "collection_mode": "self_reported",
        },
    )
    assert res.status_code == 422
    row = start(auth_client, c).json()
    assert (
        auth_client.post(
            f"{c['base']}/{row['id']}/abandon",
            headers=c["headers"],
            json={"row_version": 1, "actor_id": str(uuid4())},
        ).status_code
        == 422
    )


def test_catalog_pagination_and_viewer_does_not_receive_rubric(
    auth_client, assessment_setup, material_factory, stored_session
):
    c = assessment_setup(
        "educator_viewer",
        comprehension_question_count=1,
        comprehension_prompt_text="Synthetic question",
        comprehension_rubric_text="Private synthetic rubric",
    )
    row = stored_session(c)
    detail = auth_client.get(f"{c['base']}/{row.id}", headers=c["headers"])
    assert detail.status_code == 200
    assert "rubric" not in detail.text and "passage_text" not in detail.text
    assert auth_client.get("/api/v1/assessment-materials", headers=c["headers"]).status_code == 403


def test_catalog_cursor(auth_client, assessment_setup, material_factory):
    c = assessment_setup()
    materials = [c["material"], material_factory(), material_factory()]
    first = auth_client.get(
        "/api/v1/assessment-materials", headers=c["headers"], params={"limit": 2}
    )
    second = auth_client.get(
        "/api/v1/assessment-materials",
        headers=c["headers"],
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )
    assert [x["id"] for x in first.json()["items"] + second.json()["items"]] == sorted(
        str(m.id) for m in materials
    )
    assert second.json()["next_cursor"] is None


def test_stale_completion_does_not_insert_result(auth_client, assessment_setup, observations):
    c = assessment_setup()
    row = start(auth_client, c).json()
    res = auth_client.post(
        f"{c['base']}/{row['id']}/complete",
        headers=c["headers"],
        json=observations | {"row_version": 2},
    )
    assert res.json()["error"]["code"] == "version_conflict"
    read = auth_client.get(f"{c['base']}/{row['id']}", headers=c["headers"]).json()
    assert read["status"] == "started" and read["result"] is None


def test_history_cursor_tie_breaker(auth_client, assessment_setup, stored_session, db_session):
    c = assessment_setup()
    now = auth_repo.now(db_session)
    identities = []
    for _ in range(4):
        row = stored_session(c, started_at=now)
        identities.append(str(row.id))
        row.status, row.abandoned_at = "abandoned", auth_repo.now(db_session)
        db_session.flush()
    db_session.commit()
    seen, cursor = [], None
    for _ in range(4):
        params = {"limit": 1}
        if cursor is not None:
            params["cursor"] = cursor
        res = auth_client.get(c["base"], headers=c["headers"], params=params).json()
        seen.extend(i["id"] for i in res["items"])
        cursor = res["next_cursor"]
    assert seen == sorted(identities, reverse=True)
    assert cursor is None


def test_history_access_revocation_between_pages(
    auth_client, assessment_setup, db_session, active_user
):
    c = assessment_setup()
    for _ in range(2):
        row = start(auth_client, c).json()
        auth_client.post(
            f"{c['base']}/{row['id']}/abandon", headers=c["headers"], json={"row_version": 1}
        )
    first = auth_client.get(c["base"], headers=c["headers"], params={"limit": 1}).json()
    c["relation"].revoked_at = auth_repo.now(db_session)
    c["relation"].revoked_by_user_id = active_user.id
    db_session.commit()
    assert (
        auth_client.get(
            c["base"], headers=c["headers"], params={"cursor": first["next_cursor"]}
        ).status_code
        == 404
    )
