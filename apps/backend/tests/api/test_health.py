from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_session


def test_liveness_does_not_need_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_success(application: FastAPI, client: TestClient) -> None:
    session = Mock(spec=Session)
    application.dependency_overrides[get_session] = lambda: session
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    session.execute.assert_called_once()


def test_readiness_failure_hides_database_details(application: FastAPI, client: TestClient) -> None:
    session = Mock(spec=Session)
    session.execute.side_effect = OperationalError(
        "SELECT 1", {}, Exception("private-database-credentials")
    )
    application.dependency_overrides[get_session] = lambda: session
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "http_error", "message": "Database unavailable"}}
    assert "private-database-credentials" not in response.text


def test_only_approved_endpoints_are_exposed(client: TestClient) -> None:
    assert set(client.get("/openapi.json").json()["paths"]) == {
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/learners",
        "/api/v1/learners/{learner_id}",
        "/api/v1/learners/{learner_id}/preferences",
    }


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/unknown")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "http_error", "message": "Not Found"}}
