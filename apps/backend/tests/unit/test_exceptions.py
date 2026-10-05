from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel


class SyntheticRequest(BaseModel):
    count: int


def test_validation_errors_do_not_echo_sensitive_input(
    application: FastAPI, client: TestClient
) -> None:
    @application.post("/test-only-validation")
    def validate_request(payload: SyntheticRequest) -> SyntheticRequest:
        return payload

    response = client.post("/test-only-validation", json={"count": "sensitive-child-content"})
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "validation_error", "message": "Invalid request"}}
    assert "sensitive-child-content" not in response.text
