"""reading sessions and learner reading support settings

Revision ID: 0006_learner_reading_sessions
Revises: 0005_auth_sessions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_learner_reading_sessions"
down_revision: str | Sequence[str] | None = "0005_auth_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reading_sessions",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("client_session_id", sa.Uuid(), nullable=False),
        sa.Column("request_digest", sa.CHAR(length=64), nullable=False),
        sa.Column("session_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("difficulty_tier", sa.String(length=20), nullable=False),
        sa.Column("support_mode", sa.String(length=24), nullable=False),
        sa.Column("completion_status", sa.String(length=16), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("words_attempted", sa.Integer(), nullable=False),
        sa.Column("words_correct", sa.Integer(), nullable=False),
        sa.Column("target_word_count", sa.Integer(), nullable=False),
        sa.Column("active_duration_ms", sa.Integer(), nullable=False),
        sa.Column("total_duration_ms", sa.Integer(), nullable=False),
        sa.Column("hesitation_count", sa.Integer(), nullable=True),
        sa.Column("total_pause_duration_ms", sa.Integer(), nullable=True),
        sa.Column("pause_count", sa.Integer(), nullable=True),
        sa.Column("replay_count", sa.Integer(), nullable=True),
        sa.Column("calculated_accuracy", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("calculated_wpm", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("calculated_hesitation_rate", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("calculated_engagement_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("engagement_formula_version", sa.String(length=32), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "row_version > 0", name=op.f("ck_reading_sessions_row_version_positive")
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_reading_sessions_request_digest_format"),
        ),
        sa.CheckConstraint(
            "completion_status IN ('completed', 'abandoned', 'interrupted')",
            name=op.f("ck_reading_sessions_completion_status_values"),
        ),
        sa.CheckConstraint(
            "task_type IN ('independent_reading', 'assisted_read_aloud', 'guided_echo_reading')",
            name=op.f("ck_reading_sessions_task_type_values"),
        ),
        sa.CheckConstraint(
            "difficulty_tier IN ('early', 'intermediate', 'advanced')",
            name=op.f("ck_reading_sessions_difficulty_tier_values"),
        ),
        sa.CheckConstraint(
            "support_mode IN ('baseline_fixed', 'adaptive', 'manual_override')",
            name=op.f("ck_reading_sessions_support_mode_values"),
        ),
        sa.CheckConstraint(
            "words_attempted >= 0", name=op.f("ck_reading_sessions_words_attempted_nonnegative")
        ),
        sa.CheckConstraint(
            "words_correct >= 0", name=op.f("ck_reading_sessions_words_correct_nonnegative")
        ),
        sa.CheckConstraint(
            "words_correct <= words_attempted",
            name=op.f("ck_reading_sessions_words_correct_le_attempted"),
        ),
        sa.CheckConstraint(
            "target_word_count >= 0",
            name=op.f("ck_reading_sessions_target_word_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "active_duration_ms >= 0",
            name=op.f("ck_reading_sessions_active_duration_ms_nonnegative"),
        ),
        sa.CheckConstraint(
            "total_duration_ms >= 0",
            name=op.f("ck_reading_sessions_total_duration_ms_nonnegative"),
        ),
        sa.CheckConstraint(
            "active_duration_ms <= total_duration_ms",
            name=op.f("ck_reading_sessions_active_duration_le_total"),
        ),
        sa.CheckConstraint(
            "total_pause_duration_ms IS NULL OR "
            "(total_pause_duration_ms >= 0 AND total_pause_duration_ms <= total_duration_ms)",
            name=op.f("ck_reading_sessions_pause_duration_bounds"),
        ),
        sa.CheckConstraint(
            "pause_count IS NULL OR pause_count >= 0",
            name=op.f("ck_reading_sessions_pause_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "hesitation_count IS NULL OR hesitation_count >= 0",
            name=op.f("ck_reading_sessions_hesitation_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "replay_count IS NULL OR replay_count >= 0",
            name=op.f("ck_reading_sessions_replay_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "session_end_time >= session_start_time",
            name=op.f("ck_reading_sessions_session_time_order"),
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_reading_sessions_learner_id_learner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reading_sessions")),
        sa.UniqueConstraint(
            "learner_id",
            "client_session_id",
            name=op.f("uq_reading_sessions_client_session"),
        ),
    )
    op.create_index(
        op.f("ix_reading_sessions_digest"),
        "reading_sessions",
        ["request_digest"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reading_sessions_document_id"),
        "reading_sessions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reading_sessions_learner_id"),
        "reading_sessions",
        ["learner_id"],
        unique=False,
    )
    op.create_index(
        "ix_reading_sessions_learner_chronological",
        "reading_sessions",
        ["learner_id", "session_start_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_reading_sessions_partition",
        "reading_sessions",
        ["learner_id", "task_type", "difficulty_tier", "support_mode", "session_start_time"],
        unique=False,
    )

    op.create_table(
        "learner_reading_support_settings",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("support_mode", sa.String(length=24), nullable=False),
        sa.Column("default_difficulty_tier", sa.String(length=20), nullable=False),
        sa.Column("enable_speech_cues", sa.Boolean(), nullable=False),
        sa.Column("speech_rate_multiplier", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("enable_syllable_assistance", sa.Boolean(), nullable=False),
        sa.Column("enable_phoneme_breakdown", sa.Boolean(), nullable=False),
        sa.Column("enable_visual_pacing", sa.Boolean(), nullable=False),
        sa.Column("visual_pacing_rate_wpm", sa.SmallInteger(), nullable=True),
        sa.Column("enable_line_focus", sa.Boolean(), nullable=False),
        sa.Column("simplification_level", sa.SmallInteger(), nullable=False),
        sa.Column("pause_threshold_ms", sa.Integer(), nullable=False),
        sa.Column("manual_override_locked", sa.Boolean(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "row_version > 0",
            name=op.f("ck_learner_reading_support_settings_row_version_positive"),
        ),
        sa.CheckConstraint(
            "support_mode IN ('baseline_fixed', 'adaptive', 'manual_override')",
            name=op.f("ck_learner_reading_support_settings_support_mode_values"),
        ),
        sa.CheckConstraint(
            "default_difficulty_tier IN ('early', 'intermediate', 'advanced')",
            name=op.f("ck_learner_reading_support_settings_default_difficulty_values"),
        ),
        sa.CheckConstraint(
            "simplification_level BETWEEN 1 AND 5",
            name=op.f("ck_learner_reading_support_settings_simplification_level_range"),
        ),
        sa.CheckConstraint(
            "speech_rate_multiplier BETWEEN 0.50 AND 2.00",
            name=op.f("ck_learner_reading_support_settings_speech_rate_multiplier_range"),
        ),
        sa.CheckConstraint(
            "visual_pacing_rate_wpm IS NULL OR visual_pacing_rate_wpm BETWEEN 20 AND 300",
            name=op.f("ck_learner_reading_support_settings_visual_pacing_rate_range"),
        ),
        sa.CheckConstraint(
            "pause_threshold_ms BETWEEN 1000 AND 10000",
            name=op.f("ck_learner_reading_support_settings_pause_threshold_range"),
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_learner_reading_support_settings_learner_id_learner_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_learner_reading_support_settings_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learner_reading_support_settings")),
        sa.UniqueConstraint(
            "learner_id",
            name=op.f("uq_learner_reading_support_settings_learner_id"),
        ),
    )
    op.create_index(
        op.f("ix_learner_reading_support_settings_updated_by_user_id"),
        "learner_reading_support_settings",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_learner_reading_support_settings_updated",
        "learner_reading_support_settings",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learner_reading_support_settings_updated",
        table_name="learner_reading_support_settings",
    )
    op.drop_index(
        op.f("ix_learner_reading_support_settings_updated_by_user_id"),
        table_name="learner_reading_support_settings",
    )
    op.drop_table("learner_reading_support_settings")

    op.drop_index("ix_reading_sessions_partition", table_name="reading_sessions")
    op.drop_index("ix_reading_sessions_learner_chronological", table_name="reading_sessions")
    op.drop_index(op.f("ix_reading_sessions_learner_id"), table_name="reading_sessions")
    op.drop_index(op.f("ix_reading_sessions_document_id"), table_name="reading_sessions")
    op.drop_index(op.f("ix_reading_sessions_digest"), table_name="reading_sessions")
    op.drop_table("reading_sessions")
