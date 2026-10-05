"""Tests use synthetic settings; no developer .env or production data is loaded."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

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


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    """Exclusive disposable database only. No fallback to DATABASE_URL or dotenv."""
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL and ALLOW_TEST_DATABASE_RESET=1 for PostgreSQL tests")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
        pytest.fail(
            "Refusing test database: PostgreSQL/psycopg and a name ending in _test are required"
        )
    if os.environ.get("ALLOW_TEST_DATABASE_RESET") != "1":
        pytest.fail(
            "Database tests require ALLOW_TEST_DATABASE_RESET=1 and an exclusive disposable DB"
        )
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail("Migration tests require an exclusive database; xdist is not supported")
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"},
    )
    try:
        with engine.begin() as connection:
            assert (
                connection.execute(text("SELECT current_database()")).scalar_one() == url.database
            )
            command.upgrade(migration_config(connection), "head")
        yield engine
    finally:
        engine.dispose()


def migration_config(connection: Connection) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def db_session(postgres_engine: Engine) -> Iterator[Session]:
    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            try:
                yield session
            finally:
                session.close()
                transaction.rollback()
