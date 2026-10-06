"""Approved profile reads and versioned accessibility preferences only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.modules.auth.dependencies import Authenticated, Database
from app.modules.learners import service
from app.modules.learners.schemas import (
    LearnerDetailEducator,
    LearnerDetailSelfGuardian,
    LearnerListResponse,
    LearnerPreferenceResponse,
    LearnerPreferenceUpdate,
)

router = APIRouter()


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
