"""Module-owned PDF queries; service coordinates authorization and transactions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select, tuple_
from sqlalchemy.orm import Session

from app.modules.reading_materials.models import ReadingMaterial as Material
from app.modules.reading_materials.pdf.models import ExtractionPage, ExtractionRun, Source


def source(db: Session, learner: UUID, identity: UUID, *, lock: bool = False) -> Source | None:
    q = (
        select(Source)
        .where(Source.id == identity, Source.learner_id == learner)
        .execution_options(populate_existing=True)
    )
    return db.scalar(q.with_for_update() if lock else q)


def upload(db: Session, learner: UUID, actor: UUID, request: UUID) -> Source | None:
    return db.scalar(
        select(Source).where(
            Source.learner_id == learner,
            Source.created_by_user_id == actor,
            Source.upload_request_id == request,
        )
    )


def attempts(db: Session, identity: UUID, fingerprint: str) -> list[ExtractionRun]:
    return list(
        db.scalars(
            select(ExtractionRun)
            .where(
                ExtractionRun.source_id == identity,
                ExtractionRun.extraction_method == "embedded_pdf",
                ExtractionRun.extraction_fingerprint == fingerprint,
            )
            .order_by(ExtractionRun.attempt_number.desc())
            .with_for_update()
        )
    )


def run(
    db: Session, source_id: UUID, identity: UUID, *, lock: bool = False
) -> ExtractionRun | None:
    q = (
        select(ExtractionRun)
        .where(
            ExtractionRun.id == identity,
            ExtractionRun.source_id == source_id,
            ExtractionRun.extraction_method == "embedded_pdf",
        )
        .execution_options(populate_existing=True)
    )
    return db.scalar(q.with_for_update() if lock else q)


def pages(db: Session, identity: UUID) -> list[ExtractionPage]:
    return list(
        db.scalars(
            select(ExtractionPage)
            .where(ExtractionPage.extraction_run_id == identity)
            .order_by(ExtractionPage.page_number)
        )
    )


def latest(db: Session, identity: UUID) -> ExtractionRun | None:
    return db.scalar(
        select(ExtractionRun)
        .where(
            ExtractionRun.source_id == identity, ExtractionRun.extraction_method == "embedded_pdf"
        )
        .order_by(ExtractionRun.started_at.desc(), ExtractionRun.id.desc())
        .limit(1)
    )


def sources(
    db: Session, learner: UUID, cursor: tuple[datetime, UUID] | None, limit: int
) -> list[Source]:
    q = (
        select(Source)
        .outerjoin(Material, Source.material_id == Material.id)
        .where(
            Source.learner_id == learner,
            Source.archived_at.is_(None),
            or_(Source.material_id.is_(None), Material.archived_at.is_(None)),
        )
    )
    if cursor:
        q = q.where(tuple_(Source.created_at, Source.id) < cursor)
    return list(db.scalars(q.order_by(Source.created_at.desc(), Source.id.desc()).limit(limit + 1)))


def history(
    db: Session, identity: UUID, cursor: tuple[datetime, UUID] | None, limit: int
) -> list[ExtractionRun]:
    q = select(ExtractionRun).where(
        ExtractionRun.source_id == identity, ExtractionRun.extraction_method == "embedded_pdf"
    )
    if cursor:
        q = q.where(tuple_(ExtractionRun.started_at, ExtractionRun.id) < cursor)
    return list(
        db.scalars(
            q.order_by(ExtractionRun.started_at.desc(), ExtractionRun.id.desc()).limit(limit + 1)
        )
    )
