"""SQLAlchemy 2 models for reading sessions and learner reading-support settings."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class ReadingSession(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    """Canonical persistent telemetry and evaluation records for reading sessions."""

    __tablename__ = "reading_sessions"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="request_digest_format"),
        CheckConstraint(
            "completion_status IN ('completed', 'abandoned', 'interrupted')",
            name="completion_status_values",
        ),
        CheckConstraint(
            "task_type IN ('independent_reading', 'assisted_read_aloud', 'guided_echo_reading')",
            name="task_type_values",
        ),
        CheckConstraint(
            "difficulty_tier IN ('early', 'intermediate', 'advanced')",
            name="difficulty_tier_values",
        ),
        CheckConstraint(
            "support_mode IN ('baseline_fixed', 'adaptive', 'manual_override')",
            name="support_mode_values",
        ),
        CheckConstraint("words_attempted >= 0", name="words_attempted_nonnegative"),
        CheckConstraint("words_correct >= 0", name="words_correct_nonnegative"),
        CheckConstraint("words_correct <= words_attempted", name="words_correct_le_attempted"),
        CheckConstraint("target_word_count >= 0", name="target_word_count_nonnegative"),
        CheckConstraint("active_duration_ms >= 0", name="active_duration_ms_nonnegative"),
        CheckConstraint("total_duration_ms >= 0", name="total_duration_ms_nonnegative"),
        CheckConstraint("active_duration_ms <= total_duration_ms", name="active_duration_le_total"),
        CheckConstraint(
            "total_pause_duration_ms IS NULL OR "
            "(total_pause_duration_ms >= 0 AND total_pause_duration_ms <= total_duration_ms)",
            name="pause_duration_bounds",
        ),
        CheckConstraint("pause_count IS NULL OR pause_count >= 0", name="pause_count_nonnegative"),
        CheckConstraint(
            "hesitation_count IS NULL OR hesitation_count >= 0",
            name="hesitation_count_nonnegative",
        ),
        CheckConstraint(
            "replay_count IS NULL OR replay_count >= 0",
            name="replay_count_nonnegative",
        ),
        CheckConstraint("session_end_time >= session_start_time", name="session_time_order"),
        UniqueConstraint(
            "learner_id", "client_session_id", name="uq_reading_sessions_client_session"
        ),
        Index(
            "ix_reading_sessions_learner_chronological",
            "learner_id",
            "session_start_time",
            "id",
        ),
        Index(
            "ix_reading_sessions_partition",
            "learner_id",
            "task_type",
            "difficulty_tier",
            "support_mode",
            "session_start_time",
        ),
        Index("ix_reading_sessions_digest", "request_digest"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learner_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    client_session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    request_digest: Mapped[str] = mapped_column(CHAR(64), nullable=False)

    session_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="independent_reading"
    )
    difficulty_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="intermediate")
    support_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="adaptive")
    completion_status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )

    words_attempted: Mapped[int] = mapped_column(Integer, nullable=False)
    words_correct: Mapped[int] = mapped_column(Integer, nullable=False)
    target_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    active_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    total_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    hesitation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_pause_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pause_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    replay_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    calculated_accuracy: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    calculated_wpm: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    calculated_hesitation_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    calculated_engagement_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    engagement_formula_version: Mapped[str | None] = mapped_column(String(32), nullable=True)


class LearnerReadingSupportSettings(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    """Configured and adaptive scaffolding parameters for reading support."""

    __tablename__ = "learner_reading_support_settings"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint(
            "support_mode IN ('baseline_fixed', 'adaptive', 'manual_override')",
            name="support_mode_values",
        ),
        CheckConstraint(
            "default_difficulty_tier IN ('early', 'intermediate', 'advanced')",
            name="default_difficulty_values",
        ),
        CheckConstraint(
            "simplification_level BETWEEN 1 AND 5",
            name="simplification_level_range",
        ),
        CheckConstraint(
            "speech_rate_multiplier BETWEEN 0.50 AND 2.00",
            name="speech_rate_multiplier_range",
        ),
        CheckConstraint(
            "visual_pacing_rate_wpm IS NULL OR visual_pacing_rate_wpm BETWEEN 20 AND 300",
            name="visual_pacing_rate_range",
        ),
        CheckConstraint(
            "pause_threshold_ms BETWEEN 1000 AND 10000",
            name="pause_threshold_range",
        ),
        UniqueConstraint("learner_id", name="uq_learner_reading_support_settings_learner_id"),
        Index("ix_learner_reading_support_settings_updated", "updated_at"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learner_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    support_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="adaptive")
    default_difficulty_tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="intermediate"
    )

    enable_speech_cues: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    speech_rate_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("1.00")
    )
    enable_syllable_assistance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enable_phoneme_breakdown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enable_visual_pacing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visual_pacing_rate_wpm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    enable_line_focus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    simplification_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    pause_threshold_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=2500)

    manual_override_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
