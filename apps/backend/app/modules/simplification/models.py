"""SQLAlchemy models for adaptive text simplification and vocabulary support."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class SimplificationSession(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    """A record of a text simplification request and its generated output."""

    __tablename__ = "simplification_sessions"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("source_length > 0", name="source_length_positive"),
        CheckConstraint("output_length > 0", name="output_length_positive"),
        CheckConstraint(
            "source_difficulty IS NULL OR "
            "(source_difficulty >= 0.00 AND source_difficulty <= 1.00)",
            name="source_difficulty_range",
        ),
        CheckConstraint(
            "output_difficulty IS NULL OR "
            "(output_difficulty >= 0.00 AND output_difficulty <= 1.00)",
            name="output_difficulty_range",
        ),
        CheckConstraint("adaptation_attempt BETWEEN 1 AND 10", name="adaptation_attempt_range"),
        CheckConstraint("length(source_text_sha256) = 64", name="source_text_sha256_length"),
        CheckConstraint(
            "strategy_applied IN ("
            "'vocabulary_swap', 'sentence_split', 'concept_reduction', 'full_rewrite', 'combined'"
            ")",
            name="strategy_applied_values",
        ),
        CheckConstraint(
            "target_reading_level IN ('beginner', 'elementary', 'intermediate', 'advanced')",
            name="target_reading_level_values",
        ),
        Index(
            "ix_simplification_sessions_learner_history",
            "learner_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_simplification_sessions_document_id",
            "document_id",
            postgresql_where=text("document_id IS NOT NULL"),
        ),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learner_profiles.id", ondelete="RESTRICT"), index=True
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    # Loose correlation ID; no foreign key because documents table is not in migrations yet.
    document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_text_sha256: Mapped[str] = mapped_column(String(64))
    # Stored only if explicit retention consent exists; otherwise kept NULL.
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_length: Mapped[int] = mapped_column(Integer)
    source_difficulty: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    strategy_applied: Mapped[str] = mapped_column(String(24))
    target_reading_level: Mapped[str] = mapped_column(String(16))
    adaptation_attempt: Mapped[int] = mapped_column(SmallInteger)
    simplified_text: Mapped[str] = mapped_column(Text)
    output_length: Mapped[int] = mapped_column(Integer)
    output_difficulty: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    concepts_preserved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    validation_warnings: Mapped[list[str]] = mapped_column(
        ARRAY(String), server_default=text("'{}'")
    )
    ai_provider: Mapped[str] = mapped_column(String(40))
    ai_latency_ms: Mapped[int] = mapped_column(Integer)


class SimplificationVocabulary(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    """Vocabulary terms identified automatically or requested on-demand by a learner."""

    __tablename__ = "simplification_vocabulary"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("length(btrim(term)) > 0", name="term_nonblank"),
        CheckConstraint("source IN ('automatic', 'user')", name="source_values"),
        CheckConstraint("length(btrim(language_tag)) > 0", name="language_tag_nonblank"),
        Index("ix_simplification_vocabulary_session_id", "session_id"),
    )

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("simplification_sessions.id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(200))
    simplified_definition: Mapped[str] = mapped_column(Text)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=text("'{}'"))
    source: Mapped[str] = mapped_column(String(16))
    language_tag: Mapped[str] = mapped_column(String(35))


class SimplificationFeedback(UUIDPrimaryKeyMixin, Base):
    """Append-only post-reading learner feedback event."""

    __tablename__ = "simplification_feedback"
    __table_args__ = (
        CheckConstraint(
            "feedback_signal IN ('too_hard', 'too_easy', 'just_right', 'skipped')",
            name="feedback_signal_values",
        ),
        CheckConstraint(
            "time_spent_seconds IS NULL OR "
            "(time_spent_seconds >= 0 AND time_spent_seconds <= 7200)",
            name="time_spent_seconds_range",
        ),
        CheckConstraint(
            "vocabulary_lookups_count IS NULL OR "
            "(vocabulary_lookups_count >= 0 AND vocabulary_lookups_count <= 100)",
            name="vocabulary_lookups_count_range",
        ),
        CheckConstraint("occurred_at <= recorded_at", name="recording_order"),
        Index("ix_simplification_feedback_session_id", "session_id"),
        Index(
            "ix_simplification_feedback_learner_history",
            "learner_id",
            text("recorded_at DESC"),
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simplification_sessions.id", ondelete="RESTRICT"), index=True
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learner_profiles.id", ondelete="RESTRICT"), index=True
    )
    feedback_signal: Mapped[str] = mapped_column(String(16))
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vocabulary_lookups_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    completed_reading: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
