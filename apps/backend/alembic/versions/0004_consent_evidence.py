"""versioned notices and append only consent

Revision ID: 0004_consent_evidence
Revises: 0003_learner_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_consent_evidence"
down_revision: str | Sequence[str] | None = "0003_learner_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consent_notice_versions",
        sa.Column("purpose_code", sa.String(length=40), nullable=False),
        sa.Column("record_kind", sa.String(length=20), nullable=False),
        sa.Column("version_label", sa.String(length=32), nullable=False),
        sa.Column("language_tag", sa.String(length=35), nullable=False),
        sa.Column("notice_text", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by_user_id", sa.Uuid(), nullable=True),
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
            "content_sha256 = encode(sha256(convert_to(notice_text, 'UTF8')), 'hex')",
            name=op.f("ck_consent_notice_versions_digest_matches_content"),
        ),
        sa.CheckConstraint(
            "content_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_consent_notice_versions_digest_format"),
        ),
        sa.CheckConstraint(
            "purpose_code IN ('learning_support', 'research_participation', 'audio_retention')",
            name=op.f("ck_consent_notice_versions_purpose_values"),
        ),
        sa.CheckConstraint(
            "record_kind IN ('guardian_consent', 'learner_assent')",
            name=op.f("ck_consent_notice_versions_kind_values"),
        ),
        sa.CheckConstraint(
            "(retired_at IS NULL) = (retired_by_user_id IS NULL)",
            name=op.f("ck_consent_notice_versions_retirement_pair"),
        ),
        sa.CheckConstraint(
            "length(btrim(language_tag)) > 0",
            name=op.f("ck_consent_notice_versions_language_nonblank"),
        ),
        sa.CheckConstraint(
            "length(btrim(notice_text)) > 0",
            name=op.f("ck_consent_notice_versions_notice_nonblank"),
        ),
        sa.CheckConstraint(
            "length(btrim(version_label)) > 0",
            name=op.f("ck_consent_notice_versions_version_nonblank"),
        ),
        sa.CheckConstraint(
            "retired_at IS NULL OR retired_at >= published_at",
            name=op.f("ck_consent_notice_versions_retirement_order"),
        ),
        sa.CheckConstraint(
            "row_version > 0", name=op.f("ck_consent_notice_versions_row_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            name=op.f("fk_consent_notice_versions_published_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retired_by_user_id"],
            ["users.id"],
            name=op.f("fk_consent_notice_versions_retired_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_notice_versions")),
        sa.UniqueConstraint("id", "purpose_code", "record_kind", name="uq_consent_notice_scope"),
        sa.UniqueConstraint(
            "purpose_code",
            "record_kind",
            "version_label",
            "language_tag",
            name="uq_consent_notice_version_language",
        ),
    )
    op.create_index(
        op.f("ix_consent_notice_versions_published_by_user_id"),
        "consent_notice_versions",
        ["published_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consent_notice_versions_retired_by_user_id"),
        "consent_notice_versions",
        ["retired_by_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_consent_notice_current",
        "consent_notice_versions",
        ["purpose_code", "record_kind", "language_tag"],
        unique=True,
        postgresql_where=sa.text("retired_at IS NULL"),
    )
    op.create_table(
        "consent_records",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("notice_version_id", sa.Uuid(), nullable=False),
        sa.Column("purpose_code", sa.String(length=40), nullable=False),
        sa.Column("record_kind", sa.String(length=20), nullable=False),
        sa.Column("guardian_relationship_id", sa.Uuid(), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("sequence_no", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("capture_method", sa.String(length=24), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(record_kind = 'guardian_consent' AND guardian_relationship_id IS NOT NULL) OR"
            " (record_kind = 'learner_assent' AND guardian_relationship_id IS NULL)",
            name=op.f("ck_consent_records_respondent_scope"),
        ),
        sa.CheckConstraint(
            "capture_method IN ('self_service', 'assisted_in_person')",
            name=op.f("ck_consent_records_capture_method_values"),
        ),
        sa.CheckConstraint(
            "decision IN ('granted', 'declined', 'withdrawn')",
            name=op.f("ck_consent_records_decision_values"),
        ),
        sa.CheckConstraint(
            "occurred_at <= recorded_at", name=op.f("ck_consent_records_recording_order")
        ),
        sa.CheckConstraint("sequence_no > 0", name=op.f("ck_consent_records_sequence_positive")),
        sa.ForeignKeyConstraint(
            ["guardian_relationship_id", "learner_id"],
            ["guardian_learner_relationships.id", "guardian_learner_relationships.learner_id"],
            name="fk_consent_record_guardian_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_consent_records_learner_id_learner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["notice_version_id", "purpose_code", "record_kind"],
            [
                "consent_notice_versions.id",
                "consent_notice_versions.purpose_code",
                "consent_notice_versions.record_kind",
            ],
            name="fk_consent_record_notice_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_consent_records_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_records")),
        sa.UniqueConstraint(
            "learner_id",
            "purpose_code",
            "record_kind",
            "guardian_relationship_id",
            "sequence_no",
            name="uq_consent_record_stream_sequence",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_consent_record_learner_history",
        "consent_records",
        ["learner_id", sa.literal_column("recorded_at DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_consent_records_guardian_relationship_id"),
        "consent_records",
        ["guardian_relationship_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consent_records_notice_version_id"),
        "consent_records",
        ["notice_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consent_records_recorded_by_user_id"),
        "consent_records",
        ["recorded_by_user_id"],
        unique=False,
    )

    op.execute("""
        CREATE FUNCTION protect_consent_notice_versions_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF (OLD.retired_at IS NOT NULL
                AND (NEW.retired_at IS DISTINCT FROM OLD.retired_at
                OR NEW.retired_by_user_id IS DISTINCT FROM OLD.retired_by_user_id))
                OR NEW.id IS DISTINCT FROM OLD.id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.purpose_code IS DISTINCT FROM OLD.purpose_code
                OR NEW.record_kind IS DISTINCT FROM OLD.record_kind
                OR NEW.version_label IS DISTINCT FROM OLD.version_label
                OR NEW.language_tag IS DISTINCT FROM OLD.language_tag
                OR NEW.notice_text IS DISTINCT FROM OLD.notice_text
                OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256
                OR NEW.published_at IS DISTINCT FROM OLD.published_at
                OR NEW.published_by_user_id IS DISTINCT FROM OLD.published_by_user_id
            THEN
                RAISE EXCEPTION 'Historical identity fields cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_consent_notice_versions_history BEFORE UPDATE ON consent_notice_versions
        FOR EACH ROW EXECUTE FUNCTION protect_consent_notice_versions_history();
    """)
    op.execute("""
        CREATE FUNCTION protect_consent_records_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Consent records are append-only; use an authorized retention process'
                USING ERRCODE = '23514';
        END;
        $$;
        CREATE TRIGGER trg_consent_records_history BEFORE UPDATE OR DELETE ON consent_records
        FOR EACH ROW EXECUTE FUNCTION protect_consent_records_history();
        CREATE TRIGGER trg_consent_records_no_truncate BEFORE TRUNCATE ON consent_records
        FOR EACH STATEMENT EXECUTE FUNCTION protect_consent_records_history();
    """)


def downgrade() -> None:
    op.drop_index(op.f("ix_consent_records_recorded_by_user_id"), table_name="consent_records")
    op.drop_index(op.f("ix_consent_records_notice_version_id"), table_name="consent_records")
    op.drop_index(op.f("ix_consent_records_guardian_relationship_id"), table_name="consent_records")
    op.drop_index("ix_consent_record_learner_history", table_name="consent_records")
    op.drop_table("consent_records")
    op.drop_index(
        "uq_consent_notice_current",
        table_name="consent_notice_versions",
        postgresql_where=sa.text("retired_at IS NULL"),
    )
    op.drop_index(
        op.f("ix_consent_notice_versions_retired_by_user_id"), table_name="consent_notice_versions"
    )
    op.drop_index(
        op.f("ix_consent_notice_versions_published_by_user_id"),
        table_name="consent_notice_versions",
    )
    op.drop_table("consent_notice_versions")

    op.execute("DROP FUNCTION protect_consent_records_history()")
    op.execute("DROP FUNCTION protect_consent_notice_versions_history()")
