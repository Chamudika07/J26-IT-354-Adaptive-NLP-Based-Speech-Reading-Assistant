"""Reading-material persistence only. Services own commit/rollback."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

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


def now(db: Session) -> datetime:
    return cast(datetime, db.scalar(select(func.clock_timestamp())))


def material(
    db: Session, learner_id: UUID, identity: UUID, *, lock: bool = False
) -> Material | None:
    query = (
        select(Material)
        .where(Material.id == identity, Material.learner_id == learner_id)
        .execution_options(populate_existing=True)
    )
    return db.scalar(query.with_for_update() if lock else query)


def revision(
    db: Session, material_id: UUID, identity: UUID, *, lock: bool = False
) -> Revision | None:
    query = (
        select(Revision)
        .where(Revision.id == identity, Revision.material_id == material_id)
        .execution_options(populate_existing=True)
    )
    return db.scalar(query.with_for_update() if lock else query)


def run(db: Session, revision_id: UUID, identity: UUID, *, lock: bool = False) -> Run | None:
    query = (
        select(Run)
        .where(Run.id == identity, Run.revision_id == revision_id)
        .execution_options(populate_existing=True)
    )
    return db.scalar(query.with_for_update() if lock else query)


def latest(db: Session, material_id: UUID) -> Revision:
    return db.scalars(
        select(Revision)
        .where(Revision.material_id == material_id)
        .order_by(Revision.revision_number.desc())
        .limit(1)
    ).one()


def material_page(
    db: Session, learner_id: UUID, cursor: tuple[datetime, UUID] | None, limit: int
) -> list[Material]:
    query = select(Material).where(
        Material.learner_id == learner_id, Material.archived_at.is_(None)
    )
    if cursor:
        query = query.where(tuple_(Material.created_at, Material.id) < cursor)
    return list(
        db.scalars(query.order_by(Material.created_at.desc(), Material.id.desc()).limit(limit + 1))
    )


def revision_page(db: Session, material_id: UUID, cursor: int | None, limit: int) -> list[Revision]:
    query = select(Revision).where(Revision.material_id == material_id)
    if cursor is not None:
        query = query.where(Revision.revision_number < cursor)
    return list(db.scalars(query.order_by(Revision.revision_number.desc()).limit(limit + 1)))


def run_page(
    db: Session, revision_id: UUID, cursor: tuple[datetime, UUID] | None, limit: int
) -> list[Run]:
    query = select(Run).where(Run.revision_id == revision_id)
    if cursor:
        query = query.where(tuple_(Run.started_at, Run.id) < cursor)
    return list(db.scalars(query.order_by(Run.started_at.desc(), Run.id.desc()).limit(limit + 1)))


def matching_runs(db: Session, revision_id: UUID, fingerprint: str) -> list[Run]:
    return list(
        db.scalars(
            select(Run)
            .where(Run.revision_id == revision_id, Run.pipeline_fingerprint == fingerprint)
            .order_by(Run.attempt_number.desc())
            .with_for_update()
        )
    )


def sentences(db: Session, run_id: UUID) -> list[Sentence]:
    return list(
        db.scalars(select(Sentence).where(Sentence.run_id == run_id).order_by(Sentence.ordinal))
    )


def save(db: Session, row: Material | Revision | Run | Sentence) -> None:
    db.add(row)
    db.flush()
