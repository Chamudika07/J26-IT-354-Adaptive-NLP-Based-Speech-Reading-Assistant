"""Internal review contracts. No HTTP routes expose these models."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.modules.reading_materials.schemas import EmptyRequest, Positive


class ReviewedPage(EmptyRequest):
    page_number: Positive
    text: str = Field(max_length=50000, repr=False)
    acknowledged: bool = Field(strict=True)


class Submission(EmptyRequest):
    row_version: Positive
    expected_material_version: Positive | None = None
    pages: list[ReviewedPage] = Field(min_length=1, max_length=25)


class Acceptance(EmptyRequest):
    row_version: Positive
    decision_request_id: UUID
    expected_material_version: Positive | None = None


class Rejection(EmptyRequest):
    row_version: Positive
    decision_request_id: UUID
    reason: Literal["unusable_text", "incorrect_content", "incomplete_content", "wrong_source"]


class ReviewResult(EmptyRequest):
    id: UUID
    extraction_run_id: UUID
    status: Literal["pending", "submitted", "accepted", "rejected"]
    row_version: int
    reviewed_text: str | None = Field(repr=False)
    reviewed_text_sha256: str | None
    accepted_revision_id: UUID | None
    expected_material_version: int | None
