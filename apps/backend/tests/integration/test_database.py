"""Read-only connectivity check, enabled only for an explicit disposable test DB."""

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.db.session import create_db_engine
from app.main import create_app

pytestmark = pytest.mark.integration


def test_postgresql_connectivity_and_utc_session() -> None:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    url = make_url(value)
    if not url.database or not url.database.endswith("_test"):
        pytest.fail("Refusing integration connection: the database name must end in _test")

    settings = Settings(
        _env_file=None,
        database_url=SecretStr(value),
        migration_database_url=None,
        app_env="test",
        jwt_signing_key=SecretStr("synthetic-test-signing-key-never-use-in-production"),
        log_level="WARNING",
    )
    engine = create_db_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
            assert connection.execute(text("SHOW timezone")).scalar_one() == "UTC"
    finally:
        engine.dispose()

    # Exercise the actual request-scoped session dependency against the same DB.
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
