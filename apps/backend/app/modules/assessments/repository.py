"""Assessment-owned queries and persistence; caller owns every transaction."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.modules.assessments.models import (
    ReadingAssessmentMaterial as Material,
)
from app.modules.assessments.models import (
    ReadingAssessmentResult as Result,
)
from app.modules.assessments.models import (
    ReadingAssessmentSession as Assessment,
)


def now(db: Session) -> datetime:
    return cast(datetime, db.scalar(select(func.clock_timestamp())))


def material(db: Session, identity: UUID, *, lock: bool = False) -> Material | None:
    query = (
        select(Material).where(Material.id == identity).execution_options(populate_existing=True)
    )
    return db.scalar(query.with_for_update(read=True) if lock else query)


def materials(db: Session, cursor: UUID | None, limit: int) -> list[Material]:
    query = select(Material).where(Material.is_active.is_(True))
    if cursor is not None:
        query = query.where(Material.id > cursor)
    return list(db.scalars(query.order_by(Material.id).limit(limit + 1)))


def assessment(
    db: Session, learner_id: UUID, identity: UUID, *, lock: bool = False
) -> Assessment | None:
    query = (
        select(Assessment)
        .where(Assessment.id == identity, Assessment.learner_id == learner_id)
        .execution_options(populate_existing=True)
    )
    return db.scalar(query.with_for_update() if lock else query)


def active_session(db: Session, learner_id: UUID, actor_id: UUID) -> bool:
    return (
        db.scalar(
            select(Assessment.id).where(
                Assessment.learner_id == learner_id,
                Assessment.administered_by_user_id == actor_id,
                Assessment.status == "started",
            )
        )
        is not None
    )


def history(
    db: Session, learner_id: UUID, cursor: tuple[datetime, UUID] | None, limit: int
) -> list[tuple[Assessment, Material, Result | None]]:
    query = (
        select(Assessment, Material, Result)
        .join(Material, Material.id == Assessment.material_id)
        .outerjoin(Result, Result.session_id == Assessment.id)
        .where(Assessment.learner_id == learner_id)
    )
    if cursor is not None:
        query = query.where(tuple_(Assessment.started_at, Assessment.id) < cursor)
    rows = db.execute(
        query.order_by(Assessment.started_at.desc(), Assessment.id.desc()).limit(limit + 1)
    )
    return [(s, m, r) for s, m, r in rows]


def result(db: Session, session_id: UUID) -> Result | None:
    return db.scalar(select(Result).where(Result.session_id == session_id))


def insert_session(db: Session, row: Assessment) -> None:
    db.add(row)
    db.flush()


def insert_result(db: Session, row: Result) -> None:
    db.add(row)
    db.flush()
