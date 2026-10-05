import pytest
from pydantic import ValidationError

from app.core.config import Settings

DATABASE_URL = "postgresql+psycopg://synthetic:secret-marker@localhost:5432/config_test"


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "MIGRATION_DATABASE_URL", "APP_ENV", "LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("APP_ENV", "test")
    settings = Settings(_env_file=None)
    assert settings.app_env == "test"
    assert settings.database_url.get_secret_value() == DATABASE_URL
    assert "secret-marker" not in repr(settings)


def test_database_url_is_required() -> None:
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///local.db",
        "postgresql://synthetic@localhost/config_test",
        "postgresql+psycopg://synthetic@localhost",
        "postgresql+psycopg://synthetic:secret-marker@localhost:bad/config_test",
        "not-a-url-secret-marker",
    ],
)
def test_invalid_database_urls_are_rejected_without_exposing_input(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert "secret-marker" not in str(error.value)


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("APP_ENV", "unknown")
    with pytest.raises(ValidationError, match="app_env"):
        Settings(_env_file=None)
