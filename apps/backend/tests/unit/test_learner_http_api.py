"""HTTP contract tests with real C4 services and synthetic repository/auth boundaries.

No database fixtures, network providers or production consent decisions are used.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import authentication_required
from app.db.session import get_session
from app.modules.auth import dependencies
from app.modules.auth.contracts import Principal
from app.modules.learner_modelling import repository, service
from app.modules.learner_modelling.historical import (
    HistoricalDataIntegrityError,
    HistoricalResultLimitExceeded,
    HistoricalSessionRecord,
)
from app.modules.learner_modelling.router import get_learning_support_consent_checker
from app.modules.learners import repository as learner_repository

ROOT = "/api/v1/learner-modelling"
NOW = datetime(2026, 1, 5, tzinfo=UTC)
PARAMS = {"start_at_utc": "2026-01-01T00:00:00Z", "end_at_utc": "2026-02-01T00:00:00Z"}
PATHS = [
    ("learner", "progress"),
    ("guardian", "guardian-summary"),
    ("educator", "educator-analytics"),
]


@pytest.fixture
def boundary(application, monkeypatch):
    db = MagicMock(spec=Session)
    actor_id, learner_id = uuid4(), uuid4()
    principal = Principal(
        actor_id,
        "synthetic-http",
        frozenset({"learner"}),
        uuid4(),
        NOW,
        uuid4(),
        NOW,
        NOW + timedelta(hours=1),
    )
    profile = SimpleNamespace(learner_user_id=actor_id)
    monkeypatch.setattr(learner_repository, "accessible_profile", lambda *_args, **_kw: profile)
    guardian = MagicMock(return_value=None)
    educator = MagicMock(return_value=None)
    monkeypatch.setattr(learner_repository, "guardian_level", guardian)
    monkeypatch.setattr(learner_repository, "educator_level", educator)
    monkeypatch.setattr(learner_repository, "current_time", lambda *_: NOW)
    history = MagicMock(
        return_value=(
            HistoricalSessionRecord(
                id=uuid4(),
                session_start_time=NOW,
                task_type="independent_reading",
                difficulty_tier="intermediate",
                support_mode="adaptive",
                completion_status="completed",
                words_attempted=100,
                words_correct=90,
                target_word_count=100,
                active_duration_ms=60000,
                total_duration_ms=70000,
                hesitation_count=2,
                total_pause_duration_ms=None,
            ),
        )
    )
    monkeypatch.setattr(repository, "get_bounded_learner_session_history", history)
    application.dependency_overrides[get_session] = lambda: db
    state = SimpleNamespace(
        db=db,
        principal=principal,
        learner_id=learner_id,
        history=history,
        guardian=guardian,
        educator=educator,
        profile=profile,
        app=application,
    )
    with TestClient(application) as client:
        state.client = client
        yield state
    application.dependency_overrides.clear()


def allow_test_identity(boundary, role="learner", *, consent=True):
    from dataclasses import replace

    boundary.principal = replace(boundary.principal, roles=frozenset({role}))
    boundary.app.dependency_overrides[dependencies.get_current_principal] = lambda: (
        boundary.principal
    )
    if role == "guardian":
        boundary.guardian.return_value = "viewer"
    if role == "educator":
        boundary.educator.return_value = "viewer"
    if consent:
        boundary.app.dependency_overrides[get_learning_support_consent_checker] = lambda: (
            lambda *_: None
        )


def payload(boundary):
    return {
        "learner_id": str(boundary.learner_id),
        "client_session_id": str(uuid4()),
        "session_start_time": "2026-01-05T00:00:00Z",
        "session_end_time": "2026-01-05T00:02:00Z",
        "words_attempted": 100,
        "words_correct": 90,
        "target_word_count": 100,
        "active_duration_ms": 60000,
        "total_duration_ms": 70000,
    }


@pytest.mark.parametrize("role,suffix", PATHS)
def test_real_reporting_pipeline_returns_only_role_projection(boundary, role, suffix):
    allow_test_identity(boundary, role)
    response = boundary.client.get(f"{ROOT}/learners/{boundary.learner_id}/{suffix}", params=PARAMS)
    assert response.status_code == 200
    data = response.json()
    assert data["included_session_count"] == 1
    assert data["reporting_period"]["start_at_utc"] == "2026-01-01T00:00:00Z"
    assert response.headers["cache-control"] == "no-store"
    assert not {"learner_id", "request_digest", "engagement_score", "recommendation"} & data.keys()
    if role == "educator":
        assert "partitions" in data and "contexts" not in data
    else:
        assert "contexts" in data and "partitions" not in data
    query = boundary.history.call_args.args[1]
    assert query.learner_id == boundary.learner_id
    boundary.db.commit.assert_not_called()


@pytest.mark.parametrize("role,suffix", PATHS)
def test_default_missing_consent_denies_before_history(boundary, role, suffix):
    allow_test_identity(boundary, role, consent=False)
    response = boundary.client.get(f"{ROOT}/learners/{boundary.learner_id}/{suffix}", params=PARAMS)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "consent_required"
    boundary.history.assert_not_called()


@pytest.mark.parametrize("role,suffix", PATHS)
def test_wrong_learner_or_missing_relationship_fails_closed(boundary, role, suffix):
    allow_test_identity(boundary, role)
    boundary.profile.learner_user_id = uuid4()
    boundary.guardian.return_value = None
    boundary.educator.return_value = None
    response = boundary.client.get(f"{ROOT}/learners/{uuid4()}/{suffix}", params=PARAMS)
    assert response.status_code == 404
    boundary.history.assert_not_called()


@pytest.mark.parametrize("role,suffix", PATHS)
def test_learner_cannot_choose_another_projection(boundary, role, suffix):
    if role == "learner":
        allow_test_identity(boundary, "educator")
    else:
        allow_test_identity(boundary)
    response = boundary.client.get(f"{ROOT}/learners/{boundary.learner_id}/{suffix}", params=PARAMS)
    assert response.status_code == 404
    boundary.history.assert_not_called()


@pytest.mark.parametrize("suffix", [p[1] for p in PATHS] + ["ingest"])
def test_missing_bearer_is_401(boundary, suffix):
    if suffix == "ingest":
        response = boundary.client.post(f"{ROOT}/reading-sessions", json=payload(boundary))
    else:
        response = boundary.client.get(
            f"{ROOT}/learners/{boundary.learner_id}/{suffix}", params=PARAMS
        )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    boundary.history.assert_not_called()
    boundary.db.commit.assert_not_called()


def test_invalid_bearer_is_401(boundary, monkeypatch):
    def denied(*_args):
        raise authentication_required()

    monkeypatch.setattr(dependencies, "resolve_principal", denied)
    response = boundary.client.get(
        f"{ROOT}/learners/{boundary.learner_id}/progress",
        params=PARAMS,
        headers={"Authorization": "Bearer invalid"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"start_at_utc": "2026-01-01"},
        {"end_at_utc": "2025-12-31T00:00:00Z"},
        {"end_at_utc": "2027-01-01T00:00:00Z"},
        {"session_limit": 1001},
    ],
)
def test_invalid_reporting_bounds_are_sanitized(boundary, changes):
    allow_test_identity(boundary)
    response = boundary.client.get(
        f"{ROOT}/learners/{boundary.learner_id}/progress", params=PARAMS | changes
    )
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Invalid request"
    boundary.history.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        HistoricalDataIntegrityError("private"),
        HistoricalResultLimitExceeded("private"),
        SQLAlchemyError("private"),
    ],
)
def test_history_errors_are_sanitized(boundary, error):
    allow_test_identity(boundary)
    boundary.history.side_effect = error
    response = boundary.client.get(f"{ROOT}/learners/{boundary.learner_id}/progress", params=PARAMS)
    assert response.status_code == 503
    assert "private" not in response.text


def prepare_ingestion(boundary, monkeypatch):
    allow_test_identity(boundary)
    monkeypatch.setattr(service, "protect_principal_for_write", lambda _db, p: p)
    monkeypatch.setattr(service, "assert_protected_session_live", lambda *_: None)
    monkeypatch.setattr(
        repository, "insert_reading_session", lambda _db, row: setattr(row, "id", uuid4())
    )
    lookup = MagicMock(return_value=None)
    monkeypatch.setattr(repository, "get_session_by_client_id", lookup)
    return lookup


def test_ingest_and_exact_retry_return_minimal_receipts(boundary, monkeypatch):
    lookup = prepare_ingestion(boundary, monkeypatch)
    data = payload(boundary)
    response = boundary.client.post(f"{ROOT}/reading-sessions", json=data)
    assert response.status_code == 201
    assert set(response.json()) == {"id", "client_session_id", "created"}
    assert response.json()["created"] is True
    boundary.db.commit.assert_called_once()
    # Reuse the existing service's canonical identity check, not a mocked HTTP response.
    from app.modules.learner_modelling.schemas import (
        ReadingSessionIngest,
        compute_canonical_session_digest,
    )

    lookup.return_value = SimpleNamespace(
        id=response.json()["id"],
        client_session_id=data["client_session_id"],
        request_digest=compute_canonical_session_digest(ReadingSessionIngest.model_validate(data)),
    )
    retry = boundary.client.post(f"{ROOT}/reading-sessions", json=data)
    assert retry.status_code == 200
    assert retry.json() == response.json() | {"created": False}
    lookup.return_value.request_digest = "b" * 64
    conflict = boundary.client.post(f"{ROOT}/reading-sessions", json=data)
    assert conflict.status_code == 409
    assert boundary.db.commit.call_count == 2


def test_ingestion_requires_consent_and_does_not_commit(boundary, monkeypatch):
    prepare_ingestion(boundary, monkeypatch)
    boundary.app.dependency_overrides.pop(get_learning_support_consent_checker)
    response = boundary.client.post(f"{ROOT}/reading-sessions", json=payload(boundary))
    assert response.status_code == 403
    boundary.db.commit.assert_not_called()


def test_invalid_ingestion_is_rejected_without_write(boundary):
    allow_test_identity(boundary)
    data = payload(boundary) | {"words_correct": 101, "consent": True}
    response = boundary.client.post(f"{ROOT}/reading-sessions", json=data)
    assert response.status_code == 422
    boundary.db.commit.assert_not_called()
    boundary.db.add.assert_not_called()


def test_ingestion_denies_unrelated_learner_before_write(boundary, monkeypatch):
    prepare_ingestion(boundary, monkeypatch)
    boundary.profile.learner_user_id = uuid4()
    response = boundary.client.post(f"{ROOT}/reading-sessions", json=payload(boundary))
    assert response.status_code == 404
    boundary.db.commit.assert_not_called()
    boundary.db.add.assert_not_called()


def test_commit_failure_never_reports_success_or_database_details(boundary, monkeypatch):
    prepare_ingestion(boundary, monkeypatch)
    boundary.db.commit.side_effect = SQLAlchemyError("private SQL and connection details")
    response = boundary.client.post(f"{ROOT}/reading-sessions", json=payload(boundary))
    assert response.status_code == 503
    assert "private" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_unavailable_consent_never_reads_history(boundary):
    allow_test_identity(boundary)

    def unavailable(*_args):
        raise RuntimeError("private consent failure")

    boundary.app.dependency_overrides[get_learning_support_consent_checker] = lambda: unavailable
    response = boundary.client.get(f"{ROOT}/learners/{boundary.learner_id}/progress", params=PARAMS)
    assert response.status_code == 503
    assert "private" not in response.text
    boundary.history.assert_not_called()


@pytest.mark.parametrize("role,suffix", PATHS)
def test_empty_history_stays_empty_for_every_role(boundary, role, suffix):
    allow_test_identity(boundary, role)
    boundary.history.return_value = ()
    response = boundary.client.get(f"{ROOT}/learners/{boundary.learner_id}/{suffix}", params=PARAMS)
    assert response.status_code == 200
    data = response.json()
    assert data["included_session_count"] == 0
    assert data.get("contexts", data.get("partitions")) == []


def test_openapi_lists_role_specific_responses_and_bearer_security(application):
    spec = application.openapi()
    for _, suffix in PATHS:
        operation = spec["paths"][f"{ROOT}/learners/{{learner_id}}/{suffix}"]["get"]
        assert operation["security"] == [{"HTTPBearer": []}]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    operation = spec["paths"][f"{ROOT}/reading-sessions"]["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert "201" in operation["responses"]
