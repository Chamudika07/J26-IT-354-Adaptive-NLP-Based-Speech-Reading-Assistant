"""Private, unregistered adapters for proposed Component 4 reporting endpoints.

An approved HTTP layer may eventually supply the shared request-scoped ``Session``
and authenticated ``Principal`` to these functions. It must also inject the learners
component's approved production consent callback with the existing signature::

    ConsentChecker = Callable[[Session, UUID, str], None]

The callback must raise a sanitized ``SecurityError`` when active consent for
``learning_support`` is absent. No production evaluator exists here. Omitting the
callback deliberately preserves the existing fail-closed service behavior.

This module defines no ``APIRouter`` and is not imported by the production router.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.learner_modelling import service
from app.modules.learner_modelling.api_contracts import (
    ReportingProjection,
    ReportingRequest,
)
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    LearnerProgressProjection,
)
from app.modules.learner_modelling.historical import (
    HistoricalDataIntegrityError,
    HistoricalQueryValidationError,
    HistoricalResultLimitExceeded,
    HistoricalSessionQuery,
)
from app.modules.learner_modelling.service import ConsentChecker

type _ReportingReader[ProjectionT: ReportingProjection] = Callable[..., ProjectionT]


def _read_learner_progress(
    db: Session,
    principal: Principal,
    request: ReportingRequest,
    *,
    consent_checker: ConsentChecker | None = None,
) -> LearnerProgressProjection:
    """Use the existing fixed self-service authorization and learner projection."""
    return _invoke_reporting_service(
        service.read_learner_progress,
        db,
        principal,
        _prepare_query(request),
        consent_checker,
    )


def _read_guardian_summary(
    db: Session,
    principal: Principal,
    request: ReportingRequest,
    *,
    consent_checker: ConsentChecker | None = None,
) -> GuardianSummaryProjection:
    """Use the existing fixed guardian authorization and minimized projection."""
    return _invoke_reporting_service(
        service.read_guardian_summary,
        db,
        principal,
        _prepare_query(request),
        consent_checker,
    )


def _read_educator_analytics(
    db: Session,
    principal: Principal,
    request: ReportingRequest,
    *,
    consent_checker: ConsentChecker | None = None,
) -> EducatorAnalyticsProjection:
    """Use the existing fixed educator authorization and detailed projection."""
    return _invoke_reporting_service(
        service.read_educator_analytics,
        db,
        principal,
        _prepare_query(request),
        consent_checker,
    )


def _prepare_query(request: ReportingRequest) -> HistoricalSessionQuery:
    """Defensively rebuild the trusted query and sanitize boundary failures."""
    try:
        return request.to_historical_query()
    except HistoricalQueryValidationError as exc:
        raise SecurityError(422, "validation_error", "Invalid request") from exc


def _invoke_reporting_service[ProjectionT: ReportingProjection](
    reader: _ReportingReader[ProjectionT],
    db: Session,
    principal: Principal,
    query: HistoricalSessionQuery,
    consent_checker: ConsentChecker | None,
) -> ProjectionT:
    """Preserve security denials and sanitize historical processing failures."""
    try:
        return reader(
            db,
            principal,
            query,
            consent_checker=consent_checker,
        )
    except SecurityError:
        # Authentication, fixed learner authorization, and consent decisions already
        # use stable public errors. Preserve their status and fail-closed semantics.
        raise
    except HistoricalQueryValidationError as exc:
        raise SecurityError(422, "validation_error", "Invalid request") from exc
    except (HistoricalResultLimitExceeded, HistoricalDataIntegrityError) as exc:
        raise SecurityError(503, "service_unavailable", "Service unavailable") from exc
