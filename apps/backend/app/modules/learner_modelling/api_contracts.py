"""Bounded request and minimized response contracts for Component 4 APIs.

This module defines validation only. It has no router, dependency injection, database
access, authorization selection, or consent implementation. The existing 90-day and
1,000-row safety bounds are retained; production consent integration remains blocked.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.core.schemas import Schema
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    LearnerProgressProjection,
)
from app.modules.learner_modelling.historical import (
    CANDIDATE_MAX_HISTORICAL_SESSIONS,
    HistoricalQueryValidationError,
    HistoricalSessionQuery,
)


class ReportingRequest(Schema):
    """Learner-scoped, bounded values for a reporting request.

    No authorization action, access path, projection choice, or consent result is
    accepted from a client. Those policies remain fixed by the selected private
    adapter and the existing service implementation.
    """

    learner_id: UUID
    start_at_utc: AwareDatetime
    end_at_utc: AwareDatetime
    session_limit: Annotated[int, Field(ge=1, le=CANDIDATE_MAX_HISTORICAL_SESSIONS)] = (
        CANDIDATE_MAX_HISTORICAL_SESSIONS
    )

    @model_validator(mode="after")
    def validate_existing_history_bounds(self) -> ReportingRequest:
        """Reuse the historical contract as the single source of boundary rules."""
        try:
            query = self.to_historical_query()
        except HistoricalQueryValidationError as exc:
            raise ValueError("invalid reporting request") from exc

        self.start_at_utc = query.start_at_utc
        self.end_at_utc = query.end_at_utc
        return self

    def to_historical_query(self) -> HistoricalSessionQuery:
        """Create the existing UTC-normalized query without any database access."""
        return HistoricalSessionQuery(
            learner_id=self.learner_id,
            start_at_utc=self.start_at_utc,
            end_at_utc=self.end_at_utc,
            session_limit=self.session_limit,
        )


ReportingProjection = (
    LearnerProgressProjection | GuardianSummaryProjection | EducatorAnalyticsProjection
)


class SessionIngestReceipt(Schema):
    """Minimized ingestion acknowledgment, never an unrestricted session read."""

    id: UUID
    client_session_id: UUID
    created: bool
