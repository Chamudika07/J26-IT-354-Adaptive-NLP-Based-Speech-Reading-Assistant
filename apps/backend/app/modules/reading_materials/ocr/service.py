"""Instructor-only review transactions; no engine, routes, or automatic processing."""

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import StaleDataError

from app.modules.auth.contracts import Principal
from app.modules.learners.service import LearnerAction as Action
from app.modules.reading_materials import repository as materials
from app.modules.reading_materials.models import ReadingMaterial
from app.modules.reading_materials.normalization import validate_text
from app.modules.reading_materials.ocr import repository as repo
from app.modules.reading_materials.ocr.models import ExtractionReview, ExtractionReviewPage
from app.modules.reading_materials.ocr.schemas import (
    Acceptance,
    Rejection,
    ReviewResult,
    Submission,
)
from app.modules.reading_materials.pdf import repository as pdf
from app.modules.reading_materials.pdf.models import ExtractionRun, Source
from app.modules.reading_materials.schemas import MaterialCreate
from app.modules.reading_materials.service import add_revision, error, protect, recheck

ACTION = Action.REVISE_READING_MATERIAL


@contextmanager
def transaction(db: Session) -> Iterator[None]:
    try:
        yield
        db.commit()
    except (StaleDataError, IntegrityError) as exc:
        db.rollback()
        raise error(409, "review_conflict") from exc
    except Exception:
        db.rollback()
        raise


def locked(
    db: Session, principal: Principal, learner: UUID, source_id: UUID, run_id: UUID
) -> tuple[Principal, Source, ExtractionRun, ReadingMaterial | None]:
    # Auth user/session/roles -> learner/grant -> material -> source -> run -> review.
    principal = protect(db, principal, learner, ACTION)
    source = pdf.source(db, learner, source_id)
    if source is None:
        raise error(404, "not_found")
    material = None
    if source.material_id is not None:
        material = materials.material(db, learner, source.material_id, lock=True)
    source = pdf.source(db, learner, source_id, lock=True)
    assert source is not None
    run = repo.run(db, source.id, run_id)
    recheck(db, principal, learner, ACTION)
    if run is None:
        raise error(404, "not_found")
    if run.extraction_method != "ocr" or run.status != "review_required":
        raise error(409, "review_state_conflict")
    if source.material_id is not None and (material is None or material.id != source.material_id):
        raise error(409, "material_state_conflict")
    return principal, source, run, material


def writable(source: Source, material: ReadingMaterial | None) -> None:
    if source.archived_at is not None or (material and material.archived_at is not None):
        raise error(409, "source_state_conflict")


def ensure_review(db: Session, run: ExtractionRun) -> ExtractionReview:
    """Caller owns authorization, run lock and transaction, including future publication."""
    if run.extraction_method != "ocr" or run.status != "review_required":
        raise error(409, "review_state_conflict")
    row = repo.review(db, run.id)
    if row is None:
        row = ExtractionReview(extraction_run_id=run.id, status="pending")
        db.add(row)
        db.flush()
    return row


def result(row: ExtractionReview) -> ReviewResult:
    return ReviewResult(**{name: getattr(row, name) for name in ReviewResult.model_fields})


def obtain(
    db: Session, principal: Principal, learner: UUID, source_id: UUID, run_id: UUID
) -> ReviewResult:
    with transaction(db):
        principal, source, run, material = locked(db, principal, learner, source_id, run_id)
        row = ensure_review(db, run)
        recheck(db, principal, learner, ACTION)
        writable(source, material)
        response = result(row)
    return response


def target(db: Session, run: ExtractionRun, identity: UUID) -> ExtractionReview:
    row = repo.review(db, run.id)
    if row is None or row.id != identity:
        raise error(404, "not_found")
    return row


def submit(
    db: Session,
    principal: Principal,
    learner: UUID,
    source_id: UUID,
    run_id: UUID,
    review_id: UUID,
    payload: Submission,
) -> ReviewResult:
    with transaction(db):
        principal, source, run, material = locked(db, principal, learner, source_id, run_id)
        row = target(db, run, review_id)
        recheck(db, principal, learner, ACTION)
        writable(source, material)
        if row.status not in {"pending", "submitted"} or row.row_version != payload.row_version:
            raise error(409, "version_conflict")
        if payload.expected_material_version != (material.row_version if material else None):
            raise error(409, "material_version_conflict")
        if [p.page_number for p in payload.pages] != list(
            range(1, (run.total_page_count or 0) + 1)
        ):
            raise error(422, "page_coverage_invalid")
        if not all(p.acknowledged for p in payload.pages):
            raise error(422, "page_acknowledgement_required")
        value = "\n\n".join(p.text for p in payload.pages)
        try:
            validate_text(value)
        except ValueError as exc:
            raise error(422, "validation_error") from exc
        row.status = "submitted"
        row.reviewed_text = value
        row.reviewed_text_sha256 = hashlib.sha256(value.encode()).hexdigest()
        row.submitted_by = principal.user_id
        row.submitted_at = row.updated_at = materials.now(db)
        row.expected_material_version = payload.expected_material_version
        db.flush()
        existing = {p.page_number: p for p in repo.pages(db, row.id)}
        offset = 0
        for page in payload.pages:
            record = existing.get(page.page_number)
            if record is None:
                record = ExtractionReviewPage(review_id=row.id, page_number=page.page_number)
                db.add(record)
            record.reviewed_text_start = offset
            record.reviewed_text_end = offset + len(page.text)
            record.page_acknowledged = True
            record.updated_at = materials.now(db)
            offset = record.reviewed_text_end + 2
        db.flush()
        recheck(db, principal, learner, ACTION)
        response = result(row)
    return response


def digest(
    learner: UUID, source: UUID, run: UUID, review: UUID, payload: Acceptance | Rejection
) -> str:
    canonical = {
        "version": "ocr-decision-v1",
        "action": "accept" if isinstance(payload, Acceptance) else "reject",
        "learner": str(learner),
        "source": str(source),
        "run": str(run),
        "review": str(review),
        "payload": payload.model_dump(mode="json"),
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def decide(
    db: Session,
    principal: Principal,
    learner: UUID,
    source_id: UUID,
    run_id: UUID,
    review_id: UUID,
    payload: Acceptance | Rejection,
) -> ReviewResult:
    with transaction(db):
        principal, source, run, material = locked(db, principal, learner, source_id, run_id)
        row = target(db, run, review_id)
        recheck(db, principal, learner, ACTION)
        fingerprint = digest(learner, source_id, run_id, review_id, payload)
        previous = repo.decision(db, principal.user_id, payload.decision_request_id)
        if previous is not None:
            if previous.id != row.id or previous.decision_request_sha256 != fingerprint:
                raise error(409, "decision_request_conflict")
            response = result(previous)
        else:
            writable(source, material)
            if row.status not in {"pending", "submitted"} or row.row_version != payload.row_version:
                raise error(409, "review_state_conflict")
            now = materials.now(db)
            if isinstance(payload, Acceptance):
                expected = material.row_version if material else None
                if (
                    payload.expected_material_version != expected
                    or row.expected_material_version != expected
                ):
                    raise error(409, "material_version_conflict")
                if row.status != "submitted" or row.reviewed_text is None:
                    raise error(409, "review_state_conflict")
                try:
                    validate_text(row.reviewed_text)
                except ValueError as exc:
                    raise error(422, "validation_error") from exc
                # Force all deferred evidence/coverage guards before creating a revision.
                from sqlalchemy import text

                db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
                db.execute(text("SET CONSTRAINTS ALL DEFERRED"))
                if material is None:
                    material = ReadingMaterial(
                        learner_id=learner,
                        created_by_user_id=principal.user_id,
                        created_at=now,
                        updated_at=now,
                    )
                    materials.save(db, material)
                    source.material_id = material.id
                    number = 1
                else:
                    number = materials.latest(db, material.id).revision_number + 1
                    material.updated_at = now
                    flag_modified(material, "updated_at")
                revision = add_revision(
                    db,
                    material.id,
                    number,
                    principal.user_id,
                    MaterialCreate(title=source.title, language_tag="en", text=row.reviewed_text),
                    now,
                    source_kind="ocr_reviewed",
                    extraction_run_id=run.id,
                )
                row.accepted_revision_id = revision.id
                row.status = "accepted"
            else:
                row.rejection_reason = payload.reason
                row.status = "rejected"
            row.decided_by = principal.user_id
            row.decided_at = row.updated_at = now
            row.decision_request_id = payload.decision_request_id
            row.decision_request_sha256 = fingerprint
            db.flush()
            recheck(db, principal, learner, ACTION)
            response = result(row)
    return response


def accept(
    db: Session,
    principal: Principal,
    learner: UUID,
    source_id: UUID,
    run_id: UUID,
    review_id: UUID,
    payload: Acceptance,
) -> ReviewResult:
    return decide(db, principal, learner, source_id, run_id, review_id, payload)


def reject(
    db: Session,
    principal: Principal,
    learner: UUID,
    source_id: UUID,
    run_id: UUID,
    review_id: UUID,
    payload: Rejection,
) -> ReviewResult:
    return decide(db, principal, learner, source_id, run_id, review_id, payload)
