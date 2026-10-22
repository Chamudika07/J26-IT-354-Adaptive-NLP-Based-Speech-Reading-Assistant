from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.modules.reading_materials import repository as materials
from app.modules.reading_materials.models import ReadingMaterial, ReadingMaterialRevision
from app.modules.reading_materials.pdf import repository
from app.modules.reading_materials.pdf.models import ExtractionPage

from .conftest import (
    check,
    finish,
    new_review,
    new_run,
    new_source,
    ocr_values,
    page_metadata,
    sha,
    submit,
)

pytestmark = pytest.mark.integration


def accept(
    db,
    user,
    learner,
    source,
    run,
    review,
    *,
    value=None,
    wrong_material=False,
    kind="ocr_reviewed",
    actor=None,
):
    material = ReadingMaterial(id=uuid4(), learner_id=learner, created_by_user_id=user)
    db.add(material)
    db.flush()
    source.material_id = material.id
    if wrong_material:
        other = ReadingMaterial(id=uuid4(), learner_id=learner, created_by_user_id=user)
        db.add(other)
        db.flush()
        material = other
    revision = ReadingMaterialRevision(
        id=uuid4(),
        material_id=material.id,
        revision_number=1,
        title=source.title,
        language_tag="en",
        source_kind=kind,
        original_text=value if value is not None else review.reviewed_text,
        source_sha256=sha(value if value is not None else review.reviewed_text),
        created_by_user_id=actor or user,
        created_at=materials.now(db),
        extraction_run_id=run.id,
    )
    db.add(revision)
    db.flush()
    review.status = "accepted"
    review.decided_by = user
    review.decided_at = review.updated_at = materials.now(db)
    review.decision_request_id = uuid4()
    review.decision_request_sha256 = sha("decision")
    review.accepted_revision_id = revision.id
    check(db)
    return revision


def test_candidate_has_review_and_zero_revisions(pending):
    db, user, learner, source, parent, run, review = pending
    assert run.status == "review_required" and review.status == "pending"
    assert (
        db.scalar(
            select(ReadingMaterialRevision.id).where(
                ReadingMaterialRevision.extraction_run_id == run.id
            )
        )
        is None
    )
    # Existing broad-reader PDF paths must not expose future OCR evidence.
    assert repository.run(db, source.id, run.id) is None
    assert repository.latest(db, source.id).id == parent.id
    assert [r.id for r in repository.history(db, source.id, None, 100)] == [parent.id]
    assert repository.attempts(db, source.id, run.extraction_fingerprint) == []


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "other_source",
        "running",
        "failed",
        "ocr_parent",
        "mode",
        "reason",
        "manifest_hash",
        "request_hash",
        "null_mode",
    ],
)
def test_bad_parent_and_metadata(domain, fault):
    db, user, learner, source, parent = domain
    args = ocr_values(db, parent)
    if fault == "missing":
        args["parent_extraction_run_id"] = None
    elif fault == "other_source":
        source = new_source(db, user, learner)
    elif fault in {"running", "failed", "ocr_parent"}:
        other = new_run(
            db, source, user, **(ocr_values(db, parent) if fault == "ocr_parent" else {})
        )
        if fault == "failed":
            other.status = "failed"
            other.outcome_code = "encrypted_pdf"
            other.finished_at = materials.now(db)
            db.flush()
        args["parent_extraction_run_id"] = other.id
    elif fault == "mode":
        args.update(request_mode="review_comparison", request_reason="Compare")
    elif fault == "reason":
        args["request_reason"] = "unexpected"
    elif fault == "manifest_hash":
        args["execution_manifest_sha256"] = "0" * 64
    elif fault == "request_hash":
        args["request_sha256"] = "bad"
    else:
        args["request_mode"] = None
    with pytest.raises(IntegrityError), db.begin_nested():
        new_run(db, source, user, **args)


def test_controlled_comparison(domain):
    db, user, learner, source, parent = domain
    parent = new_run(db, source, user)
    finish(db, parent, "needs_review", "Direct words.")
    check(db)
    args = ocr_values(db, parent)
    args.update(request_mode="review_comparison", request_reason="Inspect ambiguous text")
    new_run(db, source, user, **args)
    check(db)
    args["request_id"] = uuid4()
    args["request_reason"] = " "
    with pytest.raises(IntegrityError), db.begin_nested():
        new_run(db, source, user, **args)


def test_completion_requires_review(domain):
    db, user, learner, source, parent = domain
    run = new_run(db, source, user, **ocr_values(db, parent))
    with pytest.raises(IntegrityError), db.begin_nested():
        finish(db, run, "review_required", "Raw words.")
        check(db)


@pytest.mark.parametrize("which", ["direct", "running", "duplicate"])
def test_review_parent_and_uniqueness(pending, which):
    db, user, learner, source, parent, run, review = pending
    target = parent if which == "direct" else run
    if which == "running":
        target = new_run(db, source, user, **ocr_values(db, parent))
    with pytest.raises(IntegrityError), db.begin_nested():
        new_review(db, target)


@pytest.mark.parametrize(
    "assign",
    [
        "status='accepted'",
        "status='rejected'",
        "reviewed_text='unsubmitted'",
        "reviewed_text_sha256=repeat('0',64)",
        "submitted_by=NULL,status='submitted'",
        "decision_request_id=gen_random_uuid()",
        "expected_material_version=0",
    ],
)
def test_invalid_review_state_sql(pending, assign):
    db, *_, review = pending
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                f"UPDATE reading_material_extraction_reviews SET {assign},"
                "row_version=row_version+1 WHERE id=:id"
            ),
            {"id": review.id},
        )
        check(db)


def test_accept_reviewed_not_raw_and_terminal_immutability(pending):
    db, user, learner, source, parent, run, review = pending
    submit(db, review, user)
    revision = accept(db, user, learner, source, run, review)
    assert revision.original_text == "Reviewed words." and run.assembled_text == "Raw words."
    for sql in [
        "UPDATE reading_material_extraction_reviews SET row_version=row_version+1 WHERE id=:id",
        "DELETE FROM reading_material_extraction_reviews WHERE id=:id",
        "UPDATE reading_material_extraction_review_pages SET page_acknowledged=false "
        "WHERE review_id=:id",
        "DELETE FROM reading_material_extraction_review_pages WHERE review_id=:id",
    ]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text(sql), {"id": review.id})
    with pytest.raises(IntegrityError), db.begin_nested():
        accept(db, user, learner, source, run, review)


@pytest.mark.parametrize("fault", ["raw_text", "material", "learner", "kind", "reviewer"])
def test_revision_linkage_sql(pending, fault):
    db, user, learner, source, parent, run, review = pending
    submit(db, review, user)
    other_user = uuid4()
    if fault == "reviewer":
        db.execute(
            text(
                "INSERT INTO users(id,login_handle,password_hash,status) "
                "VALUES (:id,:login,'synthetic','active')"
            ),
            {"id": other_user, "login": other_user.hex},
        )
    if fault == "learner":
        learner = uuid4()
        db.execute(
            text(
                "INSERT INTO learner_profiles(id,display_name,created_by_user_id) "
                "VALUES (:id,'Synthetic',:u)"
            ),
            {"id": learner, "u": user},
        )
    with pytest.raises(IntegrityError), db.begin_nested():
        accept(
            db,
            user,
            learner,
            source,
            run,
            review,
            value=run.assembled_text if fault == "raw_text" else None,
            wrong_material=fault == "material",
            kind="pdf_text" if fault == "kind" else "ocr_reviewed",
            actor=other_user if fault == "reviewer" else None,
        )


@pytest.mark.parametrize("fault", ["missing", "ordinal", "span", "ack", "hash"])
def test_review_page_coverage(pending, fault):
    db, user, learner, source, parent, run, review = pending
    submit(db, review, user)
    queries = {
        "missing": "DELETE FROM reading_material_extraction_review_pages WHERE review_id=:id",
        "ordinal": (
            "UPDATE reading_material_extraction_review_pages SET page_number=2 WHERE review_id=:id"
        ),
        "span": (
            "UPDATE reading_material_extraction_review_pages "
            "SET reviewed_text_start=1 WHERE review_id=:id"
        ),
        "ack": "UPDATE reading_material_extraction_review_pages SET page_acknowledged=false "
        "WHERE review_id=:id",
        "hash": (
            "UPDATE reading_material_extraction_reviews "
            "SET reviewed_text_sha256=repeat('0',64),row_version=row_version+1 WHERE id=:id"
        ),
    }
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(queries[fault]), {"id": review.id})
        check(db)


def test_rejection_no_revision_and_no_reopen(pending):
    db, user, learner, source, parent, run, review = pending
    review.status = "rejected"
    review.decided_by = user
    review.decided_at = review.updated_at = materials.now(db)
    review.decision_request_id = uuid4()
    review.decision_request_sha256 = sha("reject")
    review.rejection_reason = "unusable"
    check(db)
    assert review.accepted_revision_id is None
    with pytest.raises(IntegrityError), db.begin_nested():
        accept(db, user, learner, source, run, review, value="Reviewed words.")
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "UPDATE reading_material_extraction_reviews SET status='pending',"
                "row_version=row_version+1 WHERE id=:id"
            ),
            {"id": review.id},
        )


@pytest.mark.parametrize(
    "column,value",
    [
        ("rendered_width", "0"),
        ("rendered_height", "6001"),
        ("rendered_dpi", "NULL"),
        ("native_storage_key", "'../escape'"),
        ("native_sha256", "'bad'"),
        ("native_byte_count", "4194305"),
        ("ocr_unit_count", "-1"),
        ("confidence_scale", "''"),
        ("ocr_warning_codes", "ARRAY['invented']::varchar[]"),
    ],
)
def test_bad_ocr_page_metadata(domain, column, value):
    db, user, learner, source, parent = domain
    run = new_run(db, source, user, **ocr_values(db, parent))
    metadata = page_metadata()
    metadata[column] = db.scalar(text(f"SELECT {value}"))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            ExtractionPage(
                extraction_run_id=run.id,
                page_number=1,
                text_start=0,
                text_end=0,
                raw_character_count=0,
                lexical_word_count=0,
                text_status="empty",
                warning_codes=[],
                **metadata,
            )
        )
        db.flush()


def test_pending_cannot_own_revision(pending):
    db, user, learner, source, parent, run, review = pending
    with pytest.raises(IntegrityError), db.begin_nested():
        # Even fully self-consistent raw text cannot bypass an explicit submitted review.
        review.reviewed_text = run.assembled_text
        review.reviewed_text_sha256 = run.assembled_text_sha256
        accept(db, user, learner, source, run, review, value=run.assembled_text)


@pytest.mark.parametrize(
    "code",
    [
        "malformed_pdf",
        "encrypted_pdf",
        "unsupported_pdf_features",
        "page_limit_exceeded",
        "text_limit_exceeded",
        "unsupported_extracted_text",
        "resource_limit_exceeded",
        "extraction_interrupted",
        "backend_failed",
        "integrity_failed",
        "no_usable_text",
    ],
)
def test_every_failed_direct_outcome_is_ineligible(domain, code):
    db, user, learner, source, _ = domain
    parent = new_run(db, source, user)
    parent.status = "failed"
    parent.outcome_code = code
    parent.finished_at = materials.now(db)
    check(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        new_run(db, source, user, **ocr_values(db, parent))


def test_multiple_pages_require_complete_order(domain):
    db, user, learner, source, _ = domain
    parent = new_run(db, source, user)
    finish(db, parent, pages=2)
    check(db)
    run = new_run(db, source, user, **ocr_values(db, parent))
    finish(db, run, "review_required", "Raw words.", pages=2)
    review = new_review(db, run)
    check(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        submit(db, review, user, pages=1)
    db.refresh(review)
    submit(db, review, user, pages=2)
    revision = accept(db, user, learner, source, run, review)
    assert revision.original_text == "Reviewed words.\n\nReviewed words."


def test_request_identity_is_unique(domain):
    db, user, learner, source, parent = domain
    args = ocr_values(db, parent)
    new_run(db, source, user, **args)
    with pytest.raises(IntegrityError), db.begin_nested():
        new_run(db, source, user, **args)


def test_submitted_cannot_skip_acceptance(pending):
    db, user, learner, source, _, run, review = pending
    submit(db, review, user)
    material = ReadingMaterial(id=uuid4(), learner_id=learner, created_by_user_id=user)
    db.add(material)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        source.material_id = material.id
        db.add(
            ReadingMaterialRevision(
                id=uuid4(),
                material_id=material.id,
                revision_number=1,
                title=source.title,
                language_tag="en",
                source_kind="ocr_reviewed",
                original_text=review.reviewed_text,
                source_sha256=review.reviewed_text_sha256,
                created_by_user_id=user,
                created_at=materials.now(db),
                extraction_run_id=run.id,
            )
        )
        check(db)


def test_terminal_ocr_run_and_pages_are_immutable(pending):
    db, _, _, _, _, run, _ = pending
    for statement in (
        "UPDATE reading_material_extraction_runs SET execution_manifest='{}' WHERE id=:id",
        "UPDATE reading_material_extraction_runs SET extraction_method='embedded_pdf' WHERE id=:id",
        "DELETE FROM reading_material_extraction_runs WHERE id=:id",
        "UPDATE reading_material_extraction_pages SET native_byte_count=2 "
        "WHERE extraction_run_id=:id",
    ):
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text(statement), {"id": run.id})
