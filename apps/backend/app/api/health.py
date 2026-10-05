"""Infrastructure probes; responses never expose database details."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_session

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "ready"]


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness: the API can respond, independently of database availability."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
def readiness(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    """Readiness: the configured PostgreSQL database accepts a simple query."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return HealthResponse(status="ready")
