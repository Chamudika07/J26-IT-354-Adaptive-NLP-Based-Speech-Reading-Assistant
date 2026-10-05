"""Validated server configuration; credentials are never exposed by repr."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: SecretStr
    migration_database_url: SecretStr | None = None

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and bool(url.host)
                and bool(url.username)
                and bool(url.database)
            )
        except (ArgumentError, ValueError):
            valid = False
        if not valid:
            raise ValueError(
                "Use a postgresql+psycopg URL with a host, username, and database name"
            )
        return value


class Settings(DatabaseSettings):
    """Runtime security settings; migrations need only DatabaseSettings."""

    jwt_signing_key: SecretStr
    jwt_issuer: str = Field(default="adaptive-assistant", min_length=1, max_length=200)
    jwt_audience: str = Field(default="adaptive-assistant-api", min_length=1, max_length=200)
    access_token_ttl_seconds: int = Field(default=300, ge=30, le=300)
    refresh_absolute_ttl_seconds: int = Field(default=604800, ge=300, le=604800)
    refresh_idle_ttl_seconds: int = Field(default=86400, ge=300, le=86400)
    jwt_clock_tolerance_seconds: int = Field(default=30, ge=0, le=30)

    @field_validator("jwt_signing_key")
    @classmethod
    def validate_signing_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw.encode()) < 32 or "replace" in raw.lower() or raw != raw.strip():
            raise ValueError("Provide a random signing secret of at least 32 bytes")
        return value

    @field_validator("jwt_issuer", "jwt_audience")
    @classmethod
    def validate_token_identifier(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("Use a nonblank identifier without surrounding whitespace")
        return value

    @model_validator(mode="after")
    def validate_lifetimes(self) -> "Settings":
        if not (
            self.access_token_ttl_seconds
            <= self.refresh_idle_ttl_seconds
            <= self.refresh_absolute_ttl_seconds
        ):
            raise ValueError("Require access TTL <= idle TTL <= absolute TTL")
        return self
