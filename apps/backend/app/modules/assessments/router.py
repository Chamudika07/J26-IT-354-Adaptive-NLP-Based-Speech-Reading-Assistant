"""Reading-specific routes; no generic material administration or result edits."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.modules.assessments import service
from app.modules.assessments.schemas import (
    AssessmentAbandonRequest,
    AssessmentCompletionRequest,
    AssessmentHistoryPage,
    AssessmentMaterialPage,
    AssessmentSessionResponse,
    AssessmentStartRequest,
    AssessmentStartResponse,
)
from app.modules.auth.dependencies import Authenticated, Database

router = APIRouter()
BASE = "/learners/{learner_id}/reading-assessments"
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/assessment-materials", response_model=AssessmentMaterialPage)
def materials(
    principal: Authenticated,
    db: Database,
    response: Response,
    cursor: UUID | None = None,
    limit: Limit = 25,
) -> AssessmentMaterialPage:
    response.headers["Cache-Control"] = "no-store"
    return service.list_materials(db, principal, cursor, limit)


@router.post(BASE, response_model=AssessmentStartResponse, status_code=201)
def start(
    learner_id: UUID,
    payload: AssessmentStartRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> AssessmentStartResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.start(db, principal, learner_id, payload)


@router.get(BASE, response_model=AssessmentHistoryPage)
def history(
    learner_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    cursor: Annotated[str | None, Query(max_length=100)] = None,
    limit: Limit = 25,
) -> AssessmentHistoryPage:
    response.headers["Cache-Control"] = "no-store"
    return service.list_history(db, principal, learner_id, cursor, limit)


@router.get(
    BASE + "/{assessment_id}", response_model=AssessmentStartResponse | AssessmentSessionResponse
)
def detail(
    learner_id: UUID,
    assessment_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> AssessmentSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.read_assessment(db, principal, learner_id, assessment_id)


@router.post(BASE + "/{assessment_id}/complete", response_model=AssessmentSessionResponse)
def complete(
    learner_id: UUID,
    assessment_id: UUID,
    payload: AssessmentCompletionRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> AssessmentSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.finish(db, principal, learner_id, assessment_id, payload)


@router.post(BASE + "/{assessment_id}/abandon", response_model=AssessmentSessionResponse)
def abandon(
    learner_id: UUID,
    assessment_id: UUID,
    payload: AssessmentAbandonRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> AssessmentSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.finish(db, principal, learner_id, assessment_id, payload)
