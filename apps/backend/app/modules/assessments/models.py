"""Assessment-owned material, lifecycle, and immutable observation storage."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class ReadingAssessmentMaterial(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "reading_assessment_materials"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_reading_material_code_version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("word_count > 0", name="word_count_positive"),
        CheckConstraint("comprehension_question_count >= 0", name="questions_nonnegative"),
        *(
            CheckConstraint(f"length(btrim({name})) > 0", name=f"{name}_nonblank")
            for name in (
                "code",
                "title",
                "language_tag",
                "passage_text",
                "tokenization_version",
                "administration_instructions",
            )
        ),
        CheckConstraint(
            "(comprehension_question_count = 0 AND comprehension_prompt_text IS NULL "
            "AND comprehension_rubric_text IS NULL) OR "
            "(comprehension_question_count > 0 AND comprehension_prompt_text IS NOT NULL "
            "AND comprehension_rubric_text IS NOT NULL "
            "AND length(btrim(comprehension_prompt_text)) > 0 "
            "AND length(btrim(comprehension_rubric_text)) > 0)",
            name="comprehension_material",
        ),
        Index("ix_reading_material_active", "id", postgresql_where=text("is_active")),
    )
    code: Mapped[str] = mapped_column(String(80))
    version: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    language_tag: Mapped[str] = mapped_column(String(35))
    passage_text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int]
    tokenization_version: Mapped[str] = mapped_column(String(80))
    administration_instructions: Mapped[str] = mapped_column(Text)
    comprehension_prompt_text: Mapped[str | None] = mapped_column(Text)
    comprehension_rubric_text: Mapped[str | None] = mapped_column(Text)
    comprehension_question_count: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class ReadingAssessmentSession(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "reading_assessment_sessions"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("collection_mode = 'instructor_observed'", name="mode_values"),
        CheckConstraint("length(btrim(protocol_version)) > 0", name="protocol_nonblank"),
        CheckConstraint(
            "(status = 'started' AND completed_at IS NULL AND abandoned_at IS NULL) OR "
            "(status = 'completed' AND completed_at IS NOT NULL AND abandoned_at IS NULL) OR "
            "(status = 'abandoned' AND abandoned_at IS NOT NULL AND completed_at IS NULL)",
            name="state_timestamps",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="complete_order"
        ),
        CheckConstraint("abandoned_at IS NULL OR abandoned_at >= started_at", name="abandon_order"),
        Index("ix_reading_session_history", "learner_id", text("started_at DESC"), text("id DESC")),
        Index(
            "uq_reading_session_started",
            "learner_id",
            "administered_by_user_id",
            unique=True,
            postgresql_where=text("status = 'started'"),
        ),
    )
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner_profiles.id", ondelete="RESTRICT"))
    material_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_assessment_materials.id", ondelete="RESTRICT"), index=True
    )
    administered_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    collection_mode: Mapped[str] = mapped_column(String(24))
    protocol_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReadingAssessmentResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reading_assessment_results"
    __table_args__ = (
        CheckConstraint("reading_duration_ms > 0", name="duration_positive"),
        *(
            CheckConstraint(f"{name} >= 0", name=f"{name}_nonnegative")
            for name in (
                "attempted_word_count",
                "correct_word_count",
                "omission_count",
                "substitution_count",
                "insertion_count",
                "repetition_count",
                "self_correction_count",
            )
        ),
        CheckConstraint("correct_word_count <= attempted_word_count", name="correct_attempted"),
        CheckConstraint(
            "unfamiliar_word_count IS NULL OR "
            "unfamiliar_word_count BETWEEN 0 AND attempted_word_count",
            name="unfamiliar_range",
        ),
        CheckConstraint(
            "(comprehension_correct IS NULL AND comprehension_total IS NULL) OR "
            "(comprehension_correct IS NOT NULL AND comprehension_total IS NOT NULL "
            "AND comprehension_total > 0 "
            "AND comprehension_correct BETWEEN 0 AND comprehension_total)",
            name="comprehension_range",
        ),
        CheckConstraint("length(btrim(scoring_version)) > 0", name="scoring_nonblank"),
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_assessment_sessions.id", ondelete="RESTRICT"), unique=True
    )
    submitted_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reading_duration_ms: Mapped[int]
    attempted_word_count: Mapped[int]
    correct_word_count: Mapped[int]
    omission_count: Mapped[int]
    substitution_count: Mapped[int]
    insertion_count: Mapped[int]
    repetition_count: Mapped[int]
    self_correction_count: Mapped[int]
    unfamiliar_word_count: Mapped[int | None]
    comprehension_correct: Mapped[int | None]
    comprehension_total: Mapped[int | None]
    scoring_version: Mapped[str] = mapped_column(String(80))
