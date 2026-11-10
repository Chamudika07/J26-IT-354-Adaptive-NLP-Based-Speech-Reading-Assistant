"""Public provisioning schemas, separate from persistence and services."""

from uuid import UUID

from pydantic import Field, SecretStr, field_validator

from app.core.schemas import Schema


class AccountCreate(Schema):
    login_handle: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")
    password: SecretStr = Field(min_length=15, max_length=128, repr=False)

    @field_validator("login_handle", mode="before")
    @classmethod
    def normalize(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class AccountCreated(Schema):
    user_id: UUID
    login_handle: str
    status: str
    roles: list[str]
