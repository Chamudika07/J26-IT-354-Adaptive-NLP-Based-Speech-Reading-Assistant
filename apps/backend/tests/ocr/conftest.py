import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.modules.reading_materials import repository as materials
from app.modules.reading_materials.ocr.models import ExtractionReview, ExtractionReviewPage
from app.modules.reading_materials.pdf import contracts
from app.modules.reading_materials.pdf.models import ExtractionPage, ExtractionRun, Source
from tests.reading_materials.test_concurrency import context  # noqa: F401


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def check(db):
    db.flush()
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    db.execute(text("SET CONSTRAINTS ALL DEFERRED"))


def new_source(db, user, learner):
    source = Source(
        id=uuid4(),
        learner_id=learner,
        created_by_user_id=user,
        title="Synthetic",
        language_tag="en",
        source_kind="pdf",
        media_type="application/pdf",
        byte_count=1,
        file_sha256=sha("source"),
        storage_backend="local-v1",
        storage_key=uuid4().hex,
        upload_request_id=uuid4(),
    )
    db.add(source)
    db.flush()
    return source


def new_run(db, source, actor, **extra):
    now = materials.now(db)
    row = ExtractionRun(
        id=uuid4(),
        source_id=source.id,
        requested_by_user_id=actor,
        attempt_number=1,
        status="running",
        started_at=now,
        lease_expires_at=now + timedelta(seconds=90),
        extraction_fingerprint=sha(uuid4().hex),
        **contracts.provenance(),
        **extra,
    )
    db.add(row)
    db.flush()
    return row


def page_metadata():
    return dict(
        rendered_width=100,
        rendered_height=100,
        rendered_dpi=200,
        renderer_name="synthetic",
        renderer_version="test-v1",
        rendered_pixel_sha256=sha("pixels"),
        preprocessed_pixel_sha256=sha("processed"),
        native_storage_backend="local-v1",
        native_storage_key=uuid4().hex,
        native_sha256=sha("native"),
        native_byte_count=1,
        native_format="json",
        native_schema_version="synthetic-v1",
        ocr_unit_count=2,
        confidence_scale="synthetic-uncalibrated",
        ocr_warning_codes=["layout_unverified"],
    )


def finish(db, run, status="ocr_required", value="", pages=1):
    metadata = {}
    if run.extraction_method == "ocr":
        metadata = page_metadata()
    for i in range(pages):
        start = i * (len(value) + 2)
        db.add(
            ExtractionPage(
                extraction_run_id=run.id,
                page_number=i + 1,
                text_start=start,
                text_end=start + len(value),
                raw_character_count=len(value),
                lexical_word_count=len(value.split()),
                text_status="lexical" if value else "empty",
                warning_codes=["painted_image"],
                **metadata,
            )
        )
    db.flush()
    assembled = "\n\n".join([value] * pages)
    run.status = status
    run.outcome_code = {
        "ocr_required": "image_without_text",
        "needs_review": "ambiguous_content",
    }.get(status)
    run.finished_at = materials.now(db)
    run.assembled_text, run.assembled_text_sha256 = assembled, sha(assembled)
    run.total_page_count = pages
    run.pages_with_lexical_text = pages if value else 0
    run.pages_with_zero_characters = 0 if value else pages
    run.pages_with_zero_lexical_words = 0 if value else pages
    run.extracted_character_count = len(value) * pages
    run.assembled_character_count = len(assembled)
    run.lexical_word_count = len(value.split()) * pages
    db.flush()


def ocr_values(db, parent):
    manifest = dict(
        engine_name="synthetic",
        engine_version="test-v1",
        model_revision="pinned",
        model_sha256=sha("model"),
        config_version="test-v1",
        preprocessing_recipe="synthetic",
        preprocessing_parameters={},
    )
    digest = db.scalar(
        text("SELECT encode(sha256(convert_to(CAST(:m AS jsonb)::text,'UTF8')),'hex')"),
        {"m": json.dumps(manifest)},
    )
    return dict(
        extraction_method="ocr",
        parent_extraction_run_id=parent.id,
        request_id=uuid4(),
        request_sha256=sha("request"),
        request_mode="eligible",
        execution_manifest=manifest,
        execution_manifest_sha256=digest,
    )


def new_review(db, run):
    row = ExtractionReview(id=uuid4(), extraction_run_id=run.id, status="pending")
    db.add(row)
    db.flush()
    return row


def submit(db, review, actor, value="Reviewed words.", pages=1):
    review.status = "submitted"
    review.reviewed_text = "\n\n".join([value] * pages)
    review.reviewed_text_sha256 = sha(review.reviewed_text)
    review.submitted_by = actor
    review.submitted_at = review.updated_at = materials.now(db)
    db.flush()
    for i in range(pages):
        db.add(
            ExtractionReviewPage(
                review_id=review.id,
                page_number=i + 1,
                reviewed_text_start=i * (len(value) + 2),
                reviewed_text_end=i * (len(value) + 2) + len(value),
                page_acknowledged=True,
            )
        )
    check(db)


@pytest.fixture
def domain(db_session):
    user, learner = uuid4(), uuid4()
    db_session.execute(
        text(
            "INSERT INTO users(id,login_handle,password_hash,status) "
            "VALUES (:u,:login,'synthetic','active')"
        ),
        {"u": user, "login": user.hex},
    )
    db_session.execute(
        text(
            "INSERT INTO learner_profiles(id,display_name,created_by_user_id) "
            "VALUES (:l,'Synthetic',:u)"
        ),
        {"l": learner, "u": user},
    )
    source = new_source(db_session, user, learner)
    parent = new_run(db_session, source, user)
    finish(db_session, parent)
    check(db_session)
    return db_session, user, learner, source, parent


@pytest.fixture
def pending(domain):
    db, user, learner, source, parent = domain
    run = new_run(db, source, user, **ocr_values(db, parent))
    finish(db, run, "review_required", "Raw words.")
    review = new_review(db, run)
    check(db)
    return db, user, learner, source, parent, run, review
