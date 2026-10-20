"""Direct SQL must not bypass immutable extraction and revision evidence."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.modules.reading_materials import repository as materials
from app.modules.reading_materials.pdf import contracts
from app.modules.reading_materials.pdf.models import ExtractionRun, Source

from .test_api import upload

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "table,field,value",
    [
        ("reading_material_sources", "title", "'Rewritten'"),
        ("reading_material_sources", "file_sha256", "repeat('0',64)"),
        ("reading_material_sources", "storage_key", "repeat('0',32)"),
        ("reading_material_sources", "material_id", "NULL"),
        ("reading_material_extraction_runs", "assembled_text", "'Changed text'"),
        ("reading_material_extraction_runs", "status", "'running'"),
        ("reading_material_extraction_runs", "quality_version", "'changed'"),
        ("reading_material_extraction_pages", "text_end", "0"),
        ("reading_material_revisions", "extraction_run_id", "NULL"),
    ],
)
def test_immutable(auth_client, setup_material, pdf_storage, db_session, table, field, value):
    ctx = setup_material()
    result = upload(auth_client, ctx).json()
    source = result["source"]["id"]
    run = result["extraction"]["id"]
    rev = result["extraction"]["revision_id"]
    where = {
        "reading_material_sources": f"id='{source}'",
        "reading_material_extraction_runs": f"id='{run}'",
        "reading_material_extraction_pages": f"extraction_run_id='{run}'",
        "reading_material_revisions": f"id='{rev}'",
    }[table]
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(text(f"UPDATE {table} SET {field}={value} WHERE {where}"))


@pytest.mark.parametrize(
    "table",
    [
        "reading_material_sources",
        "reading_material_extraction_runs",
        "reading_material_extraction_pages",
    ],
)
def test_no_delete(auth_client, setup_material, pdf_storage, db_session, table):
    ctx = setup_material()
    upload(auth_client, ctx)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(text(f"DELETE FROM {table}"))


@pytest.mark.parametrize(
    "change",
    [
        {"byte_count": 0},
        {"byte_count": 10485761},
        {"file_sha256": "bad"},
        {"language_tag": "fr"},
        {"source_kind": "image"},
        {"media_type": "text/plain"},
        {"title": " "},
        {"storage_key": "../path"},
        {"storage_backend": "public"},
    ],
)
def test_source_constraints(setup_material, db_session, active_user, change):
    ctx = setup_material()
    values = dict(
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
    values.update(change)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(Source(**values))
        db_session.flush()


def running(db, source, actor):
    now = materials.now(db)
    row = ExtractionRun(
        source_id=source,
        requested_by_user_id=actor,
        attempt_number=1,
        status="running",
        started_at=now,
        lease_expires_at=now + timedelta(seconds=90),
        **contracts.provenance(),
        extraction_fingerprint="a" * 64,
    )
    db.add(row)
    db.flush()
    return row


def test_partial_unique_and_terminal_state(
    auth_client, setup_material, pdf_storage, db_session, active_user
):
    ctx = setup_material()
    result = upload(auth_client, ctx).json()
    source = result["source"]["id"]
    row = running(db_session, source, active_user.id)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        duplicate = ExtractionRun(
            **{
                c.name: getattr(row, c.name)
                for c in row.__table__.columns
                if c.name not in ("id", "attempt_number")
            },
            attempt_number=2,
        )
        db_session.add(duplicate)
        db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "UPDATE reading_material_extraction_runs SET status='extracted',"
                "finished_at=clock_timestamp() WHERE id=:id"
            ),
            {"id": row.id},
        )


def test_revision_cannot_link_wrong_extraction(
    auth_client, setup_material, pdf_storage, db_session
):
    ctx = setup_material()
    result = upload(auth_client, ctx).json()
    revision = result["extraction"]["revision_id"]
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text("""INSERT INTO reading_material_revisions
            (material_id,revision_number,title,language_tag,source_kind,original_text,
            source_sha256,created_by_user_id,created_at,id,extraction_run_id)
            SELECT material_id,revision_number+10,title,language_tag,source_kind,
            original_text,source_sha256,created_by_user_id,created_at,gen_random_uuid(),
            extraction_run_id FROM reading_material_revisions WHERE id=:id"""),
            {"id": revision},
        )


@pytest.mark.parametrize(
    "fault",
    [
        "missing_pages",
        "ordinal",
        "offset",
        "aggregate",
        "wrong_material",
        "wrong_text",
        "nonaccepted_revision",
    ],
)
def test_deferred_evidence_guards(
    auth_client, setup_material, pdf_storage, db_session, active_user, fault
):
    import hashlib

    from app.modules.reading_materials.models import ReadingMaterialRevision
    from app.modules.reading_materials.pdf.models import ExtractionPage

    ctx = setup_material()
    result = upload(auth_client, ctx).json()
    source = db_session.get(Source, result["source"]["id"])
    row = running(db_session, source.id, active_user.id)
    now = materials.now(db_session)
    actor = active_user.id
    material = source.material_id
    if fault == "wrong_material":
        material = ctx["material"].id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        if fault != "missing_pages":
            db_session.add(
                ExtractionPage(
                    extraction_run_id=row.id,
                    page_number=2 if fault == "ordinal" else 1,
                    text_start=1 if fault == "offset" else 0,
                    text_end=6 if fault == "offset" else 5,
                    raw_character_count=5,
                    lexical_word_count=2,
                    text_status="lexical",
                    warning_codes=[],
                )
            )
        db_session.flush()
        row.status = "extracted"
        row.finished_at = now
        row.assembled_text = "A cat"
        row.assembled_text_sha256 = hashlib.sha256(b"A cat").hexdigest()
        row.total_page_count = 1
        row.pages_with_lexical_text = 1
        row.pages_with_zero_characters = 0
        row.pages_with_zero_lexical_words = 0
        row.extracted_character_count = 5
        row.assembled_character_count = 5
        row.lexical_word_count = 3 if fault == "aggregate" else 2
        value = "A dog" if fault == "wrong_text" else "A cat"
        if fault == "nonaccepted_revision":
            row.status = "needs_review"
            row.outcome_code = "ambiguous_content"
        db_session.add(
            ReadingMaterialRevision(
                material_id=material,
                revision_number=100,
                title=source.title,
                language_tag="en",
                source_kind="pdf_text",
                original_text=value,
                source_sha256=hashlib.sha256(value.encode()).hexdigest(),
                created_by_user_id=actor,
                created_at=now,
                extraction_run_id=row.id,
            )
        )
        db_session.flush()
        db_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
