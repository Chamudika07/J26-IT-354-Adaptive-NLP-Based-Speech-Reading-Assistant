"""Allowlisted API projections; source text is never part of collection summaries."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.reading_materials.normalization import validate_text

Positive = Annotated[int, Field(strict=True, gt=0, le=2147483647)]


class EmptyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MaterialCreate(EmptyRequest):
    title: str = Field(min_length=1, max_length=200, repr=False)
    language_tag: Literal["en"]
    text: str = Field(min_length=1, max_length=50000, repr=False)

    @field_validator("text")
    @classmethod
    def valid_source(cls, value: str) -> str:
        return validate_text(value)

    @field_validator("title")
    @classmethod
    def valid_title(cls, value: str) -> str:
        validate_text(value)
        return value.strip()


class RevisionCreate(MaterialCreate):
    row_version: Positive


class ArchiveRequest(EmptyRequest):
    row_version: Positive


class RevisionSummary(BaseModel):
    id: UUID
    revision_number: int
    title: str
    language_tag: Literal["en"]
    source_kind: Literal["plain_text"]
    created_at: datetime


class RevisionDetail(RevisionSummary):
    original_text: str


class MaterialSummary(BaseModel):
    id: UUID
    created_at: datetime
    row_version: int
    archived_at: datetime | None
    latest_revision: RevisionSummary


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


class LengthLoad(BaseModel):
    character_count: int
    word_count: int
    sentence_count: int


class WordFormCharacteristics(BaseModel):
    unique_word_count: int
    average_word_length: Decimal
    maximum_word_length: int
    lexical_diversity: Decimal


class SentenceStructure(BaseModel):
    average_sentence_length: Decimal
    maximum_sentence_length: int


class Vocabulary(BaseModel):
    status: Literal["not_evaluated"] = "not_evaluated"


class TextProfile(BaseModel):
    material_id: UUID
    revision_id: UUID
    processing_run_id: UUID
    language_tag: Literal["en"] = "en"
    pipeline_version: str
    profile_schema_version: str
    completed_at: datetime
    length_load: LengthLoad
    word_form_characteristics: WordFormCharacteristics
    sentence_structure: SentenceStructure
    vocabulary: Vocabulary


class RunSummary(BaseModel):
    id: UUID
    attempt_number: int
    status: Literal["running", "succeeded", "failed"]
    started_at: datetime
    finished_at: datetime | None
    failure_code: Literal["pipeline_failed", "processing_interrupted"] | None
    pipeline_version: str
    profile_schema_version: str


class SentenceDetail(BaseModel):
    ordinal: int
    source_start: int
    source_end: int
    analysis_start: int
    analysis_end: int
    word_count: int
    total_word_letter_count: int
    max_word_letter_count: int
    original_text: str
    normalized_text: str


class RunDetail(RunSummary):
    profile: TextProfile | None
    sentences: list[SentenceDetail] | None = None
