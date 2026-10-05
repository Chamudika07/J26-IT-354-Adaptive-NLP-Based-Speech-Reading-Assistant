"""Tests use synthetic settings; no developer .env or production data is loaded."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    # Explicit values and disabled dotenv loading isolate tests from local settings.
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    return Settings(
        _env_file=None,
        app_env="test",
        log_level="WARNING",
        database_url=SecretStr("postgresql+psycopg://synthetic:unused@127.0.0.1:1/unit_test"),
    )


@pytest.fixture
def application(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(application: FastAPI) -> Iterator[TestClient]:
    with TestClient(application) as test_client:
        yield test_client
