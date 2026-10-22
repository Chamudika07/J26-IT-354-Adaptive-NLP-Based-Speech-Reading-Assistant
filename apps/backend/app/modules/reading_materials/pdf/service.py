"""Claim outside-parser transactions and atomically publish authorized PDF evidence."""

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.learners.service import LearnerAction as Action
from app.modules.learners.service import authorize_learner_action
from app.modules.reading_materials import repository as materials
from app.modules.reading_materials.models import ReadingMaterial as Material
from app.modules.reading_materials.models import ReadingMaterialRevision as Revision
from app.modules.reading_materials.normalization import validate_text
from app.modules.reading_materials.pdf import contracts, runner
from app.modules.reading_materials.pdf import repository as repo
from app.modules.reading_materials.pdf.models import COUNTS, ExtractionPage, ExtractionRun, Source
from app.modules.reading_materials.pdf.schemas import (
    RunDetail,
    RunSummary,
    SourceSummary,
    UploadMetadata,
    UploadResult,
)
from app.modules.reading_materials.pdf.storage import LocalStorage, StoredObject
from app.modules.reading_materials.profiles import ratio
from app.modules.reading_materials.schemas import MaterialCreate, Page
from app.modules.reading_materials.segmentation import words
from app.modules.reading_materials.service import add_revision, cursor_pair, protect, recheck


def error(status: int, code: str) -> SecurityError:
    return SecurityError(
        status,
        code,
        {
            404: "Resource not found",
            409: "Resource changed. Reload and try again.",
            422: "Invalid request",
            503: "Service unavailable",
        }[status],
    )


def scoped(
    db: Session,
    learner: UUID,
    identity: UUID,
    *,
    lock: bool = False,
    principal: Principal | None = None,
) -> Source:
    row = repo.source(db, learner, identity)
    if row is None:
        raise error(404, "not_found")
    # Protected learner lock serializes writes/bindings; always material before source.
    material_missing = False
    if row.material_id:
        material = materials.material(db, learner, row.material_id, lock=lock)
        material_missing = material is None or material.archived_at is not None
    if lock:
        row = repo.source(db, learner, identity, lock=True)
        assert row is not None
        assert principal is not None
        recheck(db, principal, learner, Action.EXTRACT_PDF)
    if material_missing:
        raise error(404, "not_found")
    if row.archived_at is not None:
        raise error(409 if lock else 404, "source_state_conflict" if lock else "not_found")
    return row


def summary(row: ExtractionRun) -> RunSummary:
    return RunSummary(**{n: getattr(row, n) for n in RunSummary.model_fields})


def source_summary(db: Session, row: Source) -> SourceSummary:
    latest = repo.latest(db, row.id)
    return SourceSummary(
        **{n: getattr(row, n) for n in SourceSummary.model_fields if n != "latest_extraction"},
        latest_extraction=summary(latest) if latest else None,
    )


def detail(db: Session, source: Source, row: ExtractionRun, evidence: bool = False) -> RunDetail:
    revision = db.scalar(select(Revision.id).where(Revision.extraction_run_id == row.id))
    return RunDetail(
        **summary(row).model_dump(),
        material_id=source.material_id,
        revision_id=revision,
        **{n: getattr(row, n) for n in COUNTS},
        lexical_page_coverage=ratio(row.pages_with_lexical_text, row.total_page_count)
        if row.total_page_count is not None and row.pages_with_lexical_text is not None
        else None,
        assembled_text=row.assembled_text if evidence else None,
        pages=[
            contracts.PageEvidence(
                **{n: getattr(p, n) for n in contracts.PageEvidence.model_fields}
            )
            for p in repo.pages(db, row.id)
        ]
        if evidence and row.assembled_text is not None
        else None,
    )


@dataclass(frozen=True)
class Claim:
    source_id: UUID
    run_id: UUID
    version: int
    fingerprint: str
    key: str
    digest: str
    size: int
    material_version: int | None


def claim_locked(
    db: Session, principal: Principal, source: Source, expected: int | None
) -> Claim | RunDetail:
    fingerprint = contracts.fingerprint()
    rows = repo.attempts(db, source.id, fingerprint)
    recheck(db, principal, source.learner_id, Action.EXTRACT_PDF)
    for old in rows:
        if old.status in ("extracted", "ocr_required", "needs_review"):
            return detail(db, source, old)
    material_version = None
    if source.material_id:
        material = materials.material(db, source.learner_id, source.material_id, lock=True)
        assert material is not None
        if expected != material.row_version:
            raise error(409, "version_conflict")
        material_version = material.row_version
    now = materials.now(db)
    for old in rows:
        if old.status == "running":
            if old.lease_expires_at > now:
                raise error(409, "extraction_conflict")
            old.status, old.outcome_code, old.finished_at = "failed", "extraction_interrupted", now
    db.flush()
    row = ExtractionRun(
        source_id=source.id,
        requested_by_user_id=principal.user_id,
        attempt_number=max((r.attempt_number for r in rows), default=0) + 1,
        status="running",
        started_at=now,
        lease_expires_at=now + timedelta(seconds=contracts.LEASE_SECONDS),
        **contracts.provenance(),
        extraction_fingerprint=fingerprint,
    )
    db.add(row)
    db.flush()
    return Claim(
        source.id,
        row.id,
        row.row_version,
        fingerprint,
        source.storage_key,
        source.file_sha256,
        source.byte_count,
        material_version,
    )


def claim(
    db: Session, principal: Principal, learner: UUID, source_id: UUID, expected: int | None
) -> Claim | RunDetail:
    try:
        principal = protect(db, principal, learner, Action.EXTRACT_PDF)
        source = scoped(db, learner, source_id, lock=True, principal=principal)
        result = claim_locked(db, principal, source, expected)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def validate_result(result: contracts.ExtractionResult) -> dict[str, int]:
    if result.status == "failed":
        if (
            result.pages
            or result.assembled_text is not None
            or result.outcome_code not in contracts.OUTCOMES[:11]
        ):
            raise ValueError("Invalid failed result")
        return {}
    value = result.assembled_text
    if value is None or not result.pages:
        raise ValueError("Missing evidence")
    validate_text(value if value.strip() else value + "a")
    end = 0
    for ordinal, p in enumerate(result.pages, 1):
        if (
            p.page_number != ordinal
            or p.text_start != end
            or p.text_end < p.text_start
            or p.text_end > len(value)
            or p.raw_character_count != p.text_end - p.text_start
            or p.lexical_word_count != len(words(value[p.text_start : p.text_end]))
        ):
            raise ValueError("Invalid page evidence")
        if ordinal < len(result.pages) and value[p.text_end : p.text_end + 2] != "\n\n":
            raise ValueError("Invalid separator")
        end = p.text_end + 2
    if end - 2 != len(value):
        raise ValueError("Invalid final offset")
    pages = result.pages
    if result.status == "extracted" and (
        any(p.warning_codes for p in pages)
        or not any(p.lexical_word_count for p in pages)
        or result.outcome_code is not None
    ):
        raise ValueError("Invalid accepted output")
    if result.status == "ocr_required" and (
        result.outcome_code != "image_without_text"
        or not any("painted_image" in p.warning_codes and p.lexical_word_count == 0 for p in pages)
    ):
        raise ValueError("Invalid OCR outcome")
    if result.status == "needs_review" and (
        result.outcome_code != "ambiguous_content" or not any(p.warning_codes for p in pages)
    ):
        raise ValueError("Invalid review outcome")
    return dict(
        total_page_count=len(pages),
        pages_with_lexical_text=sum(p.lexical_word_count > 0 for p in pages),
        pages_with_zero_characters=sum(p.raw_character_count == 0 for p in pages),
        pages_with_zero_lexical_words=sum(p.lexical_word_count == 0 for p in pages),
        extracted_character_count=sum(p.raw_character_count for p in pages),
        assembled_character_count=len(value),
        lexical_word_count=sum(p.lexical_word_count for p in pages),
    )


def publish(
    db: Session,
    principal: Principal,
    learner: UUID,
    work: Claim,
    result: contracts.ExtractionResult,
) -> RunDetail:
    counts = validate_result(result)
    try:
        principal = protect(db, principal, learner, Action.EXTRACT_PDF)
        source = scoped(db, learner, work.source_id, lock=True, principal=principal)
        row = repo.run(db, source.id, work.run_id, lock=True)
        recheck(db, principal, learner, Action.EXTRACT_PDF)
        if row is None or row.requested_by_user_id != principal.user_id:
            raise error(404, "not_found")
        if (
            row.status != "running"
            or row.row_version != work.version
            or row.extraction_fingerprint != work.fingerprint
            or row.lease_expires_at <= materials.now(db)
        ):
            raise error(409, "extraction_conflict")
        material = None
        if source.material_id:
            material = materials.material(db, learner, source.material_id, lock=True)
            if material is None or material.row_version != work.material_version:
                raise error(409, "version_conflict")
        for page in result.pages:
            db.add(ExtractionPage(extraction_run_id=row.id, **page.model_dump()))
        db.flush()
        row.status, row.outcome_code = result.status, result.outcome_code
        row.assembled_text = result.assembled_text
        row.assembled_text_sha256 = (
            hashlib.sha256(result.assembled_text.encode()).hexdigest()
            if result.assembled_text is not None
            else None
        )
        for name, value in counts.items():
            setattr(row, name, value)
        row.finished_at = materials.now(db)
        if result.status == "extracted":
            if material is None:
                material = Material(
                    learner_id=learner,
                    created_by_user_id=principal.user_id,
                    created_at=row.finished_at,
                    updated_at=row.finished_at,
                )
                db.add(material)
                db.flush()
                source.material_id = material.id
                number = 1
            else:
                number = materials.latest(db, material.id).revision_number + 1
                material.updated_at = row.finished_at
                flag_modified(material, "updated_at")
            assert row.assembled_text is not None
            add_revision(
                db,
                material.id,
                number,
                principal.user_id,
                MaterialCreate(title=source.title, language_tag="en", text=row.assembled_text),
                row.finished_at,
                source_kind="pdf_text",
                extraction_run_id=row.id,
            )
        recheck(db, principal, learner, Action.EXTRACT_PDF)
        if row.lease_expires_at <= materials.now(db):
            raise error(409, "extraction_conflict")
        db.flush()
        response = detail(db, source, row)
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def finish(
    db: Session, principal: Principal, learner: UUID, storage: LocalStorage, work: Claim | RunDetail
) -> tuple[RunDetail, int]:
    if isinstance(work, RunDetail):
        return work, 200
    try:
        with storage.open(work.key) as stream:
            result = runner.run(stream, work.digest, work.size)
        validate_result(result)
    except Exception:
        result = contracts.failed("backend_failed")
    public = publish(db, principal, learner, work, result)
    if result.outcome_code in ("backend_failed", "integrity_failed", "resource_limit_exceeded"):
        raise error(503, "service_unavailable")
    return public, 201


def register(
    db: Session, principal: Principal, learner: UUID, metadata: UploadMetadata, obj: StoredObject
) -> Claim | RunDetail:
    try:
        principal = protect(db, principal, learner, Action.UPLOAD_PDF)
        source = repo.upload(db, learner, principal.user_id, metadata.upload_request_id)
        if source:
            if (
                source.title != metadata.title
                or source.language_tag != metadata.language_tag
                or source.file_sha256 != obj.digest
                or source.byte_count != obj.size
            ):
                raise error(409, "extraction_conflict")
            source = scoped(db, learner, source.id, lock=True, principal=principal)
            latest = repo.latest(db, source.id)
            # Upload idempotency returns its recorded terminal outcome, including failure.
            if latest and latest.status != "running":
                result: Claim | RunDetail = detail(db, source, latest)
                db.commit()
                return result
        else:
            source = Source(
                learner_id=learner,
                created_by_user_id=principal.user_id,
                **metadata.model_dump(),
                source_kind="pdf",
                media_type="application/pdf",
                byte_count=obj.size,
                file_sha256=obj.digest,
                storage_backend=storage_backend(),
                storage_key=obj.key,
            )
            db.add(source)
            db.flush()
        result = claim_locked(db, principal, source, None)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def storage_backend() -> str:
    return LocalStorage.backend


def upload(
    db: Session,
    principal: Principal,
    learner: UUID,
    metadata: UploadMetadata,
    data: bytes,
    storage: LocalStorage,
) -> tuple[UploadResult, int]:
    try:
        with storage.store(data) as obj:
            work = register(db, principal, learner, metadata, obj)
    except (OSError, ValueError) as exc:
        raise error(503, "service_unavailable") from exc
    result, status = finish(db, principal, learner, storage, work)
    authorize_learner_action(db, principal, learner, Action.READ_READING_MATERIAL)
    source = scoped(db, learner, result.source_id)
    return UploadResult(source=source_summary(db, source), extraction=result), status


def read_source(db: Session, principal: Principal, learner: UUID, identity: UUID) -> SourceSummary:
    authorize_learner_action(db, principal, learner, Action.READ_READING_MATERIAL)
    return source_summary(db, scoped(db, learner, identity))


def read_run(
    db: Session,
    principal: Principal,
    learner: UUID,
    source_id: UUID,
    identity: UUID,
    evidence: bool,
) -> RunDetail:
    authorize_learner_action(db, principal, learner, Action.READ_READING_MATERIAL)
    source = scoped(db, learner, source_id)
    row = repo.run(db, source.id, identity)
    if row is None:
        raise error(404, "not_found")
    return detail(db, source, row, evidence)


def list_sources(
    db: Session, principal: Principal, learner: UUID, cursor: str | None, limit: int
) -> Page[SourceSummary]:
    authorize_learner_action(db, principal, learner, Action.READ_READING_MATERIAL)
    rows = repo.sources(db, learner, cursor_pair(cursor), limit)
    return Page(
        items=[source_summary(db, r) for r in rows[:limit]],
        next_cursor=f"{rows[limit - 1].created_at.isoformat()}|{rows[limit - 1].id}"
        if len(rows) > limit
        else None,
    )


def list_runs(
    db: Session,
    principal: Principal,
    learner: UUID,
    source_id: UUID,
    cursor: str | None,
    limit: int,
) -> Page[RunSummary]:
    authorize_learner_action(db, principal, learner, Action.READ_READING_MATERIAL)
    scoped(db, learner, source_id)
    rows = repo.history(db, source_id, cursor_pair(cursor), limit)
    return Page(
        items=[summary(r) for r in rows[:limit]],
        next_cursor=f"{rows[limit - 1].started_at.isoformat()}|{rows[limit - 1].id}"
        if len(rows) > limit
        else None,
    )


def archive(
    db: Session, principal: Principal, learner: UUID, identity: UUID, version: int
) -> SourceSummary:
    try:
        principal = protect(db, principal, learner, Action.ARCHIVE_PDF)
        source = scoped(db, learner, identity, lock=True, principal=principal)
        recheck(db, principal, learner, Action.ARCHIVE_PDF)
        if version != source.row_version:
            raise error(409, "version_conflict")
        source.archived_at = source.updated_at = materials.now(db)
        db.flush()
        result = source_summary(db, source)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
