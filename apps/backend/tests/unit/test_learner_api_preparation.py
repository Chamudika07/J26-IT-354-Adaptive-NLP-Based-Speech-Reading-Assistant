"""Unit tests for inactive Component 4 reporting API preparation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.learner_modelling import api_adapters, repository, service
from app.modules.learner_modelling.api_contracts import ReportingRequest
from app.modules.learner_modelling.historical import (
    HistoricalDataIntegrityError,
    HistoricalResultLimitExceeded,
)
from app.modules.learner_modelling.router import router
from app.modules.learners.service import LearnerAction, LearnerAuthorization


def _request(**changes: object) -> ReportingRequest:
    values: dict[str, object] = {
        "learner_id": uuid4(),
        "start_at_utc": datetime(2026, 1, 1, tzinfo=UTC),
        "end_at_utc": datetime(2026, 1, 31, tzinfo=UTC),
        "session_limit": 25,
    }
    values.update(changes)
    return ReportingRequest.model_validate(values)


def _principal() -> Principal:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return Principal(
        user_id=uuid4(),
        login_handle="synthetic-api-preparation-user",
        roles=frozenset({"learner"}),
        session_id=uuid4(),
        authenticated_at=now,
        token_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _authorization(
    principal: Principal,
    request: ReportingRequest,
    *,
    learner_id: UUID | None = None,
) -> LearnerAuthorization:
    return LearnerAuthorization(
        actor_id=principal.user_id,
        learner_id=learner_id or request.learner_id,
        action=LearnerAction.READ_EDUCATIONAL_SUMMARY,
        access_path="self",
        basic_profile_fields=frozenset(),
        consent_evaluated=False,
    )


def test_valid_aware_window_is_normalized_to_utc() -> None:
    colombo = timezone(timedelta(hours=5, minutes=30))
    request = _request(
        start_at_utc=datetime(2026, 1, 1, 5, 30, tzinfo=colombo),
        end_at_utc=datetime(2026, 1, 31, 5, 30, tzinfo=colombo),
    )

    query = request.to_historical_query()

    assert request.start_at_utc == datetime(2026, 1, 1, tzinfo=UTC)
    assert request.end_at_utc == datetime(2026, 1, 31, tzinfo=UTC)
    assert query.start_at_utc.tzinfo is UTC
    assert query.end_at_utc.tzinfo is UTC


@pytest.mark.parametrize("field", ["start_at_utc", "end_at_utc"])
def test_missing_timezone_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        _request(**{field: datetime(2026, 1, 1)})


def test_invalid_or_empty_interval_is_rejected() -> None:
    instant = datetime(2026, 1, 31, tzinfo=UTC)
    with pytest.raises(ValidationError):
        _request(start_at_utc=instant, end_at_utc=instant)
    with pytest.raises(ValidationError):
        _request(start_at_utc=instant, end_at_utc=instant - timedelta(seconds=1))


def test_candidate_maximum_window_and_session_limit_are_enforced() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    accepted = _request(
        start_at_utc=start, end_at_utc=start + timedelta(days=90), session_limit=1000
    )
    assert accepted.session_limit == 1000

    with pytest.raises(ValidationError):
        _request(start_at_utc=start, end_at_utc=start + timedelta(days=90, seconds=1))
    with pytest.raises(ValidationError):
        _request(session_limit=1001)


def test_invalid_learner_uuid_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _request(learner_id="not-a-learner-uuid")


def test_request_rejects_client_controlled_authorization_fields() -> None:
    assert set(ReportingRequest.model_fields) == {
        "learner_id",
        "start_at_utc",
        "end_at_utc",
        "session_limit",
    }
    with pytest.raises(ValidationError):
        _request(access_path="educator")
    with pytest.raises(ValidationError):
        _request(authorization_action="read_guardian_summary")


def test_pure_request_validation_does_not_access_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = MagicMock()
    monkeypatch.setattr(repository, "get_bounded_learner_session_history", history)

    request = _request()
    query = request.to_historical_query()

    assert query.learner_id == request.learner_id
    history.assert_not_called()


@pytest.mark.parametrize(
    ("failure", "expected_status", "expected_code", "expected_message"),
    [
        (
            HistoricalResultLimitExceeded("private row count and learner details"),
            503,
            "service_unavailable",
            "Service unavailable",
        ),
        (
            HistoricalDataIntegrityError("private persisted telemetry details"),
            503,
            "service_unavailable",
            "Service unavailable",
        ),
    ],
)
def test_historical_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    expected_status: int,
    expected_code: str,
    expected_message: str,
) -> None:
    monkeypatch.setattr(service, "read_learner_progress", MagicMock(side_effect=failure))

    with pytest.raises(SecurityError) as exc_info:
        api_adapters._read_learner_progress(
            MagicMock(spec=Session),
            _principal(),
            _request(),
            consent_checker=MagicMock(),
        )

    error = exc_info.value
    assert (error.status, error.code, error.message) == (
        expected_status,
        expected_code,
        expected_message,
    )
    assert "private" not in error.message


def test_defensive_invalid_window_mapping_is_sanitized_before_service_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    request = ReportingRequest.model_construct(
        learner_id=uuid4(),
        start_at_utc=instant,
        end_at_utc=instant,
        session_limit=25,
    )
    reader = MagicMock()
    monkeypatch.setattr(service, "read_learner_progress", reader)

    with pytest.raises(SecurityError) as exc_info:
        api_adapters._read_learner_progress(
            MagicMock(spec=Session),
            _principal(),
            request,
            consent_checker=MagicMock(),
        )

    error = exc_info.value
    assert (error.status, error.code, error.message) == (
        422,
        "validation_error",
        "Invalid request",
    )
    reader.assert_not_called()


def test_missing_consent_callback_preserves_existing_fail_closed_denial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    principal = _principal()
    history = MagicMock()
    monkeypatch.setattr(
        service,
        "authorize_learner_action",
        MagicMock(return_value=_authorization(principal, request)),
    )
    monkeypatch.setattr(repository, "get_bounded_learner_session_history", history)

    with pytest.raises(SecurityError) as exc_info:
        api_adapters._read_learner_progress(MagicMock(spec=Session), principal, request)

    error = exc_info.value
    assert (error.status, error.code) == (403, "consent_required")
    assert str(request.learner_id) not in error.message
    history.assert_not_called()


def test_invalid_authorization_remains_sanitized_and_precedes_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    principal = _principal()
    consent = MagicMock()
    monkeypatch.setattr(
        service,
        "authorize_learner_action",
        MagicMock(return_value=_authorization(principal, request, learner_id=uuid4())),
    )

    with pytest.raises(SecurityError) as exc_info:
        api_adapters._read_learner_progress(
            MagicMock(spec=Session),
            principal,
            request,
            consent_checker=consent,
        )

    error = exc_info.value
    assert (error.status, error.code, error.message) == (
        404,
        "not_found",
        "Resource not found",
    )
    assert str(request.learner_id) not in error.message
    consent.assert_not_called()


def test_inactive_adapters_are_not_exposed_as_routes() -> None:
    assert router.routes == []
    assert not hasattr(api_adapters, "router")
