"""Learners-owned read contracts for authorization; never writes auth tables."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.learners.models import (
    EducatorLearnerRelationship,
    GuardianLearnerRelationship,
    LearnerProfile,
)


def current_time(db: Session) -> datetime:
    return cast(datetime, db.execute(select(func.clock_timestamp())).scalar_one())


def accessible_profile(db: Session, learner_id: UUID) -> LearnerProfile | None:
    return db.scalar(
        select(LearnerProfile)
        .where(LearnerProfile.id == learner_id, LearnerProfile.archived_at.is_(None))
        .execution_options(populate_existing=True)
    )


def guardian_level(db: Session, actor_id: UUID, learner_id: UUID) -> str | None:
    return db.scalar(
        select(GuardianLearnerRelationship.access_level).where(
            GuardianLearnerRelationship.guardian_user_id == actor_id,
            GuardianLearnerRelationship.learner_id == learner_id,
            GuardianLearnerRelationship.revoked_at.is_(None),
        )
    )


def educator_level(db: Session, actor_id: UUID, learner_id: UUID, now: datetime) -> str | None:
    return db.scalar(
        select(EducatorLearnerRelationship.access_level).where(
            EducatorLearnerRelationship.educator_user_id == actor_id,
            EducatorLearnerRelationship.learner_id == learner_id,
            EducatorLearnerRelationship.revoked_at.is_(None),
            EducatorLearnerRelationship.expires_at > now,
        )
    )
