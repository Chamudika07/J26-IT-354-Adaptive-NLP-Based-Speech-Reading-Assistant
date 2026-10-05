"""Shared schema metadata, independent from ORM models."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class VersionedReadSchema(Schema):
    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime
    row_version: int = Field(gt=0)
