"""No database or network; approved fixed-fixture and access-boundary regression checks."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.modules.auth import dependencies
from app.modules.learner_modelling import pp1_demo
from app.modules.learner_modelling.pp1_demo import FIXTURE, authorize, calculate, dataset_digest


def test_prefixes():
    raw = FIXTURE.read_text()
    for count in range(7):
        result = calculate(raw, dataset_digest(raw), count)
        assert result.result.includedSessionCount == count
        assert len(result.result.history) == count
        assert result.source == "postgresql-backed-python"


def test_tampered_fixture():
    raw = FIXTURE.read_text()
    with pytest.raises(ValueError):
        calculate(raw, "0" * 64, 3)
    with pytest.raises(ValueError):
        calculate(raw, dataset_digest(raw), 7)


@pytest.mark.parametrize(
    "env,enabled,role",
    [
        ("production", "1", "learner"),
        ("development", None, "learner"),
        ("development", "1", "educator"),
    ],
)
def test_closed_access(env, enabled, role):
    user = uuid4()
    with pytest.raises(HTTPException):
        authorize(env, enabled, str(user), user, frozenset({role}), "active")


def test_explicit_account():
    user = uuid4()
    authorize("development", "1", str(user), user, frozenset({"learner"}), "active")
    with pytest.raises(HTTPException):
        authorize("development", "1", "", user, frozenset({"learner"}), "active")


def test_http_boundary():
    from types import SimpleNamespace
    from uuid import uuid4

    user = uuid4()
    app = FastAPI()
    app.include_router(pp1_demo.router)
    app.dependency_overrides[dependencies.get_current_principal] = lambda: SimpleNamespace(
        user_id=user, roles=frozenset({"learner"}), status="active"
    )
    app.dependency_overrides[dependencies.get_session] = lambda: None
    app.dependency_overrides[dependencies.get_settings] = lambda: SimpleNamespace(
        app_env="development"
    )
    raw = pp1_demo.FIXTURE.read_text()
    with patch.dict(
        "os.environ", {"READBUDDY_PP1_ENABLED": "1", "READBUDDY_PP1_ACCOUNT_IDS": str(user)}
    ):
        with patch.object(
            pp1_demo, "load_dataset", return_value=(raw, pp1_demo.dataset_digest(raw))
        ) as load:
            secure = TestClient(app, base_url="https://testserver")
            assert secure.get("/pp1-demo/scenarios/3").status_code == 200
            assert secure.get("/pp1-demo/scenarios/7").status_code == 422
            assert secure.get("/pp1-demo/scenarios/3?view=educator").status_code == 422
            assert TestClient(app).get("/pp1-demo/scenarios/3").status_code == 403
            assert load.call_count == 1
        with patch.object(pp1_demo, "load_dataset", side_effect=RuntimeError("private")):
            response = secure.get("/pp1-demo/scenarios/3")
            assert response.status_code == 503
            assert "private" not in response.text
