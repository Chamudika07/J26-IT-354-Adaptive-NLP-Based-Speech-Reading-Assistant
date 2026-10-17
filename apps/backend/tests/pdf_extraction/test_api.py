import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.reading_materials.models import ReadingMaterialRevision as Revision
from app.modules.reading_materials.pdf.models import ExtractionRun, Source

from .conftest import pdf_bytes

pytestmark = pytest.mark.integration


def upload(client, ctx, data=None, request_id=None, title="Synthetic PDF", **kwargs):
    return client.post(
        ctx["base"] + "/pdf",
        headers=ctx["headers"],
        data={
            "title": title,
            "language_tag": "en",
            "upload_request_id": str(request_id or uuid4()),
        },
        files={
            "file": (
                "../../private.pdf",
                data if data is not None else pdf_bytes(),
                "application/pdf",
            )
        },
        **kwargs,
    )


def test_lifecycle(auth_client, setup_material, pdf_storage, db_session):
    ctx = setup_material()
    data = pdf_bytes()
    request = uuid4()
    response = upload(auth_client, ctx, data, request)
    assert response.status_code == 201, response.text
    value = response.json()
    source = value["source"]
    run = value["extraction"]
    assert run["status"] == "extracted" and run["revision_id"]
    assert response.headers["cache-control"] == "no-store"
    assert (
        not {"storage_key", "file_sha256", "created_by_user_id", "storage_backend"} & source.keys()
    )
    stored = db_session.get(Source, source["id"])
    assert stored.file_sha256 == hashlib.sha256(data).hexdigest()
    revision = db_session.get(Revision, run["revision_id"])
    assert revision.source_kind == "pdf_text" and revision.extraction_run_id == uuid4().__class__(
        run["id"]
    )
    base = ctx["base"] + "/pdf-sources/" + source["id"]
    evidence = auth_client.get(
        base + "/extraction-runs/" + run["id"] + "?include_evidence=true", headers=ctx["headers"]
    )
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["assembled_text"] == revision.original_text
    assert evidence.json()["lexical_page_coverage"] == "1.00"
    processed = auth_client.post(
        ctx["base"]
        + "/"
        + run["material_id"]
        + "/revisions/"
        + run["revision_id"]
        + "/processing-runs",
        headers=ctx["headers"],
    )
    assert processed.status_code == 201, processed.text
    repeated = upload(auth_client, ctx, data, request)
    assert repeated.status_code == 200 and repeated.json()["extraction"]["id"] == run["id"]
    assert upload(auth_client, ctx, data, request, title="Different").status_code == 409
    assert upload(auth_client, ctx, pdf_bytes(("A dog.",)), request).status_code == 409
    assert auth_client.get(base, headers=ctx["headers"]).status_code == 200
    assert auth_client.get(ctx["base"] + "/pdf-sources", headers=ctx["headers"]).json()["items"]
    assert auth_client.get(base + "/extraction-runs", headers=ctx["headers"]).json()["items"]
    assert (
        auth_client.post(
            base + "/archive", headers=ctx["headers"], json={"row_version": 0}
        ).status_code
        == 422
    )
    assert (
        auth_client.post(
            base + "/archive", headers=ctx["headers"], json={"row_version": source["row_version"]}
        ).status_code
        == 200
    )
    assert auth_client.get(base, headers=ctx["headers"]).status_code == 404
    assert auth_client.post(base + "/extraction-runs", headers=ctx["headers"]).status_code == 409


@pytest.mark.parametrize(
    "kind", ["self", "guardian_viewer", "guardian_manager", "educator_viewer", "administrator"]
)
def test_upload_permissions(auth_client, setup_material, pdf_storage, kind):
    ctx = setup_material(kind)
    assert upload(auth_client, ctx).status_code == 404
    res = auth_client.get(ctx["base"] + "/pdf-sources", headers=ctx["headers"])
    assert res.status_code == (404 if kind == "administrator" else 200)


@pytest.mark.parametrize(
    "data,status,code",
    [
        (pdf_bytes(("",), image=True), "ocr_required", "image_without_text"),
        (pdf_bytes(image=True), "needs_review", "ambiguous_content"),
        (pdf_bytes(encrypted=True), "failed", "encrypted_pdf"),
        (b"%PDF-corrupt", "failed", "malformed_pdf"),
    ],
)
def test_no_revision_for_unaccepted(
    auth_client, setup_material, pdf_storage, db_session, data, status, code
):
    ctx = setup_material()
    res = upload(auth_client, ctx, data)
    assert res.status_code == 201, res.text
    run = res.json()["extraction"]
    assert run["status"] == status and run["outcome_code"] == code
    assert run["revision_id"] is None and run["material_id"] is None
    assert (
        db_session.scalar(select(Revision).where(Revision.extraction_run_id == run["id"])) is None
    )


@pytest.mark.parametrize(
    "file,media,extra,status",
    [
        (b"not a pdf", "application/pdf", False, 415),
        (b"%PDF-", "text/plain", False, 415),
        (b"%PDF-", "application/pdf", True, 422),
        (b"%PDF-" + b"x" * (10 * 1024 * 1024), "application/pdf", False, 413),
    ],
)
def test_upload_validation(auth_client, setup_material, pdf_storage, file, media, extra, status):
    ctx = setup_material()
    files = [("file", ("evil.pdf", file, media))]
    if extra:
        files.append(("other", ("second.pdf", file, media)))
    res = auth_client.post(
        ctx["base"] + "/pdf",
        headers=ctx["headers"],
        files=files,
        data={"title": "Synthetic", "language_tag": "en", "upload_request_id": str(uuid4())},
    )
    assert res.status_code == status, res.text
    assert "evil.pdf" not in res.text


def test_wrong_language(auth_client, setup_material, pdf_storage):
    ctx = setup_material()
    res = auth_client.post(
        ctx["base"] + "/pdf",
        headers=ctx["headers"],
        files={"file": ("x", pdf_bytes(), "application/pdf")},
        data={"title": "Synthetic", "language_tag": "fr", "upload_request_id": str(uuid4())},
    )
    assert res.status_code == 422


def test_cross_learner_and_run(auth_client, setup_material, pdf_storage):
    ctx = setup_material()
    value = upload(auth_client, ctx).json()
    source = value["source"]["id"]
    run = value["extraction"]["id"]
    wrong = f"/api/v1/learners/{uuid4()}/reading-materials/pdf-sources/{source}"
    assert auth_client.get(wrong, headers=ctx["headers"]).status_code == 404
    assert (
        auth_client.get(
            ctx["base"] + f"/pdf-sources/{source}/extraction-runs/{uuid4()}", headers=ctx["headers"]
        ).status_code
        == 404
    )
    other = upload(auth_client, ctx).json()["source"]["id"]
    assert (
        auth_client.get(
            ctx["base"] + f"/pdf-sources/{other}/extraction-runs/{run}", headers=ctx["headers"]
        ).status_code
        == 404
    )


def test_failure_is_safe(auth_client, setup_material, pdf_storage, monkeypatch, caplog):
    from app.modules.reading_materials.pdf import runner

    def crash(*args):
        raise RuntimeError("SECRET filename content")

    monkeypatch.setattr(runner, "run", crash)
    ctx = setup_material()
    res = upload(auth_client, ctx)
    assert res.status_code == 503
    assert "SECRET" not in res.text + caplog.text


@pytest.mark.parametrize(
    "kind", ["self", "guardian_viewer", "guardian_manager", "educator_viewer", "administrator"]
)
@pytest.mark.parametrize("operation", ["source", "history", "run", "extract", "archive"])
def test_source_permission_matrix(
    auth_client, setup_material, pdf_storage, db_session, active_user, kind, operation
):
    from datetime import timedelta

    from app.modules.reading_materials import repository
    from app.modules.reading_materials.pdf import contracts

    ctx = setup_material(kind)
    row = Source(
        learner_id=ctx["learner"].id,
        created_by_user_id=active_user.id,
        title="Synthetic",
        language_tag="en",
        source_kind="pdf",
        media_type="application/pdf",
        byte_count=1,
        file_sha256="0" * 64,
        storage_backend="local-v1",
        storage_key=uuid4().hex,
        upload_request_id=uuid4(),
    )
    db_session.add(row)
    db_session.flush()
    now = repository.now(db_session)
    run = ExtractionRun(
        source_id=row.id,
        requested_by_user_id=active_user.id,
        attempt_number=1,
        status="running",
        started_at=now,
        lease_expires_at=now + timedelta(seconds=90),
        **contracts.provenance(),
        extraction_fingerprint=contracts.fingerprint(),
    )
    db_session.add(run)
    db_session.flush()
    run.status = "failed"
    run.outcome_code = "malformed_pdf"
    run.finished_at = now
    db_session.commit()
    base = ctx["base"] + f"/pdf-sources/{row.id}"
    routes = {
        "source": base,
        "history": base + "/extraction-runs",
        "run": base + f"/extraction-runs/{run.id}",
        "extract": base + "/extraction-runs",
        "archive": base + "/archive",
    }
    if operation in ("extract", "archive"):
        res = auth_client.post(
            routes[operation],
            headers=ctx["headers"],
            json={"row_version": 1} if operation == "archive" else {},
        )
        assert res.status_code == 404
    else:
        res = auth_client.get(routes[operation], headers=ctx["headers"])
        assert res.status_code == (404 if kind == "administrator" else 200)


@pytest.mark.parametrize("change", ["expired", "revoked", "learner_archived", "material_archived"])
def test_lost_access(auth_client, setup_material, pdf_storage, db_session, active_user, change):
    from app.modules.reading_materials import repository
    from app.modules.reading_materials.models import ReadingMaterial

    ctx = setup_material(expired=change == "expired")
    if change == "expired":
        assert upload(auth_client, ctx).status_code == 404
        return
    value = upload(auth_client, ctx).json()
    now = repository.now(db_session)
    actor = active_user.id
    if change == "revoked":
        ctx["relation"].revoked_at = now
        ctx["relation"].revoked_by_user_id = actor
    elif change == "learner_archived":
        ctx["learner"].archived_at = now
    else:
        db_session.get(ReadingMaterial, value["source"]["material_id"]).archived_at = now
    db_session.commit()
    base = ctx["base"] + "/pdf-sources/" + value["source"]["id"]
    assert auth_client.get(base, headers=ctx["headers"]).status_code == 404
    assert auth_client.post(base + "/extraction-runs", headers=ctx["headers"]).status_code == 404


@pytest.mark.parametrize("declared", [None, "1", "-1", "garbage"])
def test_actual_body_limit(auth_client, setup_material, pdf_storage, declared):
    from app.modules.reading_materials.pdf.contracts import MAX_BODY

    ctx = setup_material()
    headers = {**ctx["headers"], "content-type": "multipart/form-data; boundary=test"}
    if declared is not None:
        headers["content-length"] = declared
    res = auth_client.post(
        ctx["base"] + "/pdf",
        headers=headers,
        content=iter([b"x" * 65536] * (MAX_BODY // 65536 + 1)),
    )
    assert res.status_code == (422 if declared in ("-1", "garbage") else 413)


def test_unauthenticated_upload_and_storage_unavailable(auth_client, setup_material, settings):
    ctx = setup_material()
    assert auth_client.post(ctx["base"] + "/pdf", content=b"x").status_code == 401
    settings.pdf_storage_root = None
    assert upload(auth_client, ctx).status_code == 503
