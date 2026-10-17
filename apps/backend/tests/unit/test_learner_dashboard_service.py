"""Synthetic tests for private fail-closed dashboard service orchestration."""

from __future__ import annotations

import ast
import inspect
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import app.modules.learner_modelling.service as service
from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.learner_modelling import repository as repository_module
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    LearnerProgressProjection,
    project_educator_analytics,
    project_guardian_summary,
    project_learner_progress,
)
from app.modules.learner_modelling.historical import (
    HistoricalDataIntegrityError,
    HistoricalResultLimitExceeded,
    HistoricalSessionQuery,
    HistoricalSessionRecord,
)
from app.modules.learner_modelling.models import ReadingSession
from app.modules.learners.service import LearnerAction, LearnerAuthorization

DashboardReader = Callable[..., Any]
_service_internals: Any = service


def _utc(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 4, day, hour, tzinfo=UTC)


def _principal(*roles: str, user_id: UUID | None = None) -> Principal:
    now = _utc(1)
    return Principal(
        user_id=user_id or uuid4(),
        login_handle="synthetic-user",
        roles=frozenset(roles or ("learner",)),
        session_id=uuid4(),
        authenticated_at=now,
        token_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _query(
    learner_id: UUID | None = None,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> HistoricalSessionQuery:
    return HistoricalSessionQuery(
        learner_id=learner_id or uuid4(),
        start_at_utc=start or _utc(1, 0),
        end_at_utc=end or _utc(30, 0),
        session_limit=25,
    )


def _grant(
    principal: Principal,
    query: HistoricalSessionQuery,
    action: LearnerAction,
    access_path: service.DashboardAccessPath,
    **changes: Any,
) -> LearnerAuthorization:
    values: dict[str, object] = {
        "actor_id": principal.user_id,
        "learner_id": query.learner_id,
        "action": action,
        "access_path": access_path,
        "basic_profile_fields": frozenset(),
        "consent_evaluated": False,
    }
    values.update(changes)
    return LearnerAuthorization(**values)  # type: ignore[arg-type]


def _record(
    *,
    session_id: UUID | None = None,
    words_attempted: int = 100,
    words_correct: int = 80,
    active_duration_ms: int = 60000,
    total_duration_ms: int = 70000,
    hesitation_count: int | None = 8,
    total_pause_duration_ms: int | None = 10000,
) -> HistoricalSessionRecord:
    return HistoricalSessionRecord(
        id=session_id or uuid4(),
        session_start_time=_utc(5),
        task_type="independent_reading",
        difficulty_tier="intermediate",
        support_mode="adaptive",
        completion_status="completed",
        words_attempted=words_attempted,
        words_correct=words_correct,
        target_word_count=words_attempted,
        active_duration_ms=active_duration_ms,
        total_duration_ms=total_duration_ms,
        hesitation_count=hesitation_count,
        total_pause_duration_ms=total_pause_duration_ms,
    )


def _db() -> MagicMock:
    return MagicMock(spec=Session)


def _allow(
    monkeypatch: pytest.MonkeyPatch,
    principal: Principal,
    query: HistoricalSessionQuery,
    action: LearnerAction,
    access_path: service.DashboardAccessPath,
    records: tuple[HistoricalSessionRecord, ...] = (),
) -> tuple[MagicMock, MagicMock]:
    authorize = MagicMock(return_value=_grant(principal, query, action, access_path))
    history = MagicMock(return_value=records)
    monkeypatch.setattr(service, "authorize_learner_action", authorize)
    monkeypatch.setattr(repository_module, "get_bounded_learner_session_history", history)
    return authorize, history


@pytest.mark.parametrize(
    ("reader", "roles", "action", "access_path", "projection_type"),
    [
        (
            service.read_learner_progress,
            ("learner",),
            LearnerAction.READ_EDUCATIONAL_SUMMARY,
            "self",
            LearnerProgressProjection,
        ),
        (
            service.read_guardian_summary,
            ("guardian",),
            LearnerAction.READ_GUARDIAN_SUMMARY,
            "guardian",
            GuardianSummaryProjection,
        ),
        (
            service.read_educator_analytics,
            ("educator",),
            LearnerAction.READ_EDUCATIONAL_SUMMARY,
            "educator",
            EducatorAnalyticsProjection,
        ),
    ],
)
def test_fixed_access_paths_return_exact_empty_projection_types(
    monkeypatch: pytest.MonkeyPatch,
    reader: DashboardReader,
    roles: tuple[str, ...],
    action: LearnerAction,
    access_path: service.DashboardAccessPath,
    projection_type: type[object],
) -> None:
    db = _db()
    principal = _principal(*roles)
    query = _query()
    authorize, history = _allow(monkeypatch, principal, query, action, access_path)
    consent = MagicMock()

    result: Any = reader(db, principal, query, consent_checker=consent)

    assert result.included_session_count == 0
    assert type(result) is projection_type
    authorize.assert_called_once_with(db, principal, query.learner_id, action)
    consent.assert_called_once_with(db, query.learner_id, "learning_support")
    history.assert_called_once_with(db, query)


def test_multi_role_principal_cannot_select_educator_projection_from_self_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _db()
    principal = _principal("learner", "educator")
    query = _query()
    monkeypatch.setattr(
        service,
        "authorize_learner_action",
        MagicMock(
            return_value=_grant(
                principal,
                query,
                LearnerAction.READ_EDUCATIONAL_SUMMARY,
                "self",
            )
        ),
    )
    consent = MagicMock()
    history = MagicMock()
    monkeypatch.setattr(repository_module, "get_bounded_learner_session_history", history)

    with pytest.raises(SecurityError) as exc_info:
        service.read_educator_analytics(db, principal, query, consent_checker=consent)

    assert (exc_info.value.status, exc_info.value.code) == (404, "not_found")
    consent.assert_not_called()
    history.assert_not_called()


def test_missing_principal_fails_authentication_before_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorize = MagicMock()
    monkeypatch.setattr(service, "authorize_learner_action", authorize)

    with pytest.raises(SecurityError) as exc_info:
        service.read_learner_progress(
            _db(),
            None,  # type: ignore[arg-type]
            _query(),
            consent_checker=MagicMock(),
        )

    assert (exc_info.value.status, exc_info.value.code) == (401, "authentication_required")
    authorize.assert_not_called()


def test_revoked_or_unrelated_authorization_stops_before_consent_and_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal("guardian")
    query = _query()
    denied = SecurityError(404, "not_found", "Resource not found")
    monkeypatch.setattr(service, "authorize_learner_action", MagicMock(side_effect=denied))
    consent = MagicMock()
    history = MagicMock()
    monkeypatch.setattr(repository_module, "get_bounded_learner_session_history", history)

    with pytest.raises(SecurityError) as exc_info:
        service.read_guardian_summary(_db(), principal, query, consent_checker=consent)

    assert exc_info.value is denied
    consent.assert_not_called()
    history.assert_not_called()


@pytest.mark.parametrize("mismatch", ["actor", "learner", "action", "access_path", "consent"])
def test_mismatched_authorization_grant_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    principal = _principal("learner")
    query = _query()
    grant = _grant(
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "self",
    )
    if mismatch == "actor":
        grant = replace(grant, actor_id=uuid4())
    elif mismatch == "learner":
        grant = replace(grant, learner_id=uuid4())
    elif mismatch == "action":
        grant = replace(grant, action=LearnerAction.READ_GUARDIAN_SUMMARY)
    elif mismatch == "access_path":
        grant = replace(grant, access_path="educator")
    else:
        grant = replace(grant, consent_evaluated=True)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "authorize_learner_action", MagicMock(return_value=grant))
    consent = MagicMock()
    history = MagicMock()
    monkeypatch.setattr(repository_module, "get_bounded_learner_session_history", history)

    with pytest.raises(SecurityError) as exc_info:
        service.read_learner_progress(_db(), principal, query, consent_checker=consent)

    assert str(exc_info.value) == "Resource not found"
    consent.assert_not_called()
    history.assert_not_called()


def test_missing_consent_checker_uses_existing_fail_closed_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal("learner")
    query = _query()
    _, history = _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "self",
    )

    with pytest.raises(SecurityError) as exc_info:
        service.read_learner_progress(_db(), principal, query)

    assert (exc_info.value.status, exc_info.value.code) == (403, "consent_required")
    assert str(query.learner_id) not in str(exc_info.value)
    history.assert_not_called()


@pytest.mark.parametrize("code", ["consent_denied", "consent_withdrawn"])
def test_explicit_consent_denial_or_withdrawal_stops_history(
    monkeypatch: pytest.MonkeyPatch,
    code: str,
) -> None:
    principal = _principal("guardian")
    query = _query()
    _, history = _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_GUARDIAN_SUMMARY,
        "guardian",
    )
    denial = SecurityError(403, code, "Consent is not active")
    consent = MagicMock(side_effect=denial)

    with pytest.raises(SecurityError) as exc_info:
        service.read_guardian_summary(_db(), principal, query, consent_checker=consent)

    assert exc_info.value is denial
    history.assert_not_called()


def test_unexpected_consent_checker_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal("educator")
    query = _query()
    _, history = _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "educator",
    )
    consent = MagicMock(side_effect=RuntimeError(f"sensitive-{query.learner_id}"))

    with pytest.raises(SecurityError) as exc_info:
        service.read_educator_analytics(_db(), principal, query, consent_checker=consent)

    assert (exc_info.value.status, exc_info.value.code, str(exc_info.value)) == (
        503,
        "service_unavailable",
        "Service unavailable",
    )
    assert str(query.learner_id) not in str(exc_info.value)
    history.assert_not_called()


def test_pipeline_order_is_authorize_consent_history_map_analytics_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    principal = _principal("learner")
    query = _query()
    record = _record()
    original_mapper = _service_internals.historical_records_to_observations
    original_analytics = _service_internals.calculate_longitudinal_progress
    original_projector = project_learner_progress

    def authorize(*_args: object) -> LearnerAuthorization:
        events.append("authorize")
        return _grant(principal, query, LearnerAction.READ_EDUCATIONAL_SUMMARY, "self")

    def consent(*_args: object) -> None:
        events.append("consent")

    def history(*_args: object) -> tuple[HistoricalSessionRecord, ...]:
        events.append("history")
        return (record,)

    def mapper(records: tuple[HistoricalSessionRecord, ...]) -> object:
        events.append("map")
        return original_mapper(records)

    def analytics(observations: object, window: object) -> object:
        events.append("analytics")
        return original_analytics(observations, window)

    def projector(report: object) -> LearnerProgressProjection:
        events.append("project")
        return original_projector(report)  # type: ignore[arg-type]

    monkeypatch.setattr(service, "authorize_learner_action", authorize)
    monkeypatch.setattr(repository_module, "get_bounded_learner_session_history", history)
    monkeypatch.setattr(service, "historical_records_to_observations", mapper)
    monkeypatch.setattr(service, "calculate_longitudinal_progress", analytics)
    monkeypatch.setattr(
        service,
        "_LEARNER_DASHBOARD_POLICY",
        replace(service._LEARNER_DASHBOARD_POLICY, projector=projector),
    )

    service.read_learner_progress(_db(), principal, query, consent_checker=consent)

    assert events == ["authorize", "consent", "history", "map", "analytics", "project"]


def test_historical_overflow_stops_before_mapping_or_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal("learner")
    query = _query()
    _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "self",
    )
    overflow = HistoricalResultLimitExceeded("Historical result exceeds limit")
    monkeypatch.setattr(
        repository_module,
        "get_bounded_learner_session_history",
        MagicMock(side_effect=overflow),
    )
    mapper = MagicMock()
    monkeypatch.setattr(service, "historical_records_to_observations", mapper)

    with pytest.raises(HistoricalResultLimitExceeded) as exc_info:
        service.read_learner_progress(_db(), principal, query, consent_checker=lambda *_args: None)

    assert exc_info.value is overflow
    mapper.assert_not_called()


def test_invalid_persisted_telemetry_stops_before_analytics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal("learner")
    query = _query()
    invalid = _record(words_attempted=5, words_correct=6)
    _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "self",
        (invalid,),
    )
    analytics = MagicMock()
    monkeypatch.setattr(service, "calculate_longitudinal_progress", analytics)

    with pytest.raises(HistoricalDataIntegrityError):
        service.read_learner_progress(_db(), principal, query, consent_checker=lambda *_args: None)

    analytics.assert_not_called()


def test_database_exception_is_preserved_for_existing_sanitized_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal("educator")
    query = _query()
    _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "educator",
    )
    failure = SQLAlchemyError("synthetic database failure")
    monkeypatch.setattr(
        repository_module,
        "get_bounded_learner_session_history",
        MagicMock(side_effect=failure),
    )

    with pytest.raises(SQLAlchemyError) as exc_info:
        service.read_educator_analytics(
            _db(), principal, query, consent_checker=lambda *_args: None
        )

    assert exc_info.value is failure


def test_fixed_policies_select_exactly_one_projector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {
        "learner": MagicMock(side_effect=project_learner_progress),
        "guardian": MagicMock(side_effect=project_guardian_summary),
        "educator": MagicMock(side_effect=project_educator_analytics),
    }
    monkeypatch.setattr(
        service,
        "_LEARNER_DASHBOARD_POLICY",
        replace(service._LEARNER_DASHBOARD_POLICY, projector=calls["learner"]),
    )
    monkeypatch.setattr(
        service,
        "_GUARDIAN_DASHBOARD_POLICY",
        replace(service._GUARDIAN_DASHBOARD_POLICY, projector=calls["guardian"]),
    )
    monkeypatch.setattr(
        service,
        "_EDUCATOR_DASHBOARD_POLICY",
        replace(service._EDUCATOR_DASHBOARD_POLICY, projector=calls["educator"]),
    )

    cases: tuple[tuple[DashboardReader, str, LearnerAction, service.DashboardAccessPath], ...] = (
        (
            service.read_learner_progress,
            "learner",
            LearnerAction.READ_EDUCATIONAL_SUMMARY,
            "self",
        ),
        (
            service.read_guardian_summary,
            "guardian",
            LearnerAction.READ_GUARDIAN_SUMMARY,
            "guardian",
        ),
        (
            service.read_educator_analytics,
            "educator",
            LearnerAction.READ_EDUCATIONAL_SUMMARY,
            "educator",
        ),
    )
    for reader, name, action, access_path in cases:
        principal = _principal(name)
        query = _query()
        monkeypatch.setattr(
            service,
            "authorize_learner_action",
            MagicMock(return_value=_grant(principal, query, action, access_path)),
        )
        monkeypatch.setattr(
            repository_module,
            "get_bounded_learner_session_history",
            MagicMock(return_value=()),
        )
        before = {key: mock.call_count for key, mock in calls.items()}

        reader(_db(), principal, query, consent_checker=lambda *_args: None)

        assert calls[name].call_count == before[name] + 1
        assert all(calls[key].call_count == before[key] for key in calls if key != name)


def test_normalized_query_window_is_reused_by_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    offset = timezone(timedelta(hours=5, minutes=30))
    principal = _principal("learner")
    query = _query(
        start=datetime(2026, 4, 1, 5, 30, tzinfo=offset),
        end=datetime(2026, 4, 2, 5, 30, tzinfo=offset),
    )
    _, history = _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "self",
    )

    result = service.read_learner_progress(
        _db(), principal, query, consent_checker=lambda *_args: None
    )

    assert query.start_at_utc == datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    assert query.end_at_utc == datetime(2026, 4, 2, 0, 0, tzinfo=UTC)
    assert result.reporting_period.start_at_utc == query.start_at_utc
    assert result.reporting_period.end_at_utc == query.end_at_utc
    history.assert_called_once()


def test_missing_metrics_remain_missing_in_returned_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal("learner")
    query = _query()
    record = _record(
        words_attempted=0,
        words_correct=0,
        active_duration_ms=0,
        total_duration_ms=0,
        hesitation_count=None,
        total_pause_duration_ms=None,
    )
    _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "self",
        (record,),
    )

    result = service.read_learner_progress(
        _db(), principal, query, consent_checker=lambda *_args: None
    )

    assert result.included_session_count == 1
    assert all(metric.first_value is None for metric in result.contexts[0].metrics)
    assert all(metric.latest_value is None for metric in result.contexts[0].metrics)
    assert all(metric.evidence_state == "no_observations" for metric in result.contexts[0].metrics)


@pytest.mark.parametrize(
    ("reader", "role", "action", "access_path"),
    [
        (
            service.read_learner_progress,
            "learner",
            LearnerAction.READ_EDUCATIONAL_SUMMARY,
            "self",
        ),
        (
            service.read_guardian_summary,
            "guardian",
            LearnerAction.READ_GUARDIAN_SUMMARY,
            "guardian",
        ),
        (
            service.read_educator_analytics,
            "educator",
            LearnerAction.READ_EDUCATIONAL_SUMMARY,
            "educator",
        ),
    ],
)
def test_returned_projection_contains_no_learner_or_session_identifier(
    monkeypatch: pytest.MonkeyPatch,
    reader: DashboardReader,
    role: str,
    action: LearnerAction,
    access_path: service.DashboardAccessPath,
) -> None:
    learner_id = UUID("10000000-0000-0000-0000-000000000001")
    session_id = UUID("20000000-0000-0000-0000-000000000002")
    principal = _principal(role)
    query = _query(learner_id)
    _allow(monkeypatch, principal, query, action, access_path, (_record(session_id=session_id),))

    result = reader(_db(), principal, query, consent_checker=lambda *_args: None)
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)

    assert str(learner_id) not in serialized
    assert str(session_id) not in serialized
    assert "learner_id" not in serialized
    assert "session_id" not in serialized


def test_read_orchestration_does_not_control_caller_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _db()
    principal = _principal("learner")
    query = _query()
    _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        "self",
    )

    service.read_learner_progress(db, principal, query, consent_checker=lambda *_args: None)

    db.commit.assert_not_called()
    db.flush.assert_not_called()
    db.rollback.assert_not_called()


def test_service_adds_no_http_network_or_consent_table_access() -> None:
    source = inspect.getsource(service)
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}

    forbidden = ("fastapi", "requests", "httpx", "socket", "urllib")
    assert not any(name.startswith(forbidden) for name in imported)
    assert "consent_records" not in source
    assert "ConsentRecord" not in source


def test_existing_ingestion_contract_remains_available() -> None:
    signature = inspect.signature(service.ingest_reading_session)

    assert tuple(signature.parameters) == ("db", "principal", "payload", "consent_checker")
    assert signature.parameters["consent_checker"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.return_annotation == tuple[ReadingSession, bool]


def test_identical_synthetic_evidence_produces_deterministic_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal("guardian")
    query = _query()
    records = (
        _record(session_id=UUID("30000000-0000-0000-0000-000000000003")),
        replace(
            _record(session_id=UUID("40000000-0000-0000-0000-000000000004")),
            session_start_time=_utc(6),
            words_correct=90,
        ),
    )
    _allow(
        monkeypatch,
        principal,
        query,
        LearnerAction.READ_GUARDIAN_SUMMARY,
        "guardian",
        records,
    )

    first = service.read_guardian_summary(
        _db(), principal, query, consent_checker=lambda *_args: None
    )
    second = service.read_guardian_summary(
        _db(), principal, query, consent_checker=lambda *_args: None
    )

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
