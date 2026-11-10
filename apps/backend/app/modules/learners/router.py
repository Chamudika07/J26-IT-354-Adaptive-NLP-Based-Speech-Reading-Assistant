"""Profiles, preferences and administrator-managed learner onboarding."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.modules.auth.dependencies import Authenticated, Database
from app.modules.learners import onboarding, service
from app.modules.learners.onboarding_schemas import (
    EducatorGrantCreate,
    EducatorGrantRead,
    LearnerCreate,
    LearnerCreated,
)
from app.modules.learners.schemas import (
    LearnerDetailEducator,
    LearnerDetailSelfGuardian,
    LearnerListResponse,
    LearnerPreferenceResponse,
    LearnerPreferenceUpdate,
)

router = APIRouter()


@router.post("", response_model=LearnerCreated, status_code=201)
def create_learner(
    payload: LearnerCreate, principal: Authenticated, db: Database, response: Response
) -> LearnerCreated:
    """Administrator only. Create a login-less profile; no content access or consent is granted."""
    response.headers["Cache-Control"] = "no-store"
    return onboarding.create_learner(db, principal, payload)


@router.post("/{learner_id}/educator-grants", response_model=EducatorGrantRead, status_code=201)
def create_grant(
    learner_id: UUID,
    payload: EducatorGrantCreate,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> EducatorGrantRead:
    """Administrator only. Assign an active educator explicit, expiring learner access."""
    response.headers["Cache-Control"] = "no-store"
    return onboarding.create_grant(db, principal, learner_id, payload)


@router.post("/{learner_id}/educator-grants/{grant_id}/revoke", response_model=EducatorGrantRead)
def revoke_grant(
    learner_id: UUID,
    grant_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> EducatorGrantRead:
    """Administrator only. Revoke an assignment; repeating a revocation is safe."""
    response.headers["Cache-Control"] = "no-store"
    return onboarding.revoke_grant(db, principal, learner_id, grant_id)


@router.get("", response_model=LearnerListResponse)
def list_learners(
    principal: Authenticated,
    db: Database,
    response: Response,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> LearnerListResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.list_learners(db, principal, cursor, limit)


@router.get("/{learner_id}", response_model=LearnerDetailSelfGuardian | LearnerDetailEducator)
def read_profile(
    learner_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> LearnerDetailSelfGuardian | LearnerDetailEducator:
    response.headers["Cache-Control"] = "no-store"
    return service.read_profile(db, principal, learner_id)


@router.get("/{learner_id}/preferences", response_model=LearnerPreferenceResponse)
def read_preferences(
    learner_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> LearnerPreferenceResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.read_preferences(db, principal, learner_id)


@router.patch("/{learner_id}/preferences", response_model=LearnerPreferenceResponse)
def update_preferences(
    learner_id: UUID,
    payload: LearnerPreferenceUpdate,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> LearnerPreferenceResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.update_preferences(db, principal, learner_id, payload)
