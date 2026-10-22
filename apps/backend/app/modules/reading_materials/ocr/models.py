"""Mutable review drafts and immutable decisions; raw extraction evidence stays separate."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin

TEXT_STATE = (
    "(reviewed_text IS NULL AND reviewed_text_sha256 IS NULL AND submitted_by IS NULL "
    "AND submitted_at IS NULL) OR (reviewed_text IS NOT NULL AND "
    "length(btrim(reviewed_text)) BETWEEN 1 AND 50000 AND length(reviewed_text)<=50000 "
    "AND reviewed_text_sha256 IS NOT NULL AND reviewed_text_sha256="
    "encode(sha256(convert_to(reviewed_text,'UTF8')),'hex') AND submitted_by IS NOT NULL "
    "AND submitted_at IS NOT NULL AND submitted_at>=created_at AND submitted_at<=updated_at)"
)
DECISION_EMPTY = (
    "decided_by IS NULL AND decided_at IS NULL AND decision_request_id IS NULL "
    "AND decision_request_sha256 IS NULL AND accepted_revision_id IS NULL "
    "AND rejection_reason IS NULL"
)
DECISION_PRESENT = (
    "decided_by IS NOT NULL AND decided_at IS NOT NULL AND decided_at>=created_at "
    "AND decided_at<=updated_at AND (submitted_at IS NULL OR decided_at>=submitted_at) "
    "AND decision_request_id IS NOT NULL AND decision_request_sha256 IS NOT NULL "
    "AND decision_request_sha256 ~ '^[0-9a-f]{64}$'"
)
REVIEW_STATE = (
    f"(status='pending' AND reviewed_text IS NULL AND {DECISION_EMPTY}) OR "
    f"(status='submitted' AND reviewed_text IS NOT NULL AND {DECISION_EMPTY}) OR "
    f"(status='accepted' AND reviewed_text IS NOT NULL AND {DECISION_PRESENT} "
    "AND accepted_revision_id IS NOT NULL AND rejection_reason IS NULL) OR "
    f"(status='rejected' AND {DECISION_PRESENT} AND accepted_revision_id IS NULL "
    "AND length(btrim(rejection_reason)) BETWEEN 1 AND 500)"
)


class ExtractionReview(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "reading_material_extraction_reviews"
    __table_args__ = (
        UniqueConstraint("extraction_run_id", name="uq_ocr_review_run"),
        UniqueConstraint("accepted_revision_id", name="uq_ocr_review_revision"),
        UniqueConstraint("decided_by", "decision_request_id", name="uq_ocr_review_decision"),
        CheckConstraint(f"({TEXT_STATE}) IS TRUE", name="review_text"),
        CheckConstraint(f"({REVIEW_STATE}) IS TRUE", name="review_state"),
        CheckConstraint(
            "row_version>0 AND updated_at>=created_at AND "
            "(expected_material_version IS NULL OR expected_material_version>0)",
            name="versions",
        ),
        Index("ix_ocr_review_status", "status", "created_at", "id"),
    )
    extraction_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_material_extraction_runs.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(24))
    reviewed_text: Mapped[str | None] = mapped_column(Text)
    reviewed_text_sha256: Mapped[str | None] = mapped_column(String(64))
    submitted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_request_id: Mapped[UUID | None]
    decision_request_sha256: Mapped[str | None] = mapped_column(String(64))
    accepted_revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reading_material_revisions.id", ondelete="RESTRICT")
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    expected_material_version: Mapped[int | None]


class ExtractionReviewPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reading_material_extraction_review_pages"
    __table_args__ = (
        UniqueConstraint("review_id", "page_number", name="uq_ocr_review_page"),
        CheckConstraint("page_number BETWEEN 1 AND 25", name="page_number"),
        CheckConstraint(
            "reviewed_text_start>=0 AND reviewed_text_end>=reviewed_text_start "
            "AND reviewed_text_end<=50000",
            name="spans",
        ),
        CheckConstraint("updated_at>=created_at", name="timestamps"),
    )
    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_material_extraction_reviews.id", ondelete="RESTRICT")
    )
    page_number: Mapped[int]
    reviewed_text_start: Mapped[int]
    reviewed_text_end: Mapped[int]
    page_acknowledged: Mapped[bool]
