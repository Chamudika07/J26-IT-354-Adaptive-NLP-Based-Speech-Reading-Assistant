"""Explicit read projections; never serialize password hashes or ORM internals."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, SecretStr, field_validator

from app.core.schemas import Schema, VersionedReadSchema

RoleCode = Literal["guardian", "educator", "learner", "administrator"]
UserStatus = Literal["active", "disabled", "anonymized"]


class UserRead(VersionedReadSchema):
    login_handle: str | None
    email: str | None
    email_verified_at: AwareDatetime | None
    status: UserStatus
    deleted_at: AwareDatetime | None


class RoleRead(VersionedReadSchema):
    code: RoleCode
    description: str
    is_active: bool


class UserRoleRead(VersionedReadSchema):
    user_id: UUID
    role_id: UUID
    granted_by_user_id: UUID
    revoked_at: AwareDatetime | None
    revoked_by_user_id: UUID | None


class LoginRequest(Schema):
    login_handle: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("login_handle")
    @classmethod
    def normalize_handle(cls, value: str) -> str:
        return value.strip().lower()


class RefreshRequest(Schema):
    refresh_token: SecretStr = Field(min_length=1, max_length=256)


class TokenResponse(Schema):
    access_token: str = Field(repr=False)
    refresh_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class MeResponse(Schema):
    user_id: UUID
    login_handle: str
    status: Literal["active"]
    roles: list[str]
