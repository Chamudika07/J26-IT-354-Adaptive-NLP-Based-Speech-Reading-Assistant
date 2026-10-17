"""Authorize, claim, compute without locks, then reauthorize and publish atomically."""

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.auth.service import assert_protected_session_live, protect_principal_for_write
from app.modules.learners.service import (
    LearnerAction as Action,
)
from app.modules.learners.service import (
    assert_protected_learner_action_live,
    authorize_learner_action,
    authorize_learner_action_for_write,
)
from app.modules.reading_materials import pipeline, profiles
from app.modules.reading_materials import repository as repo
from app.modules.reading_materials.models import (
    ReadingMaterial as Material,
)
from app.modules.reading_materials.models import (
    ReadingMaterialProcessingRun as Run,
)
from app.modules.reading_materials.models import (
    ReadingMaterialRevision as Revision,
)
from app.modules.reading_materials.models import (
    ReadingMaterialSentenceFeature as Sentence,
)
from app.modules.reading_materials.schemas import (
    MaterialCreate,
    MaterialSummary,
    Page,
    RevisionCreate,
    RevisionDetail,
    RevisionSummary,
    RunDetail,
    RunSummary,
    SentenceDetail,
)
from app.modules.reading_materials.segmentation import is_letter


def error(status: int, code: str) -> SecurityError:
    messages = {
        404: "Resource not found",
        409: "Material changed. Reload and try again.",
        422: "Invalid request",
        503: "Service unavailable",
    }
    return SecurityError(status, code, messages[status])


def protect(db: Session, principal: Principal, learner_id: UUID, action: Action) -> Principal:
    principal = protect_principal_for_write(db, principal)
    authorize_learner_action_for_write(db, principal, learner_id, action)
    return principal


def recheck(db: Session, principal: Principal, learner_id: UUID, action: Action) -> None:
    assert_protected_session_live(db, principal)
    assert_protected_learner_action_live(db, principal, learner_id, action)


def get_material(db: Session, learner_id: UUID, identity: UUID, *, lock: bool = False) -> Material:
    row = repo.material(db, learner_id, identity, lock=lock)
    if row is None:
        raise error(404, "not_found")
    if row.archived_at is not None and not lock:
        raise error(404, "not_found")
    return row


def ensure_writable(row: Material) -> None:
    """Call after post-lock authorization rechecks, before state disclosure."""
    if row.archived_at is not None:
        raise error(409, "material_state_conflict")


def get_revision(db: Session, material_id: UUID, identity: UUID, *, lock: bool = False) -> Revision:
    row = repo.revision(db, material_id, identity, lock=lock)
    if row is None:
        raise error(404, "not_found")
    return row


def revision_summary(row: Revision) -> RevisionSummary:
    return RevisionSummary(**{name: getattr(row, name) for name in RevisionSummary.model_fields})


def material_summary(db: Session, row: Material) -> MaterialSummary:
    return MaterialSummary(
        id=row.id,
        created_at=row.created_at,
        row_version=row.row_version,
        archived_at=row.archived_at,
        latest_revision=revision_summary(repo.latest(db, row.id)),
    )


def run_summary(row: Run) -> RunSummary:
    return RunSummary(**{name: getattr(row, name) for name in RunSummary.model_fields})


def run_detail(
    db: Session, material_id: UUID, revision: Revision, row: Run, include_sentences: bool = False
) -> RunDetail:
    detail = RunDetail(
        **run_summary(row).model_dump(),
        profile=profiles.build(material_id, row) if row.status == "succeeded" else None,
    )
    if include_sentences and row.status == "succeeded":
        assert row.normalized_text is not None
        detail.sentences = [
            SentenceDetail(
                **{
                    name: getattr(s, name)
                    for name in SentenceDetail.model_fields
                    if name not in {"original_text", "normalized_text"}
                },
                original_text=revision.original_text[s.source_start : s.source_end],
                normalized_text=row.normalized_text[s.analysis_start : s.analysis_end],
            )
            for s in repo.sentences(db, row.id)
        ]
    return detail


def cursor_pair(value: str | None) -> tuple[datetime, UUID] | None:
    if value is None:
        return None
    try:
        timestamp, identity = value.split("|")
        instant = datetime.fromisoformat(timestamp)
        if instant.tzinfo is None:
            raise ValueError("Timezone required")
        return instant.astimezone(UTC), UUID(identity)
    except (ValueError, OverflowError) as exc:
        raise error(422, "validation_error") from exc


def cursor_number(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        n = int(value)
        if not 1 <= n <= 2147483647:
            raise ValueError("Invalid cursor")
        return n
    except ValueError as exc:
        raise error(422, "validation_error") from exc


def create(
    db: Session, principal: Principal, learner_id: UUID, payload: MaterialCreate
) -> MaterialSummary:
    try:
        principal = protect(db, principal, learner_id, Action.CREATE_READING_MATERIAL)
        recheck(db, principal, learner_id, Action.CREATE_READING_MATERIAL)
        now = repo.now(db)
        row = Material(
            learner_id=learner_id,
            created_by_user_id=principal.user_id,
            created_at=now,
            updated_at=now,
        )
        repo.save(db, row)
        add_revision(db, row.id, 1, principal.user_id, payload, now)
        public = material_summary(db, row)
        db.commit()
        return public
    except Exception:
        db.rollback()
        raise


def add_revision(
    db: Session,
    material_id: UUID,
    number: int,
    actor_id: UUID,
    payload: MaterialCreate,
    now: datetime,
) -> Revision:
    row = Revision(
        material_id=material_id,
        revision_number=number,
        title=payload.title,
        language_tag="en",
        source_kind="plain_text",
        original_text=payload.text,
        source_sha256=hashlib.sha256(payload.text.encode("utf-8")).hexdigest(),
        created_by_user_id=actor_id,
        created_at=now,
    )
    repo.save(db, row)
    return row


def revise(
    db: Session, principal: Principal, learner_id: UUID, material_id: UUID, payload: RevisionCreate
) -> MaterialSummary:
    try:
        principal = protect(db, principal, learner_id, Action.REVISE_READING_MATERIAL)
        row = get_material(db, learner_id, material_id, lock=True)
        recheck(db, principal, learner_id, Action.REVISE_READING_MATERIAL)
        ensure_writable(row)
        if row.row_version != payload.row_version:
            raise error(409, "version_conflict")
        number = repo.latest(db, material_id).revision_number + 1
        now = repo.now(db)
        add_revision(db, row.id, number, principal.user_id, payload, now)
        row.updated_at = now
        flag_modified(row, "updated_at")
        db.flush()
        public = material_summary(db, row)
        db.commit()
        return public
    except StaleDataError as exc:
        db.rollback()
        raise error(409, "version_conflict") from exc
    except Exception:
        db.rollback()
        raise


def archive(
    db: Session, principal: Principal, learner_id: UUID, material_id: UUID, version: int
) -> MaterialSummary:
    try:
        principal = protect(db, principal, learner_id, Action.ARCHIVE_READING_MATERIAL)
        row = get_material(db, learner_id, material_id, lock=True)
        recheck(db, principal, learner_id, Action.ARCHIVE_READING_MATERIAL)
        ensure_writable(row)
        if row.row_version != version:
            raise error(409, "version_conflict")
        row.archived_at = row.updated_at = repo.now(db)
        db.flush()
        public = material_summary(db, row)
        db.commit()
        return public
    except StaleDataError as exc:
        db.rollback()
        raise error(409, "version_conflict") from exc
    except Exception:
        db.rollback()
        raise


def read_material(
    db: Session, principal: Principal, learner_id: UUID, material_id: UUID
) -> MaterialSummary:
    authorize_learner_action(db, principal, learner_id, Action.READ_READING_MATERIAL)
    return material_summary(db, get_material(db, learner_id, material_id))


def list_materials(
    db: Session, principal: Principal, learner_id: UUID, cursor: str | None, limit: int
) -> Page[MaterialSummary]:
    authorize_learner_action(db, principal, learner_id, Action.READ_READING_MATERIAL)
    rows = repo.material_page(db, learner_id, cursor_pair(cursor), limit)
    return Page(
        items=[material_summary(db, row) for row in rows[:limit]],
        next_cursor=f"{rows[limit - 1].created_at.isoformat()}|{rows[limit - 1].id}"
        if len(rows) > limit
        else None,
    )


def list_revisions(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    material_id: UUID,
    cursor: str | None,
    limit: int,
) -> Page[RevisionSummary]:
    authorize_learner_action(db, principal, learner_id, Action.READ_READING_MATERIAL)
    get_material(db, learner_id, material_id)
    rows = repo.revision_page(db, material_id, cursor_number(cursor), limit)
    return Page(
        items=[revision_summary(row) for row in rows[:limit]],
        next_cursor=str(rows[limit - 1].revision_number) if len(rows) > limit else None,
    )


def read_revision(
    db: Session, principal: Principal, learner_id: UUID, material_id: UUID, revision_id: UUID
) -> RevisionDetail:
    authorize_learner_action(db, principal, learner_id, Action.READ_READING_MATERIAL)
    get_material(db, learner_id, material_id)
    row = get_revision(db, material_id, revision_id)
    return RevisionDetail(**revision_summary(row).model_dump(), original_text=row.original_text)


def list_runs(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    material_id: UUID,
    revision_id: UUID,
    cursor: str | None,
    limit: int,
) -> Page[RunSummary]:
    authorize_learner_action(db, principal, learner_id, Action.READ_READING_MATERIAL)
    get_material(db, learner_id, material_id)
    get_revision(db, material_id, revision_id)
    rows = repo.run_page(db, revision_id, cursor_pair(cursor), limit)
    return Page(
        items=[run_summary(row) for row in rows[:limit]],
        next_cursor=f"{rows[limit - 1].started_at.isoformat()}|{rows[limit - 1].id}"
        if len(rows) > limit
        else None,
    )


def read_run(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    material_id: UUID,
    revision_id: UUID,
    run_id: UUID,
    include_sentences: bool,
) -> RunDetail:
    authorize_learner_action(db, principal, learner_id, Action.READ_READING_MATERIAL)
    get_material(db, learner_id, material_id)
    revision = get_revision(db, material_id, revision_id)
    row = repo.run(db, revision_id, run_id)
    if row is None:
        raise error(404, "not_found")
    return run_detail(db, material_id, revision, row, include_sentences)


@dataclass(frozen=True)
class Claim:
    id: UUID
    version: int
    source: str
    fingerprint: str


def claim(
    db: Session, principal: Principal, learner_id: UUID, material_id: UUID, revision_id: UUID
) -> Claim | RunDetail:
    try:
        principal = protect(db, principal, learner_id, Action.PROCESS_READING_MATERIAL)
        material = get_material(db, learner_id, material_id, lock=True)
        revision = get_revision(db, material_id, revision_id, lock=True)
        fingerprint = pipeline.fingerprint()
        rows = repo.matching_runs(db, revision_id, fingerprint)
        recheck(db, principal, learner_id, Action.PROCESS_READING_MATERIAL)
        ensure_writable(material)
        if not any(is_letter(c) for c in revision.original_text):
            raise error(422, "validation_error")
        succeeded = next((r for r in rows if r.status == "succeeded"), None)
        if succeeded is not None:
            public = run_detail(db, material_id, revision, succeeded)
            db.commit()
            return public
        now = repo.now(db)
        for old in rows:
            if old.status == "running":
                if old.lease_expires_at > now:
                    raise error(409, "processing_conflict")
                old.status, old.finished_at, old.failure_code = (
                    "failed",
                    now,
                    "processing_interrupted",
                )
        db.flush()  # Release expired partial-unique slots before inserting a new attempt.
        row = Run(
            revision_id=revision_id,
            requested_by_user_id=principal.user_id,
            attempt_number=max((r.attempt_number for r in rows), default=0) + 1,
            status="running",
            started_at=now,
            lease_expires_at=now + timedelta(seconds=pipeline.LEASE_SECONDS),
            **pipeline.provenance(),
        )
        repo.save(db, row)
        work = Claim(row.id, row.row_version, revision.original_text, fingerprint)
        db.commit()
        return work
    except Exception:
        db.rollback()
        raise


def validate_output(work: Claim, output: pipeline.Output) -> None:
    doc = output.document
    rows = output.sentences
    if (
        not rows
        or doc.sentence_count != len(rows)
        or doc.character_count != len(output.normalized_text)
    ):
        raise ValueError("Invalid output")
    if hashlib.sha256(output.normalized_text.encode()).hexdigest() != output.normalized_sha256:
        raise ValueError("Invalid output")
    previous_source = previous_analysis = 0
    for ordinal, s in enumerate(rows, 1):
        if not (
            s.ordinal == ordinal
            and previous_source <= s.source_start < s.source_end <= len(work.source)
            and previous_analysis
            <= s.analysis_start
            < s.analysis_end
            <= len(output.normalized_text)
            and s.word_count > 0
            and 0 < s.max_word_letter_count <= s.total_word_letter_count
        ):
            raise ValueError("Invalid output")
        previous_source, previous_analysis = s.source_end, s.analysis_end
    if (
        doc.word_count != sum(s.word_count for s in rows)
        or doc.total_word_letter_count != sum(s.total_word_letter_count for s in rows)
        or doc.max_word_letter_count != max(s.max_word_letter_count for s in rows)
        or doc.max_sentence_word_count != max(s.word_count for s in rows)
        or not 1 <= doc.unique_word_count <= doc.word_count
    ):
        raise ValueError("Invalid output")


def publish(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    material_id: UUID,
    revision_id: UUID,
    work: Claim,
    output: pipeline.Output | None,
) -> RunDetail:
    try:
        # Fresh auth/role resolution after compute; no cached relationship grant is trusted.
        principal = protect(db, principal, learner_id, Action.PROCESS_READING_MATERIAL)
        material = get_material(db, learner_id, material_id, lock=True)
        revision = get_revision(db, material_id, revision_id, lock=True)
        row = repo.run(db, revision_id, work.id, lock=True)
        recheck(db, principal, learner_id, Action.PROCESS_READING_MATERIAL)
        ensure_writable(material)
        now = repo.now(db)
        if row is None or row.requested_by_user_id != principal.user_id:
            raise error(404, "not_found")
        if (
            row.status != "running"
            or row.row_version != work.version
            or row.pipeline_fingerprint != work.fingerprint
            or row.lease_expires_at <= now
        ):
            raise error(409, "processing_conflict")
        if output is not None:
            db.add_all([Sentence(run_id=row.id, **asdict(s)) for s in output.sentences])
            db.flush()  # Evidence inserted while parent is running, then publish as a unit.
            recheck(db, principal, learner_id, Action.PROCESS_READING_MATERIAL)
            ensure_writable(material)
            if row.lease_expires_at <= repo.now(db):
                raise error(409, "processing_conflict")
            row.normalized_text, row.normalized_sha256 = (
                output.normalized_text,
                output.normalized_sha256,
            )
            for name, value in asdict(output.document).items():
                setattr(row, name, value)
            row.status = "succeeded"
        else:
            row.status, row.failure_code = "failed", "pipeline_failed"
        row.finished_at = repo.now(db)
        db.flush()
        result = run_detail(db, material_id, revision, row)
        db.commit()
        return result
    except StaleDataError as exc:
        db.rollback()
        raise error(409, "processing_conflict") from exc
    except Exception:
        db.rollback()
        raise


def process(
    db: Session, principal: Principal, learner_id: UUID, material_id: UUID, revision_id: UUID
) -> tuple[RunDetail, int]:
    work = claim(db, principal, learner_id, material_id, revision_id)
    if isinstance(work, RunDetail):
        return work, 200
    output = None
    try:
        output = pipeline.process(work.source)
        validate_output(work, output)
    except Exception:
        # Deliberately do not log exception strings, input, tokens, or parser context.
        output = None
    result = publish(db, principal, learner_id, material_id, revision_id, work, output)
    if output is None:
        raise error(503, "service_unavailable")
    return result, 201
