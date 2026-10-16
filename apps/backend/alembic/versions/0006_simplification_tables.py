"""simplification tables

Revision ID: 0006_simplification_tables
Revises: 0005_auth_sessions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_simplification_tables"
down_revision: str | Sequence[str] | None = "0005_auth_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simplification_sessions",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("source_text_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("source_length", sa.Integer(), nullable=False),
        sa.Column("source_difficulty", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("strategy_applied", sa.String(length=24), nullable=False),
        sa.Column("target_reading_level", sa.String(length=16), nullable=False),
        sa.Column("adaptation_attempt", sa.SmallInteger(), nullable=False),
        sa.Column("simplified_text", sa.Text(), nullable=False),
        sa.Column("output_length", sa.Integer(), nullable=False),
        sa.Column("output_difficulty", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("concepts_preserved", sa.Boolean(), nullable=True),
        sa.Column(
            "validation_warnings",
            sa.ARRAY(sa.String()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("ai_provider", sa.String(length=40), nullable=False),
        sa.Column("ai_latency_ms", sa.Integer(), nullable=False),
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
            "adaptation_attempt BETWEEN 1 AND 10",
            name=op.f("ck_simplification_sessions_adaptation_attempt_range"),
        ),
        sa.CheckConstraint(
            "length(source_text_sha256) = 64",
            name=op.f("ck_simplification_sessions_source_text_sha256_length"),
        ),
        sa.CheckConstraint(
            "output_difficulty IS NULL OR "
            "(output_difficulty >= 0.00 AND output_difficulty <= 1.00)",
            name=op.f("ck_simplification_sessions_output_difficulty_range"),
        ),
        sa.CheckConstraint(
            "output_length > 0",
            name=op.f("ck_simplification_sessions_output_length_positive"),
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name=op.f("ck_simplification_sessions_row_version_positive"),
        ),
        sa.CheckConstraint(
            "source_difficulty IS NULL OR "
            "(source_difficulty >= 0.00 AND source_difficulty <= 1.00)",
            name=op.f("ck_simplification_sessions_source_difficulty_range"),
        ),
        sa.CheckConstraint(
            "source_length > 0",
            name=op.f("ck_simplification_sessions_source_length_positive"),
        ),
        sa.CheckConstraint(
            "strategy_applied IN ("
            "'vocabulary_swap', 'sentence_split', 'concept_reduction', 'full_rewrite', 'combined'"
            ")",
            name=op.f("ck_simplification_sessions_strategy_applied_values"),
        ),
        sa.CheckConstraint(
            "target_reading_level IN ('beginner', 'elementary', 'intermediate', 'advanced')",
            name=op.f("ck_simplification_sessions_target_reading_level_values"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_simplification_sessions_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_simplification_sessions_learner_id_learner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simplification_sessions")),
    )
    op.create_index(
        op.f("ix_simplification_sessions_actor_user_id"),
        "simplification_sessions",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_simplification_sessions_document_id",
        "simplification_sessions",
        ["document_id"],
        unique=False,
        postgresql_where=sa.text("document_id IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_simplification_sessions_learner_id"),
        "simplification_sessions",
        ["learner_id"],
        unique=False,
    )
    op.create_index(
        "ix_simplification_sessions_learner_history",
        "simplification_sessions",
        ["learner_id", sa.text("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "simplification_vocabulary",
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("term", sa.String(length=200), nullable=False),
        sa.Column("simplified_definition", sa.Text(), nullable=False),
        sa.Column("example_sentence", sa.Text(), nullable=True),
        sa.Column(
            "synonyms",
            sa.ARRAY(sa.String()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("language_tag", sa.String(length=35), nullable=False),
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
            "length(btrim(language_tag)) > 0",
            name=op.f("ck_simplification_vocabulary_language_tag_nonblank"),
        ),
        sa.CheckConstraint(
            "length(btrim(term)) > 0",
            name=op.f("ck_simplification_vocabulary_term_nonblank"),
        ),
        sa.CheckConstraint(
            "row_version > 0",
            name=op.f("ck_simplification_vocabulary_row_version_positive"),
        ),
        sa.CheckConstraint(
            "source IN ('automatic', 'user')",
            name=op.f("ck_simplification_vocabulary_source_values"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["simplification_sessions.id"],
            name=op.f("fk_simplification_vocabulary_session_id_simplification_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simplification_vocabulary")),
    )
    op.create_index(
        "ix_simplification_vocabulary_session_id",
        "simplification_vocabulary",
        ["session_id"],
        unique=False,
    )

    op.create_table(
        "simplification_feedback",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_signal", sa.String(length=16), nullable=False),
        sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
        sa.Column("vocabulary_lookups_count", sa.SmallInteger(), nullable=True),
        sa.Column("completed_reading", sa.Boolean(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "feedback_signal IN ('too_hard', 'too_easy', 'just_right', 'skipped')",
            name=op.f("ck_simplification_feedback_feedback_signal_values"),
        ),
        sa.CheckConstraint(
            "occurred_at <= recorded_at",
            name=op.f("ck_simplification_feedback_recording_order"),
        ),
        sa.CheckConstraint(
            "time_spent_seconds IS NULL OR "
            "(time_spent_seconds >= 0 AND time_spent_seconds <= 7200)",
            name=op.f("ck_simplification_feedback_time_spent_seconds_range"),
        ),
        sa.CheckConstraint(
            "vocabulary_lookups_count IS NULL OR "
            "(vocabulary_lookups_count >= 0 AND vocabulary_lookups_count <= 100)",
            name=op.f("ck_simplification_feedback_vocabulary_lookups_count_range"),
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_simplification_feedback_learner_id_learner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_simplification_feedback_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["simplification_sessions.id"],
            name=op.f("fk_simplification_feedback_session_id_simplification_sessions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simplification_feedback")),
    )
    op.create_index(
        op.f("ix_simplification_feedback_learner_id"),
        "simplification_feedback",
        ["learner_id"],
        unique=False,
    )
    op.create_index(
        "ix_simplification_feedback_learner_history",
        "simplification_feedback",
        ["learner_id", sa.text("recorded_at DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_simplification_feedback_recorded_by_user_id"),
        "simplification_feedback",
        ["recorded_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_simplification_feedback_session_id",
        "simplification_feedback",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_simplification_feedback_session_id",
        table_name="simplification_feedback",
    )
    op.drop_index(
        op.f("ix_simplification_feedback_recorded_by_user_id"),
        table_name="simplification_feedback",
    )
    op.drop_index(
        "ix_simplification_feedback_learner_history",
        table_name="simplification_feedback",
    )
    op.drop_index(
        op.f("ix_simplification_feedback_learner_id"),
        table_name="simplification_feedback",
    )
    op.drop_table("simplification_feedback")

    op.drop_index(
        "ix_simplification_vocabulary_session_id",
        table_name="simplification_vocabulary",
    )
    op.drop_table("simplification_vocabulary")

    op.drop_index(
        "ix_simplification_sessions_learner_history",
        table_name="simplification_sessions",
    )
    op.drop_index(
        op.f("ix_simplification_sessions_learner_id"),
        table_name="simplification_sessions",
    )
    op.drop_index(
        "ix_simplification_sessions_document_id",
        table_name="simplification_sessions",
        postgresql_where=sa.text("document_id IS NOT NULL"),
    )
    op.drop_index(
        op.f("ix_simplification_sessions_actor_user_id"),
        table_name="simplification_sessions",
    )
    op.drop_table("simplification_sessions")
