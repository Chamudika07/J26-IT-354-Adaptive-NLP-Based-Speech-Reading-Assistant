"""Append-only fixed fictional PP1 sessions; no production ingestion or consent changes."""

import json
import os
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.contracts import Principal
from app.modules.auth.dependencies import Authenticated, Database, RuntimeSettings
from app.modules.learner_modelling.demo_calculation import (
    DemoContext,
    SampleFile,
    build_connected_preview,
)
from app.modules.learner_modelling.longitudinal import LongitudinalWindow
from app.modules.learner_modelling.pp1_demo import (
    APPROVED_DIGEST,
    DemoResult,
    authorize,
    dataset_digest,
    load_dataset,
    router,
)
from app.modules.learner_modelling.pp1_models import Pp1SavedSession


class SaveReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    synthetic: Literal[True] = True
    sourceDigest: str = APPROVED_DIGEST
    savedSessionCount: int = Field(ge=0, le=6)
    createdSessionCount: int = Field(ge=0, le=6)


def check_access(principal: Principal, settings: Settings, db: Session, request: Request) -> None:
    authorize(
        settings.app_env,
        os.getenv("READBUDDY_PP1_ENABLED"),
        os.getenv("READBUDDY_PP1_ACCOUNT_IDS", ""),
        principal.user_id,
        principal.roles,
        principal.status,
    )
    if request.url.scheme != "https":
        raise HTTPException(403, "HTTPS required")
    try:
        identity = db.execute(
            text(
                "SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()"
            )
        ).one()
    except SQLAlchemyError:
        raise HTTPException(503, "PP1 storage unavailable") from None
    if tuple(identity) != (
        "readbuddy_component4_pp1_demo",
        "readbuddy_c4_pp1_runtime",
        "127.0.0.1",
        5432,
    ):
        raise HTTPException(403, "Isolated PP1 runtime required")
    if request.query_params:
        raise HTTPException(422, "Unexpected parameters")


def read_saved(db: Session, account: UUID) -> DemoResult:
    raw, digest = load_dataset(db)
    if dataset_digest(raw) != APPROVED_DIGEST or digest != APPROVED_DIGEST:
        raise ValueError("Unapproved source")
    approved = sorted(
        SampleFile.model_validate_json(raw).records, key=lambda r: (r.start, str(r.id))
    )
    rows = (
        db.execute(
            select(Pp1SavedSession)
            .where(Pp1SavedSession.account_id == account)
            .order_by(Pp1SavedSession.sequence)
        )
        .scalars()
        .all()
    )
    for index, row in enumerate(rows):
        if (
            index >= 6
            or row.sequence != index + 1
            or row.fixture_version != 1
            or row.source_digest != digest
            or row.sample_session_id != approved[index].id
            or row.measurements != approved[index].model_dump(mode="json")
        ):
            raise ValueError("Saved sample mismatch")
    samples = SampleFile.model_validate_json(
        json.dumps(
            dict(
                version=2,
                synthetic=True,
                verifiedTelemetry=False,
                records=[r.measurements for r in rows],
            )
        )
    )
    now = datetime.now(UTC)
    view = build_connected_preview(
        samples.model_dump_json(),
        LongitudinalWindow(
            start_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
            end_at_utc=datetime(2026, 1, 31, tzinfo=UTC),
        ),
        DemoContext(task="independent_reading", tier="intermediate", mode="adaptive"),
        generated_at=now,
    )
    return DemoResult(
        sourceDigest=digest, selectedSessionCount=len(rows), generatedAt=now, result=view
    )


def save_prefix(db: Session, account: UUID, count: int) -> SaveReceipt:
    if type(count) is not int or not 0 <= count <= 6:
        raise ValueError("Invalid prefix")
    before = read_saved(db, account)
    raw, _ = load_dataset(db)
    records = sorted(
        SampleFile.model_validate_json(raw).records, key=lambda r: (r.start, str(r.id))
    )
    created = 0
    for index, record in enumerate(records[:count], start=1):
        result = db.execute(
            insert(Pp1SavedSession)
            .values(
                id=uuid4(),
                account_id=account,
                sequence=index,
                sample_session_id=record.id,
                fixture_version=1,
                source_digest=APPROVED_DIGEST,
                measurements=record.model_dump(mode="json"),
            )
            .on_conflict_do_nothing()
            .returning(Pp1SavedSession.id)
        ).scalar_one_or_none()
        created += int(result is not None)
    after = read_saved(db, account)
    if after.selectedSessionCount < max(count, before.selectedSessionCount):
        raise ValueError("Save not confirmed")
    return SaveReceipt(savedSessionCount=after.selectedSessionCount, createdSessionCount=created)


@router.get("/pp1-demo/saved-progress", response_model=DemoResult)
def get_saved(
    principal: Authenticated,
    db: Database,
    settings: RuntimeSettings,
    request: Request,
    response: Response,
) -> DemoResult:
    check_access(principal, settings, db, request)
    response.headers["Cache-Control"] = "no-store"
    try:
        return read_saved(db, principal.user_id)
    except Exception:
        raise HTTPException(503, "Saved samples unavailable") from None


@router.post("/pp1-demo/saved-progress/{count}", response_model=SaveReceipt)
async def post_saved(
    count: int,
    principal: Authenticated,
    db: Database,
    settings: RuntimeSettings,
    request: Request,
    response: Response,
) -> SaveReceipt:
    check_access(principal, settings, db, request)
    if not 0 <= count <= 6:
        raise HTTPException(422, "Choose a fixed sample; measurements are not accepted")
    async for chunk in request.stream():
        if chunk:
            raise HTTPException(422, "Measurements are not accepted; choose a fixed sample")
    response.headers["Cache-Control"] = "no-store"
    try:
        receipt = save_prefix(db, principal.user_id, count)
        db.commit()
        return receipt
    except Exception:
        db.rollback()
        raise HTTPException(503, "Save not confirmed; retry the same sample safely") from None
