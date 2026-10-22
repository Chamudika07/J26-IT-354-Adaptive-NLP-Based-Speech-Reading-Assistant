"""Review operations use synthetic evidence, never an OCR engine."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.exceptions import SecurityError
from app.modules.auth import service as auth
from app.modules.reading_materials.models import ReadingMaterial, ReadingMaterialRevision
from app.modules.reading_materials.ocr import service
from app.modules.reading_materials.ocr.schemas import (
    Acceptance,
    Rejection,
    ReviewedPage,
    Submission,
)
from app.modules.reading_materials.pdf.models import ExtractionPage, Source
from app.modules.reading_materials.schemas import MaterialCreate
from tests.reading_materials.conftest import setup_material as _setup_material

from .conftest import check, finish, new_review, new_run, new_source, ocr_values, sha

setup_material = _setup_material
pytestmark = pytest.mark.integration


@pytest.fixture
def review_context(db_session, setup_material, settings):
    def make(kind="educator_instructor", pages=1, expired=False):
        ctx = setup_material(kind=kind, expired=expired)
        token = ctx["headers"]["Authorization"].split()[1]
        principal = auth.resolve_principal(db_session, settings, token)
        learner = ctx["learner"].id
        source = new_source(db_session, principal.user_id, learner)
        parent = new_run(db_session, source, principal.user_id)
        finish(db_session, parent, pages=pages)
        check(db_session)
        run = new_run(db_session, source, principal.user_id, **ocr_values(db_session, parent))
        finish(db_session, run, "review_required", "Raw words.", pages=pages)
        review = new_review(db_session, run)
        check(db_session)
        db_session.commit()
        return ctx, principal, learner, source.id, run.id, review.id

    return make


def submission(version=1, pages=None, expected=None):
    return Submission(
        row_version=version,
        expected_material_version=expected,
        pages=pages or [ReviewedPage(page_number=1, text="Reviewed words.", acknowledged=True)],
    )


def args(c):
    return c[1:]


def count(db):
    return db.scalar(select(func.count()).select_from(ReadingMaterialRevision))


def test_create_obtain_submit_accept_replay(review_context, db_session):
    c = review_context()
    a = args(c)
    before = count(db_session)
    one = service.obtain(db_session, *a[:-1])
    assert service.obtain(db_session, *a[:-1]) == one
    submitted = service.submit(db_session, *a, submission())
    assert count(db_session) == before
    request = Acceptance(row_version=submitted.row_version, decision_request_id=uuid4())
    accepted = service.accept(db_session, *a, request)
    assert accepted.status == "accepted"
    assert service.accept(db_session, *a, request) == accepted
    assert count(db_session) == before + 1
    revision = db_session.get(ReadingMaterialRevision, accepted.accepted_revision_id)
    assert revision.source_kind == "ocr_reviewed"
    assert revision.original_text == submitted.reviewed_text == "Reviewed words."
    assert revision.source_sha256 == submitted.reviewed_text_sha256
    assert db_session.get(Source, c[3]).material_id == revision.material_id
    with pytest.raises(SecurityError):
        service.accept(db_session, *a, request.model_copy(update={"row_version": 99}))


@pytest.mark.parametrize("fault", ["missing", "duplicate", "reordered", "unack", "blank_unack"])
def test_page_input_rejected(review_context, db_session, fault):
    c = review_context(pages=2)
    pages = [
        ReviewedPage(page_number=i, text="Words." if i == 1 else "", acknowledged=True)
        for i in (1, 2)
    ]
    if fault == "missing":
        pages.pop()
    elif fault == "duplicate":
        pages[1].page_number = 1
    elif fault == "reordered":
        pages.reverse()
    else:
        pages[1 if fault == "blank_unack" else 0].acknowledged = False
    with pytest.raises(SecurityError):
        service.submit(db_session, *args(c), submission(pages=pages))


def test_blank_acknowledged_and_resubmit(review_context, db_session):
    c = review_context(pages=2)
    pages = [
        ReviewedPage(page_number=i, text="Words." if i == 1 else "", acknowledged=True)
        for i in (1, 2)
    ]
    r = service.submit(db_session, *args(c), submission(pages=pages))
    assert r.reviewed_text == "Words.\n\n"
    with pytest.raises(SecurityError):
        service.submit(db_session, *args(c), submission(pages=pages))
    pages[0].text = "Edited words."
    edited = service.submit(db_session, *args(c), submission(r.row_version, pages))
    assert edited.row_version == r.row_version + 1


@pytest.mark.parametrize("submitted", [False, True])
def test_reject_replay_and_terminal(review_context, db_session, submitted):
    c = review_context()
    version = 1
    if submitted:
        version = service.submit(db_session, *args(c), submission()).row_version
    before = count(db_session)
    request = Rejection(row_version=version, decision_request_id=uuid4(), reason="unusable_text")
    r = service.reject(db_session, *args(c), request)
    assert r.status == "rejected" and r.accepted_revision_id is None
    assert service.reject(db_session, *args(c), request) == r
    assert count(db_session) == before
    for operation in (
        lambda: service.reject(
            db_session, *args(c), request.model_copy(update={"reason": "wrong_source"})
        ),
        lambda: service.submit(db_session, *args(c), submission(r.row_version)),
        lambda: service.accept(
            db_session, *args(c), Acceptance(row_version=r.row_version, decision_request_id=uuid4())
        ),
    ):
        with pytest.raises(SecurityError):
            operation()


@pytest.mark.parametrize("kind", ["self", "guardian_viewer", "educator_viewer"])
@pytest.mark.parametrize("operation", ["obtain", "submit", "accept", "reject"])
def test_broad_read_access_denied(review_context, db_session, kind, operation):
    c = review_context(kind)
    with pytest.raises(SecurityError):
        if operation == "obtain":
            service.obtain(db_session, *args(c)[:-1])
        elif operation == "submit":
            service.submit(db_session, *args(c), submission())
        elif operation == "accept":
            service.accept(
                db_session, *args(c), Acceptance(row_version=1, decision_request_id=uuid4())
            )
        else:
            service.reject(
                db_session,
                *args(c),
                Rejection(row_version=1, decision_request_id=uuid4(), reason="wrong_source"),
            )


@pytest.mark.parametrize(
    "fault",
    [
        "expired",
        "revoked",
        "wrong_learner",
        "wrong_source",
        "wrong_run",
        "wrong_review",
        "direct",
        "running",
    ],
)
def test_identity_and_current_authority(review_context, db_session, fault):
    c = review_context(expired=fault == "expired")
    a = list(args(c))
    if fault == "revoked":
        c[0]["relation"].revoked_at = service.materials.now(db_session)
        c[0]["relation"].revoked_by_user_id = c[1].user_id
        db_session.commit()
    elif fault in {"wrong_learner", "wrong_source", "wrong_run", "wrong_review"}:
        a[{"wrong_learner": 1, "wrong_source": 2, "wrong_run": 3, "wrong_review": 4}[fault]] = (
            uuid4()
        )
    elif fault in {"direct", "running"}:
        source = db_session.get(Source, c[3])
        run = new_run(db_session, source, c[1].user_id)
        if fault == "direct":
            finish(db_session, run)
        check(db_session)
        db_session.commit()
        a[3] = run.id
    with pytest.raises(SecurityError):
        service.submit(db_session, *a, submission())


@pytest.mark.parametrize("fault", ["pending", "stale", "archived", "failure"])
def test_accept_failure_atomic(review_context, db_session, monkeypatch, fault):
    c = review_context()
    version = 1
    if fault != "pending":
        version = service.submit(db_session, *args(c), submission()).row_version
    before = count(db_session)
    materials_before = db_session.scalar(select(func.count()).select_from(ReadingMaterial))
    if fault == "archived":
        source = db_session.get(Source, c[3])
        source.archived_at = source.updated_at = service.materials.now(db_session)
        db_session.commit()
    if fault == "failure":
        original = service.add_revision

        def fail(*a, **kw):
            original(*a, **kw)
            raise RuntimeError("synthetic failure after insertion")

        monkeypatch.setattr(service, "add_revision", fail)
    with pytest.raises(RuntimeError if fault == "failure" else SecurityError):
        service.accept(
            db_session,
            *args(c),
            Acceptance(row_version=1 if fault == "stale" else version, decision_request_id=uuid4()),
        )
    assert count(db_session) == before
    assert db_session.scalar(select(func.count()).select_from(ReadingMaterial)) == materials_before
    assert db_session.get(Source, c[3]).material_id is None


def bind_existing_material(c, db_session):
    source = db_session.get(Source, c[3])
    material = db_session.get(ReadingMaterial, c[0]["material"].id)

    published = new_run(db_session, source, c[1].user_id)

    value = "Existing PDF text."
    now = service.materials.now(db_session)

    db_session.add(
        ExtractionPage(
            extraction_run_id=published.id,
            page_number=1,
            text_start=0,
            text_end=len(value),
            raw_character_count=len(value),
            lexical_word_count=len(value.split()),
            text_status="lexical",
            warning_codes=[],
        )
    )
    db_session.flush()

    published.status = "extracted"
    published.outcome_code = None
    published.finished_at = now
    published.assembled_text = value
    published.assembled_text_sha256 = sha(value)
    published.total_page_count = 1
    published.pages_with_lexical_text = 1
    published.pages_with_zero_characters = 0
    published.pages_with_zero_lexical_words = 0
    published.extracted_character_count = len(value)
    published.assembled_character_count = len(value)
    published.lexical_word_count = len(value.split())

    service.add_revision(
        db_session,
        material.id,
        2,
        c[1].user_id,
        MaterialCreate(
            title=source.title,
            language_tag="en",
            text=value,
        ),
        now,
        source_kind="pdf_text",
        extraction_run_id=published.id,
    )

    source.material_id = material.id

    check(db_session)
    db_session.commit()
    db_session.refresh(material)

    return material


def test_accept_appends_to_existing_bound_material(review_context, db_session):
    c = review_context()
    material = bind_existing_material(c, db_session)
    expected = material.row_version

    submitted = service.submit(
        db_session,
        *args(c),
        submission(expected=expected),
    )

    accepted = service.accept(
        db_session,
        *args(c),
        Acceptance(
            row_version=submitted.row_version,
            decision_request_id=uuid4(),
            expected_material_version=expected,
        ),
    )

    revision = db_session.get(
        ReadingMaterialRevision,
        accepted.accepted_revision_id,
    )

    assert revision.material_id == material.id
    assert revision.revision_number == 3
    assert db_session.get(Source, c[3]).material_id == material.id


def test_material_version_change_blocks_acceptance(review_context, db_session):
    c = review_context()
    material = bind_existing_material(c, db_session)
    expected = material.row_version

    submitted = service.submit(
        db_session,
        *args(c),
        submission(expected=expected),
    )

    # Simulate another legitimate material update after review submission.
    material.updated_at = service.materials.now(db_session)
    db_session.commit()

    with pytest.raises(SecurityError) as exc:
        service.accept(
            db_session,
            *args(c),
            Acceptance(
                row_version=submitted.row_version,
                decision_request_id=uuid4(),
                expected_material_version=expected,
            ),
        )

    assert exc.value.code == "material_version_conflict"

    assert (
        db_session.scalar(
            select(func.count())
            .select_from(ReadingMaterialRevision)
            .where(ReadingMaterialRevision.extraction_run_id == c[4])
        )
        == 0
    )
