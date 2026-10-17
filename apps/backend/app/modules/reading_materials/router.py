"""Learner-scoped JSON-only text material endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Query, Response

from app.modules.auth.dependencies import Authenticated, Database
from app.modules.reading_materials import service
from app.modules.reading_materials.schemas import (
    ArchiveRequest,
    EmptyRequest,
    MaterialCreate,
    MaterialSummary,
    Page,
    RevisionCreate,
    RevisionDetail,
    RevisionSummary,
    RunDetail,
    RunSummary,
)

EMPTY_REQUEST = EmptyRequest()
router = APIRouter()
BASE = "/learners/{learner_id}/reading-materials"
REVISIONS = BASE + "/{material_id}/revisions"
RUNS = REVISIONS + "/{revision_id}/processing-runs"
Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=100)]


def private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post(BASE, response_model=MaterialSummary, status_code=201)
def create(
    learner_id: UUID,
    payload: MaterialCreate,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> MaterialSummary:
    private(response)
    return service.create(db, principal, learner_id, payload)


@router.get(BASE, response_model=Page[MaterialSummary])
def materials(
    learner_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    cursor: Cursor = None,
    limit: Limit = 25,
) -> Page[MaterialSummary]:
    private(response)
    return service.list_materials(db, principal, learner_id, cursor, limit)


@router.get(BASE + "/{material_id}", response_model=MaterialSummary)
def material(
    learner_id: UUID, material_id: UUID, principal: Authenticated, db: Database, response: Response
) -> MaterialSummary:
    private(response)
    return service.read_material(db, principal, learner_id, material_id)


@router.post(REVISIONS, response_model=MaterialSummary, status_code=201)
def revise(
    learner_id: UUID,
    material_id: UUID,
    payload: RevisionCreate,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> MaterialSummary:
    private(response)
    return service.revise(db, principal, learner_id, material_id, payload)


@router.get(REVISIONS, response_model=Page[RevisionSummary])
def revisions(
    learner_id: UUID,
    material_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    cursor: Cursor = None,
    limit: Limit = 25,
) -> Page[RevisionSummary]:
    private(response)
    return service.list_revisions(db, principal, learner_id, material_id, cursor, limit)


@router.get(REVISIONS + "/{revision_id}", response_model=RevisionDetail)
def revision(
    learner_id: UUID,
    material_id: UUID,
    revision_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> RevisionDetail:
    private(response)
    return service.read_revision(db, principal, learner_id, material_id, revision_id)


@router.post(RUNS, response_model=RunDetail, status_code=201)
def process(
    learner_id: UUID,
    material_id: UUID,
    revision_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    payload: Annotated[EmptyRequest, Body()] = EMPTY_REQUEST,
) -> RunDetail:
    private(response)
    result, status = service.process(db, principal, learner_id, material_id, revision_id)
    response.status_code = status
    return result


@router.get(RUNS, response_model=Page[RunSummary])
def runs(
    learner_id: UUID,
    material_id: UUID,
    revision_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    cursor: Cursor = None,
    limit: Limit = 25,
) -> Page[RunSummary]:
    private(response)
    return service.list_runs(db, principal, learner_id, material_id, revision_id, cursor, limit)


@router.get(RUNS + "/{run_id}", response_model=RunDetail)
def run(
    learner_id: UUID,
    material_id: UUID,
    revision_id: UUID,
    run_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    include_sentences: bool = False,
) -> RunDetail:
    private(response)
    return service.read_run(
        db, principal, learner_id, material_id, revision_id, run_id, include_sentences
    )


@router.post(BASE + "/{material_id}/archive", response_model=MaterialSummary)
def archive(
    learner_id: UUID,
    material_id: UUID,
    payload: ArchiveRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> MaterialSummary:
    private(response)
    return service.archive(db, principal, learner_id, material_id, payload.row_version)
