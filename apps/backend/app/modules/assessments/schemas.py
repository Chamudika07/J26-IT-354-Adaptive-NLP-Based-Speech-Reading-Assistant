"""Explicit public projections. Requests never accept actor or scoring provenance."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(strict=True, ge=0, le=2147483647)]
Positive = Annotated[int, Field(strict=True, gt=0, le=2147483647)]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessmentStartRequest(Request):
    material_id: UUID


class AssessmentAbandonRequest(Request):
    row_version: Positive


class Observations(BaseModel):
    reading_duration_ms: Positive
    attempted_word_count: Count
    correct_word_count: Count
    omission_count: Count
    substitution_count: Count
    insertion_count: Count
    repetition_count: Count
    self_correction_count: Count
    unfamiliar_word_count: Count | None = None
    comprehension_correct: Count | None = None
    comprehension_total: Positive | None = None


class AssessmentCompletionRequest(Observations, Request):
    row_version: Positive

    @model_validator(mode="after")
    def measurements_consistent(self) -> Self:
        if self.correct_word_count > self.attempted_word_count:
            raise ValueError("Invalid observations")
        if self.unfamiliar_word_count is not None and (
            self.unfamiliar_word_count > self.attempted_word_count
        ):
            raise ValueError("Invalid observations")
        if (self.comprehension_correct is None) != (self.comprehension_total is None):
            raise ValueError("Invalid comprehension")
        if self.comprehension_correct is not None and self.comprehension_total is not None:
            if self.comprehension_correct > self.comprehension_total:
                raise ValueError("Invalid comprehension")
        return self


class AssessmentMaterialSummary(BaseModel):
    id: UUID
    code: str
    version: int
    title: str
    language_tag: str
    word_count: int
    comprehension_question_count: int


class AssessmentMaterialDetail(AssessmentMaterialSummary):
    passage_text: str
    administration_instructions: str
    comprehension_prompt_text: str | None
    comprehension_rubric_text: str | None
    tokenization_version: str


class AssessmentMaterialPage(BaseModel):
    items: list[AssessmentMaterialSummary]
    next_cursor: UUID | None


class AssessmentResultSummary(Observations):
    scoring_version: str
    reading_duration_seconds: Decimal
    reading_time_minutes: Decimal
    attempted_words_per_minute: Decimal
    words_correct_per_minute: Decimal
    attempted_word_accuracy_percentage: Decimal | None
    incorrect_attempt_percentage: Decimal | None
    comprehension_percentage: Decimal | None


class AssessmentSessionResponse(BaseModel):
    id: UUID
    material: AssessmentMaterialSummary
    collection_mode: Literal["instructor_observed"]
    protocol_version: str
    status: Literal["started", "completed", "abandoned"]
    started_at: datetime
    completed_at: datetime | None
    abandoned_at: datetime | None
    row_version: int
    result: AssessmentResultSummary | None


class AssessmentStartResponse(AssessmentSessionResponse):
    material: AssessmentMaterialDetail


class AssessmentHistoryItem(AssessmentSessionResponse):
    pass


class AssessmentHistoryPage(BaseModel):
    items: list[AssessmentHistoryItem]
    next_cursor: str | None
