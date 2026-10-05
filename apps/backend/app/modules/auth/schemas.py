"""Explicit read projections; never serialize password hashes or ORM internals."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime

from app.core.schemas import VersionedReadSchema

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
