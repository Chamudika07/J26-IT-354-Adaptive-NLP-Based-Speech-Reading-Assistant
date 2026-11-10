"""Learners-owned administrator onboarding transactions; no auth table writes."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.auth.provisioning import assert_educator, protect_administrator
from app.modules.auth.service import assert_protected_session_live
from app.modules.learners import repository as repo
from app.modules.learners.models import EducatorLearnerRelationship, LearnerProfile
from app.modules.learners.onboarding_schemas import (
    EducatorGrantCreate,
    EducatorGrantRead,
    LearnerCreate,
    LearnerCreated,
)


def create_learner(db: Session, principal: Principal, payload: LearnerCreate) -> LearnerCreated:
    try:
        actor = protect_administrator(db, principal)
        row = LearnerProfile(display_name=payload.display_name, created_by_user_id=actor.user_id)
        db.add(row)
        db.flush()
        result = LearnerCreated.model_validate(row)
        assert_protected_session_live(db, actor)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def create_grant(
    db: Session, principal: Principal, learner_id: UUID, payload: EducatorGrantCreate
) -> EducatorGrantRead:
    try:
        actor = protect_administrator(db, principal, payload.educator_user_id)
        assert_educator(db, payload.educator_user_id)
        if repo.accessible_profile(db, learner_id, lock=True) is None:
            raise SecurityError(404, "not_found", "Resource not found")
        existing = db.scalar(
            select(EducatorLearnerRelationship.id).where(
                EducatorLearnerRelationship.learner_id == learner_id,
                EducatorLearnerRelationship.educator_user_id == payload.educator_user_id,
                EducatorLearnerRelationship.revoked_at.is_(None),
            )
        )
        if existing is not None:
            raise SecurityError(
                409, "grant_exists", "Revoke the existing grant before replacing it"
            )
        now = repo.current_time(db)
        if payload.expires_at <= now:
            raise SecurityError(422, "invalid_expiry", "Grant expiry must be in the future")
        row = EducatorLearnerRelationship(
            learner_id=learner_id,
            educator_user_id=payload.educator_user_id,
            access_level=payload.access_level,
            expires_at=payload.expires_at,
            granted_by_user_id=actor.user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        result = EducatorGrantRead.model_validate(row)
        assert_protected_session_live(db, actor)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def revoke_grant(
    db: Session, principal: Principal, learner_id: UUID, grant_id: UUID
) -> EducatorGrantRead:
    try:
        actor = protect_administrator(db, principal)
        # Same learner -> relationship lock order as all existing learner writes.
        if repo.accessible_profile(db, learner_id, lock=True) is None:
            raise SecurityError(404, "not_found", "Resource not found")
        row = db.scalar(
            select(EducatorLearnerRelationship)
            .where(
                EducatorLearnerRelationship.id == grant_id,
                EducatorLearnerRelationship.learner_id == learner_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise SecurityError(404, "not_found", "Resource not found")
        assert_protected_session_live(db, actor)
        if row.revoked_at is None:
            row.revoked_at = repo.current_time(db)
            row.revoked_by_user_id = actor.user_id
            db.flush()
        result = EducatorGrantRead.model_validate(row)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
