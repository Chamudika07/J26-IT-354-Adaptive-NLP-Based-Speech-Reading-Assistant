"""Learners-owned queries, locks, and persistence; never commits or writes auth tables."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Select, func, select, union
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.modules.learners.models import (
    EducatorLearnerRelationship,
    GuardianLearnerRelationship,
    LearnerPreferences,
    LearnerProfile,
)


def current_time(db: Session) -> datetime:
    return cast(datetime, db.execute(select(func.clock_timestamp())).scalar_one())


def accessible_profile(
    db: Session, learner_id: UUID, *, lock: bool = False
) -> LearnerProfile | None:
    query = (
        select(LearnerProfile)
        .where(LearnerProfile.id == learner_id, LearnerProfile.archived_at.is_(None))
        .execution_options(populate_existing=True)
    )
    return db.scalar(query.with_for_update() if lock else query)


def _guardian_grants(actor_id: UUID) -> Select[tuple[UUID, str]]:
    return select(
        GuardianLearnerRelationship.learner_id, GuardianLearnerRelationship.access_level
    ).where(
        GuardianLearnerRelationship.guardian_user_id == actor_id,
        GuardianLearnerRelationship.revoked_at.is_(None),
        GuardianLearnerRelationship.access_level.in_(("viewer", "manager")),
    )


def _educator_grants(actor_id: UUID, now: datetime) -> Select[tuple[UUID, str]]:
    return select(
        EducatorLearnerRelationship.learner_id, EducatorLearnerRelationship.access_level
    ).where(
        EducatorLearnerRelationship.educator_user_id == actor_id,
        EducatorLearnerRelationship.revoked_at.is_(None),
        EducatorLearnerRelationship.expires_at > now,
        EducatorLearnerRelationship.access_level.in_(("viewer", "instructor")),
    )


def guardian_level(
    db: Session, actor_id: UUID, learner_id: UUID, *, lock: bool = False
) -> str | None:
    query = (
        _guardian_grants(actor_id)
        .with_only_columns(GuardianLearnerRelationship.access_level)
        .where(GuardianLearnerRelationship.learner_id == learner_id)
    )
    return db.scalar(query.with_for_update(read=True) if lock else query)


def educator_level(db: Session, actor_id: UUID, learner_id: UUID, now: datetime) -> str | None:
    return db.scalar(
        _educator_grants(actor_id, now)
        .with_only_columns(EducatorLearnerRelationship.access_level)
        .where(EducatorLearnerRelationship.learner_id == learner_id)
    )


def accessible_page(
    db: Session,
    actor_id: UUID,
    roles: frozenset[str],
    cursor: UUID | None,
    limit: int,
) -> list[tuple[UUID, str]]:
    """Scope and deduplicate in SQL BEFORE pagination. Cursor never grants access."""
    candidates: list[Select[tuple[UUID]]] = []
    if "learner" in roles:
        candidates.append(
            select(LearnerProfile.id.label("learner_id")).where(
                LearnerProfile.learner_user_id == actor_id
            )
        )
    if "guardian" in roles:
        candidates.append(
            _guardian_grants(actor_id).with_only_columns(GuardianLearnerRelationship.learner_id)
        )
    if "educator" in roles:
        candidates.append(
            _educator_grants(actor_id, current_time(db)).with_only_columns(
                EducatorLearnerRelationship.learner_id
            )
        )
    if not candidates:
        return []
    scoped = union(*candidates).subquery()
    query = (
        select(LearnerProfile.id, LearnerProfile.display_name)
        .join(scoped, scoped.c.learner_id == LearnerProfile.id)
        .where(LearnerProfile.archived_at.is_(None))
    )
    if cursor is not None:
        query = query.where(LearnerProfile.id > cursor)
    rows = db.execute(query.order_by(LearnerProfile.id).limit(limit + 1))
    return [(row.id, row.display_name) for row in rows]


def preferences(db: Session, learner_id: UUID, *, lock: bool = False) -> LearnerPreferences | None:
    query = (
        select(LearnerPreferences)
        .where(LearnerPreferences.learner_id == learner_id)
        .execution_options(populate_existing=True)
    )
    return db.scalar(query.with_for_update() if lock else query)


def save_preferences(
    db: Session,
    row: LearnerPreferences | None,
    learner_id: UUID,
    actor_id: UUID,
    values: dict[str, object],
    now: datetime,
) -> LearnerPreferences:
    """Caller supplies validated allowlisted values after locking and checking version."""
    if row is None:
        row = LearnerPreferences(
            learner_id=learner_id, updated_by_user_id=actor_id, created_at=now, updated_at=now
        )
        db.add(row)
    else:
        row.updated_by_user_id = actor_id
        row.updated_at = now
        # Even an accepted no-op is one versioned ORM UPDATE, not a silent success.
        flag_modified(row, "updated_at")
    for name, value in values.items():
        setattr(row, name, value)
    db.flush()
    return row
