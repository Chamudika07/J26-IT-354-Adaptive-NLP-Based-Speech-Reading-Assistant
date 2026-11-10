"""Minimal management inputs; no consent claims or child login provisioning."""

from datetime import UTC
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator

from app.core.schemas import Schema


class LearnerCreate(Schema):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A display name is required")
        return value.strip()


class LearnerCreated(Schema):
    id: UUID
    display_name: str


class EducatorGrantCreate(Schema):
    educator_user_id: UUID
    access_level: Literal["viewer", "instructor"]
    expires_at: AwareDatetime

    @field_validator("expires_at")
    @classmethod
    def utc(cls, value: AwareDatetime) -> AwareDatetime:
        return value.astimezone(UTC)


class EducatorGrantRead(Schema):
    id: UUID
    learner_id: UUID
    educator_user_id: UUID
    access_level: Literal["viewer", "instructor"]
    expires_at: AwareDatetime
    revoked_at: AwareDatetime | None
