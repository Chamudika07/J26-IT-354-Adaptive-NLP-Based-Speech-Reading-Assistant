"""Authenticated Component 4 HTTP boundaries; consent remains deny-by-default.

No synthetic consent, demo data or AI provider is installed by this router.
"""

import os as _pp1_os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime, ValidationError

from app.core.exceptions import SecurityError
from app.modules.auth.dependencies import Authenticated, Database
from app.modules.learner_modelling import api_adapters, service
from app.modules.learner_modelling.api_contracts import ReportingRequest, SessionIngestReceipt
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    LearnerProgressProjection,
)
from app.modules.learner_modelling.historical import CANDIDATE_MAX_HISTORICAL_SESSIONS
from app.modules.learner_modelling.schemas import ReadingSessionIngest

router = APIRouter(
    responses={
        401: {"description": "Missing, invalid, expired or revoked authentication"},
        403: {"description": "Active learning-support consent is absent or not integrated"},
        404: {"description": "Learner or required role-specific relationship is unavailable"},
        503: {"description": "Database, consent evaluator or validated evidence unavailable"},
    }
)


def get_learning_support_consent_checker() -> service.ConsentChecker:
    """Closed integration seam until an approved public consent evaluator exists.

    Only tests override this dependency with a synthetic evaluator. Production
    integration must address consent withdrawal and transaction semantics first.
    """
    return service._fail_closed_consent_checker


Consent = Annotated[service.ConsentChecker, Depends(get_learning_support_consent_checker)]


def reporting_request(
    learner_id: UUID,
    start_at_utc: AwareDatetime,
    end_at_utc: AwareDatetime,
    session_limit: Annotated[int, Query(ge=1, le=CANDIDATE_MAX_HISTORICAL_SESSIONS)] = (
        CANDIDATE_MAX_HISTORICAL_SESSIONS
    ),
) -> ReportingRequest:
    """Bounded [start, end) query; clients cannot select an authorization policy."""
    try:
        return ReportingRequest(
            learner_id=learner_id,
            start_at_utc=start_at_utc,
            end_at_utc=end_at_utc,
            session_limit=session_limit,
        )
    except ValidationError as exc:
        raise SecurityError(422, "validation_error", "Invalid request") from exc


ReportQuery = Annotated[ReportingRequest, Depends(reporting_request)]


@router.get("/learners/{learner_id}/progress", response_model=LearnerProgressProjection)
def read_progress(
    principal: Authenticated, db: Database, query: ReportQuery, consent: Consent, response: Response
) -> LearnerProgressProjection:
    response.headers["Cache-Control"] = "no-store"
    return api_adapters._read_learner_progress(db, principal, query, consent_checker=consent)


@router.get("/learners/{learner_id}/guardian-summary", response_model=GuardianSummaryProjection)
def read_guardian_summary(
    principal: Authenticated, db: Database, query: ReportQuery, consent: Consent, response: Response
) -> GuardianSummaryProjection:
    response.headers["Cache-Control"] = "no-store"
    return api_adapters._read_guardian_summary(db, principal, query, consent_checker=consent)


@router.get("/learners/{learner_id}/educator-analytics", response_model=EducatorAnalyticsProjection)
def read_educator_analytics(
    principal: Authenticated, db: Database, query: ReportQuery, consent: Consent, response: Response
) -> EducatorAnalyticsProjection:
    response.headers["Cache-Control"] = "no-store"
    return api_adapters._read_educator_analytics(db, principal, query, consent_checker=consent)


@router.post(
    "/reading-sessions",
    response_model=SessionIngestReceipt,
    status_code=201,
    responses={
        200: {"model": SessionIngestReceipt, "description": "Identical session already stored"}
    },
)
def ingest_session(
    payload: ReadingSessionIngest,
    principal: Authenticated,
    db: Database,
    consent: Consent,
    response: Response,
) -> SessionIngestReceipt:
    """Exact retries return 200; new records return 201. Never return a raw ORM row."""
    response.headers["Cache-Control"] = "no-store"
    row, created = service.ingest_reading_session(db, principal, payload, consent_checker=consent)
    receipt = SessionIngestReceipt(
        id=row.id, client_session_id=row.client_session_id, created=created
    )
    db.commit()
    response.status_code = 201 if created else 200
    return receipt


# Separate fictional-resource boundary; production route policies above are unchanged.

if _pp1_os.getenv("APP_ENV") == "development" and _pp1_os.getenv("READBUDDY_PP1_ENABLED") == "1":
    from app.modules.learner_modelling import pp1_saved as _pp1_saved  # noqa: F401
    from app.modules.learner_modelling.pp1_demo import router as _pp1_router

    router.include_router(_pp1_router)
