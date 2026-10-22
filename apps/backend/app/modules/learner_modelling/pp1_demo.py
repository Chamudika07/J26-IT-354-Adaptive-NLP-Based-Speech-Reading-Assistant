"""Learner-only PP1 resource. Never invokes production ingestion or consent overrides."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.auth.dependencies import Authenticated, Database, RuntimeSettings
from app.modules.learner_modelling.demo_calculation import (
    ConnectedPreview,
    DemoContext,
    SampleFile,
    build_connected_preview,
)
from app.modules.learner_modelling.longitudinal import LongitudinalWindow

FIXTURE = Path(__file__).with_name("pp1_fixture.json")
APPROVED_DIGEST = "33659d1c6947d7687a7d74e00f4540da065a2450b357805c90566ec71fda0ad7"


class DemoResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["pp1-demo-result-v1"] = "pp1-demo-result-v1"
    synthetic: Literal[True] = True
    verifiedTelemetry: Literal[False] = False
    source: Literal["postgresql-backed-python"] = "postgresql-backed-python"
    datasetKey: Literal["pp1-six-session-journey"] = "pp1-six-session-journey"
    fixtureVersion: Literal[1] = 1
    sourceDigest: str
    selectedSessionCount: int
    role: Literal["learner"] = "learner"
    generatedAt: AwareDatetime
    result: ConnectedPreview


def dataset_digest(raw: str) -> str:
    sample = SampleFile.model_validate_json(raw)
    if len(sample.records) != 6:
        raise ValueError("Expected six fictional sessions")
    return hashlib.sha256(sample.model_dump_json().encode()).hexdigest()


def calculate(raw: str, digest: str, count: int) -> DemoResult:
    if not 0 <= count <= 6 or isinstance(count, bool):
        raise ValueError("Invalid prefix")
    if dataset_digest(raw) != digest or digest != APPROVED_DIGEST:
        raise ValueError("Unapproved dataset")
    sample = SampleFile.model_validate_json(raw)
    records = sorted(sample.records, key=lambda row: (row.start, str(row.id)))
    selected = sample.model_copy(update={"records": tuple(records[:count])})
    now = datetime.now(UTC)
    result = build_connected_preview(
        selected.model_dump_json(),
        LongitudinalWindow(
            start_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
            end_at_utc=datetime(2026, 1, 31, tzinfo=UTC),
        ),
        DemoContext(task="independent_reading", tier="intermediate", mode="adaptive"),
        generated_at=now,
    )
    return DemoResult(
        sourceDigest=digest, selectedSessionCount=count, generatedAt=now, result=result
    )


def load_dataset(db: Session) -> tuple[str, str]:
    # Schema/migration deliberately pending team-history reconciliation. Read only.
    row = db.execute(
        text(
            "SELECT source_payload::text, source_digest FROM component4_pp1_demo_datasets "
            "WHERE dataset_key = 'pp1-six-session-journey' AND fixture_version = 1"
        )
    ).one()
    return str(row[0]), str(row[1])


def authorize(
    environment: str,
    enabled: str | None,
    allowed: str,
    user: UUID,
    roles: frozenset[str],
    status: str,
) -> None:
    if environment != "development" or enabled != "1":
        raise HTTPException(404, "Unavailable")
    try:
        accounts = {UUID(item.strip()) for item in allowed.split(",") if item.strip()}
    except ValueError:
        accounts = set()
    if user not in accounts or "learner" not in roles or status != "active":
        raise HTTPException(403, "Access denied")


router = APIRouter()


@router.get("/pp1-demo/scenarios/{count}", response_model=DemoResult)
def read_demo(
    count: int,
    principal: Authenticated,
    db: Database,
    settings: RuntimeSettings,
    request: Request,
    response: Response,
) -> DemoResult:
    import os

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
    if not 0 <= count <= 6 or request.query_params:
        raise HTTPException(422, "Invalid scenario")
    response.headers["Cache-Control"] = "no-store"
    try:
        raw, digest = load_dataset(db)
        return calculate(raw, digest, count)
    except Exception:
        raise HTTPException(503, "Sample results unavailable") from None
