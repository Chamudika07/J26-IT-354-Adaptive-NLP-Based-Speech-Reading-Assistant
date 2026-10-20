"""Full authorization matrix, ownership, projections, and failure recovery."""

import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.auth import repository as auth_repo
from app.modules.auth.models import Role, UserRole
from app.modules.learners.models import GuardianLearnerRelationship, LearnerProfile
from app.modules.reading_materials import pipeline, service
from app.modules.reading_materials.models import ReadingMaterial as Material
from app.modules.reading_materials.models import ReadingMaterialProcessingRun as Run
from app.modules.reading_materials.models import ReadingMaterialRevision as Revision

pytestmark = pytest.mark.integration
KINDS = [
    "self",
    "guardian_viewer",
    "guardian_manager",
    "educator_viewer",
    "educator_instructor",
    "administrator",
]
PAYLOAD = {"title": "Synthetic original", "language_tag": "en", "text": "A cat rests. A dog runs!"}


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "operation",
    [
        "create",
        "list",
        "detail",
        "revise",
        "revisions",
        "revision",
        "process",
        "runs",
        "run",
        "archive",
    ],
)
def test_permission_matrix(auth_client, setup_material, stored_run, kind, operation):
    c = setup_material(kind)
    r = stored_run(c)
    requests = {
        "create": ("post", c["base"], PAYLOAD),
        "list": ("get", c["base"], None),
        "detail": ("get", c["detail"], None),
        "revise": ("post", c["revisions"], PAYLOAD | {"row_version": 1}),
        "revisions": ("get", c["revisions"], None),
        "revision": ("get", c["revisions"] + "/" + str(c["revision"].id), None),
        "process": ("post", c["runs"], {}),
        "runs": ("get", c["runs"], None),
        "run": ("get", c["runs"] + "/" + str(r.id), None),
        "archive": ("post", c["detail"] + "/archive", {"row_version": 1}),
    }
    method, url, body = requests[operation]
    kwargs = {"headers": c["headers"]}
    if body is not None:
        kwargs["json"] = body
    res = getattr(auth_client, method)(url, **kwargs)
    allowed = kind == "educator_instructor" or (method == "get" and kind != "administrator")
    expected = (201 if operation in {"create", "revise"} else 200) if allowed else 404
    assert res.status_code == expected, res.text
    assert res.headers["cache-control"] == "no-store"
    for private in (
        "created_by_user_id",
        "requested_by_user_id",
        "learner_user_id",
        "source_sha256",
        "normalized_sha256",
        "pipeline_fingerprint",
        "relationship_id",
    ):
        assert private not in res.text


def test_create_revise_process_profile_and_archive(auth_client, setup_material, db_session):
    c = setup_material()
    res = auth_client.post(c["base"], json=PAYLOAD, headers=c["headers"])
    assert res.status_code == 201
    material = res.json()
    detail = c["base"] + "/" + material["id"]
    revisions = detail + "/revisions"
    original_id = material["latest_revision"]["id"]
    assert material["latest_revision"]["revision_number"] == 1
    res = auth_client.post(
        revisions,
        json=PAYLOAD | {"row_version": 1, "text": "A blue bird flies."},
        headers=c["headers"],
    )
    assert res.status_code == 201
    assert res.json()["row_version"] == 2
    assert res.json()["latest_revision"]["revision_number"] == 2
    assert (
        auth_client.post(
            revisions, json=PAYLOAD | {"row_version": 1}, headers=c["headers"]
        ).status_code
        == 409
    )
    original = auth_client.get(revisions + "/" + original_id, headers=c["headers"]).json()
    assert original["original_text"] == PAYLOAD["text"]
    runs = revisions + "/" + original_id + "/processing-runs"
    res = auth_client.post(runs, headers=c["headers"])
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["status"] == "succeeded"
    assert data["sentences"] is None
    profile = data["profile"]
    assert profile["length_load"] == {"character_count": 24, "word_count": 6, "sentence_count": 2}
    assert profile["word_form_characteristics"] == {
        "unique_word_count": 5,
        "average_word_length": "2.83",
        "maximum_word_length": 5,
        "lexical_diversity": "0.83",
    }
    assert profile["sentence_structure"] == {
        "average_sentence_length": "3.00",
        "maximum_sentence_length": 3,
    }
    assert profile["vocabulary"] == {"status": "not_evaluated"}
    assert set(profile) == {
        "material_id",
        "revision_id",
        "processing_run_id",
        "language_tag",
        "pipeline_version",
        "profile_schema_version",
        "completed_at",
        "length_load",
        "word_form_characteristics",
        "sentence_structure",
        "vocabulary",
    }
    assert auth_client.post(runs, headers=c["headers"]).status_code == 200
    full = auth_client.get(
        runs + "/" + data["id"], params={"include_sentences": True}, headers=c["headers"]
    ).json()
    assert [s["original_text"] for s in full["sentences"]] == ["A cat rests.", "A dog runs!"]
    assert (
        auth_client.post(
            detail + "/archive", json={"row_version": 1}, headers=c["headers"]
        ).status_code
        == 409
    )
    assert (
        auth_client.post(
            detail + "/archive", json={"row_version": 2}, headers=c["headers"]
        ).status_code
        == 200
    )
    assert auth_client.get(detail, headers=c["headers"]).status_code == 404
    assert auth_client.post(runs, headers=c["headers"]).status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        {"language_tag": "si"},
        {"language_tag": "ta"},
        {"language_tag": "en-GB"},
        {"text": ""},
        {"text": "  \n\t"},
        {"text": "a\x00b"},
        {"text": "a\x01b"},
        {"text": "a" * 50001},
        {"collection_mode": "forged"},
        {"title": " "},
    ],
)
def test_input_validation_sanitized(auth_client, setup_material, change):
    c = setup_material()
    res = auth_client.post(c["base"], json=PAYLOAD | change, headers=c["headers"])
    assert res.status_code == 422
    assert res.json() == {"error": {"code": "validation_error", "message": "Invalid request"}}


def test_punctuation_only_creates_no_run(auth_client, setup_material, db_session):
    c = setup_material(source="... !!! 123")
    res = auth_client.post(c["runs"], headers=c["headers"])
    assert res.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Run)) == 0


@pytest.mark.parametrize("state", ["revoked", "expired", "archived"])
def test_creator_loses_access(auth_client, setup_material, db_session, active_user, state):
    c = setup_material(expired=state == "expired")
    actor_id = active_user.id
    if state == "revoked":
        c["relation"].revoked_at = auth_repo.now(db_session)
        c["relation"].revoked_by_user_id = actor_id
    if state == "archived":
        c["learner"].archived_at = auth_repo.now(db_session)
    db_session.commit()
    assert auth_client.get(c["detail"], headers=c["headers"]).status_code == 404
    assert auth_client.post(c["runs"], headers=c["headers"]).status_code == 404


@pytest.mark.parametrize("kind", KINDS)
def test_cross_learner_and_nested_scope(
    auth_client, setup_material, stored_run, db_session, active_user, kind
):
    c = setup_material(kind)
    row = stored_run(c)
    other = LearnerProfile(display_name="Other synthetic", created_by_user_id=active_user.id)
    db_session.add(other)
    db_session.commit()
    alien = c["detail"].replace(str(c["learner"].id), str(other.id))
    assert auth_client.get(alien, headers=c["headers"]).status_code == 404
    assert (
        auth_client.get(c["revisions"] + "/" + str(uuid4()), headers=c["headers"]).status_code
        == 404
    )
    assert auth_client.get(c["runs"] + "/" + str(uuid4()), headers=c["headers"]).status_code == 404
    fake_revision = c["runs"].replace(str(c["revision"].id), str(uuid4()))
    assert (
        auth_client.get(fake_revision + "/" + str(row.id), headers=c["headers"]).status_code == 404
    )


def test_source_hash_exact_unicode(auth_client, setup_material, db_session):
    c = setup_material()
    source = " Cafe\u0301\r\n\t! "
    res = auth_client.post(c["base"], headers=c["headers"], json=PAYLOAD | {"text": source})
    from uuid import UUID

    revision = db_session.get(Revision, UUID(res.json()["latest_revision"]["id"]))
    assert revision.original_text == source
    assert revision.source_sha256 == hashlib.sha256(source.encode("utf-8")).hexdigest()


def test_failed_run_retry_and_no_leak(auth_client, setup_material, monkeypatch, caplog):
    c = setup_material()
    real = pipeline.process

    def broken(source):
        raise RuntimeError("SECRET SOURCE " + source)

    monkeypatch.setattr(pipeline, "process", broken)
    res = auth_client.post(c["runs"], headers=c["headers"])
    assert res.status_code == 503
    assert "SECRET SOURCE" not in res.text + caplog.text
    assert PAYLOAD["text"] not in res.text + caplog.text
    rows = auth_client.get(c["runs"], headers=c["headers"]).json()["items"]
    assert len(rows) == 1 and rows[0]["failure_code"] == "pipeline_failed"
    failed = auth_client.get(c["runs"] + "/" + rows[0]["id"], headers=c["headers"]).json()
    assert failed["profile"] is None
    monkeypatch.setattr(pipeline, "process", real)
    res = auth_client.post(c["runs"], headers=c["headers"])
    assert res.status_code == 201 and res.json()["attempt_number"] == 2


def test_live_duplicate_and_expired_recovery(auth_client, setup_material, stored_run, db_session):
    c = setup_material()
    row = stored_run(c, status="running", expired=True)
    res = auth_client.post(c["runs"], headers=c["headers"])
    assert res.status_code == 201 and res.json()["attempt_number"] == 2
    db_session.refresh(row)
    assert row.failure_code == "processing_interrupted"


def test_live_claim_conflict(auth_client, setup_material, stored_run):
    c = setup_material()
    stored_run(c, status="running")
    assert (
        auth_client.post(c["runs"], headers=c["headers"]).json()["error"]["code"]
        == "processing_conflict"
    )


def test_new_fingerprint_preserves_old_profile(auth_client, setup_material, monkeypatch):
    c = setup_material()
    first = auth_client.post(c["runs"], headers=c["headers"]).json()
    monkeypatch.setattr(pipeline, "VERSION", "reading-pipeline-v2-test")
    second = auth_client.post(c["runs"], headers=c["headers"])
    assert second.status_code == 201 and second.json()["id"] != first["id"]
    old = auth_client.get(c["runs"] + "/" + first["id"], headers=c["headers"]).json()
    assert old == first


def test_revocation_during_compute_and_no_database_locks(
    auth_client, setup_material, db_session, active_user, monkeypatch
):
    c = setup_material()
    relation_id = c["relation"].id
    actor_id = active_user.id
    real = pipeline.process

    def compute(source):
        assert not db_session.in_transaction()
        from app.modules.learners.models import EducatorLearnerRelationship

        relation = db_session.get(EducatorLearnerRelationship, relation_id)
        relation.revoked_at = auth_repo.now(db_session)
        relation.revoked_by_user_id = actor_id
        db_session.commit()
        return real(source)

    monkeypatch.setattr(pipeline, "process", compute)
    assert auth_client.post(c["runs"], headers=c["headers"]).status_code == 404
    run = db_session.scalar(select(Run))
    assert run.status == "running" and run.normalized_text is None


def test_mixed_role_paths(auth_client, setup_material, db_session, active_user):
    c = setup_material("educator_viewer")
    role = db_session.scalar(select(Role).where(Role.code == "guardian"))
    db_session.add(
        UserRole(user_id=active_user.id, role_id=role.id, granted_by_user_id=active_user.id)
    )
    db_session.add(
        GuardianLearnerRelationship(
            guardian_user_id=active_user.id,
            learner_id=c["learner"].id,
            access_level="manager",
            granted_by_user_id=active_user.id,
        )
    )
    db_session.commit()
    assert auth_client.post(c["runs"], headers=c["headers"]).status_code == 404
    assert auth_client.post(c["base"], headers=c["headers"], json=PAYLOAD).status_code == 404


def test_pagination_and_revision_history(auth_client, setup_material):
    c = setup_material()
    for _ in range(3):
        assert auth_client.post(c["base"], headers=c["headers"], json=PAYLOAD).status_code == 201
    first = auth_client.get(c["base"], headers=c["headers"], params={"limit": 2}).json()
    second = auth_client.get(
        c["base"], headers=c["headers"], params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert len({i["id"] for i in first["items"] + second["items"]}) == 4
    assert second["next_cursor"] is None
    for version in range(1, 4):
        assert (
            auth_client.post(
                c["revisions"], headers=c["headers"], json=PAYLOAD | {"row_version": version}
            ).status_code
            == 201
        )
    first = auth_client.get(c["revisions"], headers=c["headers"], params={"limit": 2}).json()
    second = auth_client.get(
        c["revisions"], headers=c["headers"], params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert [r["revision_number"] for r in first["items"] + second["items"]] == [4, 3, 2, 1]
    for params in ({"limit": 0}, {"limit": 101}, {"cursor": "bad"}):
        assert auth_client.get(c["base"], headers=c["headers"], params=params).status_code == 422


def test_material_creation_rolls_back_revision_failure(
    auth_client, setup_material, monkeypatch, db_session
):
    from sqlalchemy.exc import OperationalError

    c = setup_material()
    before = db_session.scalar(select(func.count()).select_from(Material))

    def fail(*args, **kwargs):
        raise OperationalError("private", {}, Exception("private text"))

    monkeypatch.setattr(service, "add_revision", fail)
    res = auth_client.post(c["base"], headers=c["headers"], json=PAYLOAD)
    assert res.status_code == 503 and "private text" not in res.text
    assert db_session.scalar(select(func.count()).select_from(Material)) == before


def test_actual_revision_and_run_parent_mismatch(auth_client, setup_material):
    c = setup_material()
    second = auth_client.post(c["base"], headers=c["headers"], json=PAYLOAD).json()
    second_revision = second["latest_revision"]["id"]
    second_base = c["base"] + "/" + second["id"] + "/revisions/" + second_revision
    run = auth_client.post(second_base + "/processing-runs", headers=c["headers"]).json()
    assert (
        auth_client.get(c["revisions"] + "/" + second_revision, headers=c["headers"]).status_code
        == 404
    )
    assert auth_client.get(c["runs"] + "/" + run["id"], headers=c["headers"]).status_code == 404
    assert (
        auth_client.post(
            c["revisions"] + "/" + second_revision + "/processing-runs", headers=c["headers"]
        ).status_code
        == 404
    )


def test_processing_history_pagination_and_invalid_controls(
    auth_client, setup_material, stored_run
):
    c = setup_material()
    first = stored_run(c, status="failed", attempt=1)
    second = stored_run(c, status="failed", attempt=2)
    third = stored_run(c, status="failed", attempt=3)
    page = auth_client.get(c["runs"], headers=c["headers"], params={"limit": 2}).json()
    last = auth_client.get(
        c["runs"], headers=c["headers"], params={"limit": 2, "cursor": page["next_cursor"]}
    ).json()
    assert {r["id"] for r in page["items"] + last["items"]} == {
        str(first.id),
        str(second.id),
        str(third.id),
    }
    assert last["next_cursor"] is None
    assert (
        auth_client.post(
            c["runs"], headers=c["headers"], json={"pipeline_version": "forged"}
        ).status_code
        == 422
    )
    assert (
        auth_client.get(
            c["runs"] + "/" + str(first.id),
            headers=c["headers"],
            params={"include_sentences": "invalid"},
        ).status_code
        == 422
    )


def test_failed_result_has_no_sentences_or_profile(auth_client, setup_material, stored_run):
    c = setup_material()
    row = stored_run(c, status="failed")
    res = auth_client.get(
        c["runs"] + "/" + str(row.id), headers=c["headers"], params={"include_sentences": True}
    )
    assert res.status_code == 200
    assert res.json()["profile"] is None and res.json()["sentences"] is None
