"""Explicit public projections: no binary location, hashes, filenames or actors."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.modules.reading_materials.normalization import validate_text
from app.modules.reading_materials.pdf.contracts import PageEvidence
from app.modules.reading_materials.schemas import EmptyRequest, Positive


class UploadMetadata(EmptyRequest):
    title: str = Field(min_length=1, max_length=200, repr=False)
    language_tag: Literal["en"]
    upload_request_id: UUID

    @field_validator("title")
    @classmethod
    def title_valid(cls, value: str) -> str:
        return validate_text(value).strip()


class ExtractRequest(EmptyRequest):
    row_version: Positive | None = None


class RunSummary(EmptyRequest):
    id: UUID
    source_id: UUID
    attempt_number: int
    status: Literal["running", "extracted", "ocr_required", "needs_review", "failed"]
    started_at: datetime
    finished_at: datetime | None
    outcome_code: str | None
    extraction_version: str
    validation_version: str
    assembly_version: str
    quality_version: str
    extractor_name: str
    extractor_package_version: str
    python_version: str
    unicode_version: str
    quality_tokenizer_version: str


class RunDetail(RunSummary):
    material_id: UUID | None
    revision_id: UUID | None
    total_page_count: int | None
    pages_with_lexical_text: int | None
    pages_with_zero_characters: int | None
    pages_with_zero_lexical_words: int | None
    extracted_character_count: int | None
    assembled_character_count: int | None
    lexical_word_count: int | None
    lexical_page_coverage: Decimal | None
    assembled_text: str | None = Field(default=None, repr=False)
    pages: list[PageEvidence] | None = None


class SourceSummary(EmptyRequest):
    id: UUID
    material_id: UUID | None
    title: str
    language_tag: Literal["en"]
    media_type: Literal["application/pdf"]
    byte_count: int
    created_at: datetime
    row_version: int
    archived_at: datetime | None
    latest_extraction: RunSummary | None


class UploadResult(EmptyRequest):
    source: SourceSummary
    extraction: RunDetail
