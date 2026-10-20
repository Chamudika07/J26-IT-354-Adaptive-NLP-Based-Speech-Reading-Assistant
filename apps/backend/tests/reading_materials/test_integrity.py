"""Direct SQL integrity tests, including deferred aggregate validation."""

from dataclasses import asdict
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.modules.reading_materials import pipeline
from app.modules.reading_materials import repository as repo
from app.modules.reading_materials.models import ReadingMaterialProcessingRun as Run
from app.modules.reading_materials.models import ReadingMaterialSentenceFeature as Sentence

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE reading_material_revisions SET title='changed' WHERE id=:id",
        "UPDATE reading_material_revisions SET original_text='changed' WHERE id=:id",
        "DELETE FROM reading_material_revisions WHERE id=:id",
    ],
)
def test_revision_immutable(db_session, setup_material, sql):
    c = setup_material()
    identity = c["revision"].id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(text(sql), {"id": identity})


@pytest.mark.parametrize(
    "field,value",
    [
        ("learner_id", "00000000-0000-0000-0000-000000000001"),
        ("created_by_user_id", "00000000-0000-0000-0000-000000000001"),
    ],
)
def test_material_identity_immutable(db_session, setup_material, field, value):
    c = setup_material()
    identity = c["material"].id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(f"UPDATE reading_materials SET {field}=:value WHERE id=:id"),
            {"id": identity, "value": value},
        )


@pytest.mark.parametrize(
    "table,change",
    [
        ("reading_material_processing_runs", "status='running', finished_at=NULL"),
        ("reading_material_processing_runs", "word_count=word_count+1"),
        ("reading_material_processing_runs", "row_version=row_version+1"),
        ("reading_material_sentence_features", "word_count=word_count+1"),
    ],
)
def test_terminal_evidence_immutable(db_session, setup_material, stored_run, table, change):
    c = setup_material()
    row = stored_run(c)
    identity = row.id
    target = "id" if table.endswith("runs") else "run_id"
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(f"UPDATE {table} SET {change} WHERE {target}=:id"), {"id": identity}
        )


@pytest.mark.parametrize(
    "table,target",
    [
        ("reading_materials", "id"),
        ("reading_material_processing_runs", "id"),
        ("reading_material_sentence_features", "run_id"),
    ],
)
def test_no_deletion(db_session, setup_material, stored_run, table, target):
    c = setup_material()
    row = stored_run(c)
    identity = c["material"].id if table == "reading_materials" else row.id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(text(f"DELETE FROM {table} WHERE {target}=:id"), {"id": identity})


def raw_run(db, c, user, **overrides):
    now = repo.now(db)
    values = dict(
        revision_id=c["revision"].id,
        requested_by_user_id=user.id,
        attempt_number=1,
        status="running",
        started_at=now,
        lease_expires_at=now + timedelta(seconds=60),
        **pipeline.provenance(),
    )
    values.update(overrides)
    row = Run(**values)
    db.add(row)
    db.flush()
    return row


@pytest.mark.parametrize(
    "values",
    [
        {"status": "succeeded"},
        {"attempt_number": 0},
        {"pipeline_fingerprint": "not-hash"},
        {"vocabulary_mode": "enabled"},
        {"pipeline_version": ""},
        {"word_count": 1},
        {"failure_code": "private exception"},
        {"row_version": 0},
    ],
)
def test_run_constraints(db_session, setup_material, active_user, values):
    c = setup_material()
    # ORM assigns its initial row_version, so exercise that check through raw SQL below.
    if "row_version" in values:
        row = raw_run(db_session, c, active_user)
        identity = row.id
        with pytest.raises(IntegrityError), db_session.begin_nested():
            db_session.execute(
                text("UPDATE reading_material_processing_runs SET row_version=0 WHERE id=:id"),
                {"id": identity},
            )
    else:
        with pytest.raises(IntegrityError), db_session.begin_nested():
            raw_run(db_session, c, active_user, **values)


@pytest.mark.parametrize(
    "corruption",
    ["no_sentences", "word_total", "ordinal_gap", "source_bounds", "overlap", "orphan_sentences"],
)
def test_deferred_publication_consistency(db_session, setup_material, active_user, corruption):
    c = setup_material()
    row = raw_run(db_session, c, active_user)
    output = pipeline.process(c["revision"].original_text)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        if corruption != "no_sentences":
            for s in output.sentences:
                values = asdict(s)
                if s.ordinal == 2:
                    if corruption == "ordinal_gap":
                        values["ordinal"] = 3
                    if corruption == "source_bounds":
                        values["source_end"] = 5000
                    if corruption == "overlap":
                        values["analysis_start"] = 0
                db_session.add(Sentence(run_id=row.id, **values))
            db_session.flush()
        if corruption != "orphan_sentences":
            for k, v in asdict(output.document).items():
                setattr(row, k, v)
            if corruption == "word_total":
                row.word_count += 1
            row.normalized_text, row.normalized_sha256 = (
                output.normalized_text,
                output.normalized_sha256,
            )
            row.status, row.finished_at = "succeeded", repo.now(db_session)
            db_session.flush()
        db_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_partial_unique_running_and_success_rules(
    db_session, setup_material, stored_run, active_user
):
    c = setup_material()
    raw_run(db_session, c, active_user)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        raw_run(db_session, c, active_user, attempt_number=2)


def test_second_success_for_same_fingerprint_rejected(
    db_session, setup_material, stored_run, active_user
):
    c = setup_material()
    stored_run(c)
    row = raw_run(db_session, c, active_user, attempt_number=2)
    output = pipeline.process(c["revision"].original_text)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add_all([Sentence(run_id=row.id, **asdict(s)) for s in output.sentences])
        db_session.flush()
        for name, value in asdict(output.document).items():
            setattr(row, name, value)
        row.normalized_text, row.normalized_sha256 = (
            output.normalized_text,
            output.normalized_sha256,
        )
        row.status, row.finished_at = "succeeded", repo.now(db_session)
        db_session.flush()


@pytest.mark.parametrize(
    "changes",
    [
        {"language_tag": "si"},
        {"source_kind": "pdf"},
        {"title": " "},
        {"title": "a" * 201},
        {"original_text": ""},
        {"original_text": "a" * 50001},
        {"source_sha256": "0" * 64},
        {"revision_number": 0},
    ],
)
def test_revision_database_constraints(db_session, setup_material, active_user, changes):
    from sqlalchemy.exc import DataError

    from app.modules.reading_materials.models import ReadingMaterialRevision as Revision

    c = setup_material()
    values = dict(
        material_id=c["material"].id,
        revision_number=2,
        title="Synthetic",
        language_tag="en",
        source_kind="plain_text",
        original_text=c["revision"].original_text,
        source_sha256=c["revision"].source_sha256,
        created_by_user_id=active_user.id,
        created_at=repo.now(db_session),
    )
    values.update(changes)
    with pytest.raises((IntegrityError, DataError)), db_session.begin_nested():
        db_session.add(Revision(**values))
        db_session.flush()
