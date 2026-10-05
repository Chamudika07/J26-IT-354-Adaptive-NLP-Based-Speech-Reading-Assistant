"""Learner data contracts. Schemas validate shape, not access or consent policy."""

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints

from app.core.schemas import Schema, VersionedReadSchema

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
LanguageTag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=35)]
AgeBand = Annotated[int, Field(strict=True, ge=9, le=12)]
GradeLevel = Annotated[int, Field(strict=True, ge=3, le=8)]
PurposeCode = Literal["learning_support", "research_participation", "audio_retention"]
RecordKind = Literal["guardian_consent", "learner_assent"]


class LearnerProfileCreate(Schema):
    """Minimal profile input; creator/login linking must be supplied by authorized services."""

    display_name: DisplayName
    age_band: AgeBand | None = None
    grade_level: GradeLevel | None = None


class LearnerProfileRead(VersionedReadSchema):
    learner_user_id: UUID | None
    display_name: DisplayName
    created_by_user_id: UUID
    archived_at: AwareDatetime | None
    age_band: AgeBand | None
    grade_level: GradeLevel | None


class GuardianLearnerRelationshipRead(VersionedReadSchema):
    guardian_user_id: UUID
    learner_id: UUID
    access_level: Literal["viewer", "manager"]
    can_provide_consent: bool
    authority_verified_at: AwareDatetime | None
    authority_verified_by_user_id: UUID | None
    granted_by_user_id: UUID
    revoked_at: AwareDatetime | None
    revoked_by_user_id: UUID | None


class EducatorLearnerRelationshipRead(VersionedReadSchema):
    educator_user_id: UUID
    learner_id: UUID
    access_level: Literal["viewer", "instructor"]
    expires_at: AwareDatetime
    granted_by_user_id: UUID
    revoked_at: AwareDatetime | None
    revoked_by_user_id: UUID | None


class LearnerPreferencesInput(Schema):
    """NULL preferences inherit application/device defaults."""

    preferred_language_tag: LanguageTag | None = None
    text_scale: (
        Annotated[Decimal, Field(ge=Decimal("0.75"), le=Decimal("3.00"), decimal_places=2)] | None
    ) = None
    line_spacing: (
        Annotated[Decimal, Field(ge=Decimal("1.00"), le=Decimal("3.00"), decimal_places=2)] | None
    ) = None
    theme: Literal["system", "light", "dark", "high_contrast"] | None = None
    reduce_motion: bool | None = None


class LearnerPreferencesRead(LearnerPreferencesInput, VersionedReadSchema):
    learner_id: UUID
    updated_by_user_id: UUID


class ConsentNoticeVersionRead(VersionedReadSchema):
    purpose_code: PurposeCode
    record_kind: RecordKind
    version_label: str
    language_tag: LanguageTag
    notice_text: str
    content_sha256: str
    published_at: AwareDatetime
    published_by_user_id: UUID
    retired_at: AwareDatetime | None
    retired_by_user_id: UUID | None


class ConsentRecordRead(Schema):
    id: UUID
    learner_id: UUID
    notice_version_id: UUID
    purpose_code: PurposeCode
    record_kind: RecordKind
    guardian_relationship_id: UUID | None
    decision: Literal["granted", "declined", "withdrawn"]
    sequence_no: int = Field(gt=0)
    occurred_at: AwareDatetime
    recorded_at: AwareDatetime
    recorded_by_user_id: UUID
    capture_method: Literal["self_service", "assisted_in_person"]
