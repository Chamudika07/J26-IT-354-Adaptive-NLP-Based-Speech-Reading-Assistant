"""PDF-only multipart boundary; existing text endpoints remain JSON-only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Query, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.types import Message

from app.core.exceptions import SecurityError
from app.modules.auth.dependencies import Authenticated, Database, RuntimeSettings
from app.modules.learners.service import LearnerAction, authorize_learner_action
from app.modules.reading_materials.pdf import service
from app.modules.reading_materials.pdf.contracts import MAX_BODY, MAX_BYTES
from app.modules.reading_materials.pdf.schemas import (
    ExtractRequest,
    RunDetail,
    RunSummary,
    SourceSummary,
    UploadMetadata,
    UploadResult,
)
from app.modules.reading_materials.pdf.storage import LocalStorage
from app.modules.reading_materials.schemas import ArchiveRequest, Page

router = APIRouter()
BASE = "/learners/{learner_id}/reading-materials"
SOURCES = BASE + "/pdf-sources"
RUNS = SOURCES + "/{source_id}/extraction-runs"
Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=100)]
EMPTY = ExtractRequest()


def storage(settings: RuntimeSettings) -> LocalStorage:
    try:
        return LocalStorage(settings.pdf_storage_root)
    except (ValueError, OSError) as exc:
        raise service.error(503, "service_unavailable") from exc


def private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def bad(status: int, code: str) -> SecurityError:
    return SecurityError(status, code, "Invalid upload")


@router.post(
    BASE + "/pdf",
    response_model=UploadResult,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title", "language_tag", "upload_request_id", "file"],
                        "properties": {
                            "title": {"type": "string", "minLength": 1, "maxLength": 200},
                            "language_tag": {"type": "string", "enum": ["en"]},
                            "upload_request_id": {"type": "string", "format": "uuid"},
                            "file": {"type": "string", "format": "binary"},
                        },
                    },
                    "encoding": {"file": {"contentType": "application/pdf"}},
                }
            },
        }
    },
)
async def upload(
    learner_id: UUID,
    request: Request,
    principal: Authenticated,
    db: Database,
    settings: RuntimeSettings,
    response: Response,
) -> UploadResult:
    private(response)
    # No FastAPI Form/File dependency: authorization must precede body reception/parsing.
    await run_in_threadpool(
        authorize_learner_action, db, principal, learner_id, LearnerAction.UPLOAD_PDF
    )
    await run_in_threadpool(db.rollback)
    if (
        request.headers.get("content-encoding", "identity").lower() != "identity"
        or request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "multipart/form-data"
    ):
        raise bad(415, "unsupported_media_type")
    if "content-length" in request.headers:
        try:
            length = int(request.headers["content-length"])
            if length < 0:
                raise ValueError
        except ValueError as exc:
            raise bad(422, "validation_error") from exc
        if length > MAX_BODY:
            raise bad(413, "payload_too_large")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY:
            raise bad(413, "payload_too_large")
        body.extend(chunk)

    async def receive() -> Message:
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    bounded = Request(request.scope, receive)
    try:
        async with bounded.form(max_files=1, max_fields=3, max_part_size=1024) as form:
            if len(form.multi_items()) != 4 or set(form) != {
                "file",
                "title",
                "language_tag",
                "upload_request_id",
            }:
                raise bad(422, "validation_error")
            file = form["file"]
            if not isinstance(file, UploadFile) or file.content_type != "application/pdf":
                raise bad(415, "unsupported_media_type")
            metadata = UploadMetadata.model_validate(
                {k: form[k] for k in ("title", "language_tag", "upload_request_id")}
            )
            data = await file.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES or len(body) - len(data) > MAX_BODY - MAX_BYTES:
                raise bad(413, "payload_too_large")
            if not data.startswith(b"%PDF-"):
                raise bad(415, "unsupported_media_type")
    except (ValidationError, HTTPException, ValueError) as exc:
        raise bad(422, "validation_error") from exc
    result, status = await run_in_threadpool(
        service.upload, db, principal, learner_id, metadata, data, storage(settings)
    )
    response.status_code = status
    return result


@router.get(SOURCES, response_model=Page[SourceSummary])
def sources(
    learner_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    cursor: Cursor = None,
    limit: Limit = 25,
) -> Page[SourceSummary]:
    private(response)
    return service.list_sources(db, principal, learner_id, cursor, limit)


@router.get(SOURCES + "/{source_id}", response_model=SourceSummary)
def source(
    learner_id: UUID, source_id: UUID, principal: Authenticated, db: Database, response: Response
) -> SourceSummary:
    private(response)
    return service.read_source(db, principal, learner_id, source_id)


@router.post(RUNS, response_model=RunDetail, status_code=201)
def extract(
    learner_id: UUID,
    source_id: UUID,
    principal: Authenticated,
    db: Database,
    settings: RuntimeSettings,
    response: Response,
    payload: Annotated[ExtractRequest, Body()] = EMPTY,
) -> RunDetail:
    private(response)
    work = service.claim(db, principal, learner_id, source_id, payload.row_version)
    result, status = service.finish(db, principal, learner_id, storage(settings), work)
    response.status_code = status
    return result


@router.get(RUNS, response_model=Page[RunSummary])
def runs(
    learner_id: UUID,
    source_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    cursor: Cursor = None,
    limit: Limit = 25,
) -> Page[RunSummary]:
    private(response)
    return service.list_runs(db, principal, learner_id, source_id, cursor, limit)


@router.get(RUNS + "/{run_id}", response_model=RunDetail)
def run(
    learner_id: UUID,
    source_id: UUID,
    run_id: UUID,
    principal: Authenticated,
    db: Database,
    response: Response,
    include_evidence: bool = False,
) -> RunDetail:
    private(response)
    return service.read_run(db, principal, learner_id, source_id, run_id, include_evidence)


@router.post(SOURCES + "/{source_id}/archive", response_model=SourceSummary)
def archive(
    learner_id: UUID,
    source_id: UUID,
    payload: ArchiveRequest,
    principal: Authenticated,
    db: Database,
    response: Response,
) -> SourceSummary:
    private(response)
    return service.archive(db, principal, learner_id, source_id, payload.row_version)
