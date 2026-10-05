"""learner profiles grants and preferences

Revision ID: 0003_learner_foundation
Revises: 0002_auth_identity
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_learner_foundation"
down_revision: str | Sequence[str] | None = "0002_auth_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learner_profiles",
        sa.Column("learner_user_id", sa.Uuid(), nullable=True),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("age_band", sa.SmallInteger(), nullable=True),
        sa.Column("grade_level", sa.SmallInteger(), nullable=True),
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
            "age_band IS NULL OR age_band BETWEEN 9 AND 12",
            name=op.f("ck_learner_profiles_age_band_range"),
        ),
        sa.CheckConstraint(
            "archived_at IS NULL OR archived_at >= created_at",
            name=op.f("ck_learner_profiles_archive_order"),
        ),
        sa.CheckConstraint(
            "grade_level IS NULL OR grade_level BETWEEN 3 AND 8",
            name=op.f("ck_learner_profiles_grade_level_range"),
        ),
        sa.CheckConstraint(
            "length(btrim(display_name)) > 0",
            name=op.f("ck_learner_profiles_display_name_nonblank"),
        ),
        sa.CheckConstraint(
            "row_version > 0", name=op.f("ck_learner_profiles_row_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_learner_profiles_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_user_id"],
            ["users.id"],
            name=op.f("fk_learner_profiles_learner_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learner_profiles")),
        sa.UniqueConstraint("learner_user_id", name=op.f("uq_learner_profiles_learner_user_id")),
    )
    op.create_index(
        "ix_learner_profiles_archived_at",
        "learner_profiles",
        ["archived_at"],
        unique=False,
        postgresql_where=sa.text("archived_at IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_learner_profiles_created_by_user_id"),
        "learner_profiles",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_table(
        "educator_learner_relationships",
        sa.Column("educator_user_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("access_level", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
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
            "access_level IN ('viewer', 'instructor')",
            name=op.f("ck_educator_learner_relationships_access_values"),
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revoked_by_user_id IS NULL)",
            name=op.f("ck_educator_learner_relationships_revocation_pair"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_educator_learner_relationships_expiry_order")
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name=op.f("ck_educator_learner_relationships_revocation_order"),
        ),
        sa.CheckConstraint(
            "row_version > 0", name=op.f("ck_educator_learner_relationships_row_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["educator_user_id"],
            ["users.id"],
            name=op.f("fk_educator_learner_relationships_educator_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name=op.f("fk_educator_learner_relationships_granted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_educator_learner_relationships_learner_id_learner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_educator_learner_relationships_revoked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_educator_learner_relationships")),
    )
    op.create_index(
        "ix_educator_relationship_expiry",
        "educator_learner_relationships",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_educator_relationship_grantor",
        "educator_learner_relationships",
        ["granted_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_educator_relationship_history",
        "educator_learner_relationships",
        ["educator_user_id", "learner_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_educator_relationship_learner",
        "educator_learner_relationships",
        ["learner_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_educator_relationship_revoker",
        "educator_learner_relationships",
        ["revoked_by_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_educator_relationship_open",
        "educator_learner_relationships",
        ["educator_user_id", "learner_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "guardian_learner_relationships",
        sa.Column("guardian_user_id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("access_level", sa.String(length=16), nullable=False),
        sa.Column(
            "can_provide_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("authority_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authority_verified_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
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
            "access_level IN ('viewer', 'manager')",
            name=op.f("ck_guardian_learner_relationships_access_values"),
        ),
        sa.CheckConstraint(
            "(authority_verified_at IS NULL) = (authority_verified_by_user_id IS NULL)",
            name=op.f("ck_guardian_learner_relationships_verification_pair"),
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revoked_by_user_id IS NULL)",
            name=op.f("ck_guardian_learner_relationships_revocation_pair"),
        ),
        sa.CheckConstraint(
            "NOT can_provide_consent OR (authority_verified_at IS NOT NULL AND "
            "authority_verified_by_user_id IS NOT NULL)",
            name=op.f("ck_guardian_learner_relationships_consent_authority"),
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name=op.f("ck_guardian_learner_relationships_revocation_order"),
        ),
        sa.CheckConstraint(
            "row_version > 0", name=op.f("ck_guardian_learner_relationships_row_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["authority_verified_by_user_id"],
            ["users.id"],
            name=op.f("fk_guardian_learner_relationships_authority_verified_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name=op.f("fk_guardian_learner_relationships_granted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["guardian_user_id"],
            ["users.id"],
            name=op.f("fk_guardian_learner_relationships_guardian_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_guardian_learner_relationships_learner_id_learner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_guardian_learner_relationships_revoked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guardian_learner_relationships")),
        sa.UniqueConstraint("id", "learner_id", name="uq_guardian_relationship_scope"),
    )
    op.create_index(
        "ix_guardian_relationship_grantor",
        "guardian_learner_relationships",
        ["granted_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_guardian_relationship_history",
        "guardian_learner_relationships",
        ["guardian_user_id", "learner_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_guardian_relationship_learner",
        "guardian_learner_relationships",
        ["learner_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_guardian_relationship_revoker",
        "guardian_learner_relationships",
        ["revoked_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_guardian_relationship_verifier",
        "guardian_learner_relationships",
        ["authority_verified_by_user_id"],
        unique=False,
    )
    op.create_index(
        "uq_guardian_relationship_open",
        "guardian_learner_relationships",
        ["guardian_user_id", "learner_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "learner_preferences",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("preferred_language_tag", sa.String(length=35), nullable=True),
        sa.Column("text_scale", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("line_spacing", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("theme", sa.String(length=20), nullable=True),
        sa.Column("reduce_motion", sa.Boolean(), nullable=True),
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
            "theme IS NULL OR theme IN ('system', 'light', 'dark', 'high_contrast')",
            name=op.f("ck_learner_preferences_theme_values"),
        ),
        sa.CheckConstraint(
            "line_spacing IS NULL OR line_spacing BETWEEN 1.00 AND 3.00",
            name=op.f("ck_learner_preferences_line_spacing_range"),
        ),
        sa.CheckConstraint(
            "preferred_language_tag IS NULL OR length(btrim(preferred_language_tag)) > 0",
            name=op.f("ck_learner_preferences_language_nonblank"),
        ),
        sa.CheckConstraint(
            "row_version > 0", name=op.f("ck_learner_preferences_row_version_positive")
        ),
        sa.CheckConstraint(
            "text_scale IS NULL OR text_scale BETWEEN 0.75 AND 3.00",
            name=op.f("ck_learner_preferences_text_scale_range"),
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_learner_preferences_learner_id_learner_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_learner_preferences_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learner_preferences")),
        sa.UniqueConstraint("learner_id", name=op.f("uq_learner_preferences_learner_id")),
    )
    op.create_index(
        op.f("ix_learner_preferences_updated_by_user_id"),
        "learner_preferences",
        ["updated_by_user_id"],
        unique=False,
    )

    op.execute("""
        CREATE FUNCTION protect_learner_profiles_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
            THEN
                RAISE EXCEPTION 'Historical identity fields cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_learner_profiles_history BEFORE UPDATE ON learner_profiles
        FOR EACH ROW EXECUTE FUNCTION protect_learner_profiles_history();
    """)
    op.execute("""
        CREATE FUNCTION protect_guardian_learner_relationships_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.guardian_user_id IS DISTINCT FROM OLD.guardian_user_id
                OR NEW.learner_id IS DISTINCT FROM OLD.learner_id
                OR NEW.access_level IS DISTINCT FROM OLD.access_level
                OR NEW.can_provide_consent IS DISTINCT FROM OLD.can_provide_consent
                OR NEW.authority_verified_at IS DISTINCT FROM OLD.authority_verified_at
                OR NEW.authority_verified_by_user_id
                    IS DISTINCT FROM OLD.authority_verified_by_user_id
                OR NEW.granted_by_user_id IS DISTINCT FROM OLD.granted_by_user_id
                OR (OLD.revoked_at IS NOT NULL
                AND (NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
                OR NEW.revoked_by_user_id IS DISTINCT FROM OLD.revoked_by_user_id))
            THEN
                RAISE EXCEPTION 'Historical identity fields cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_guardian_learner_relationships_history
        BEFORE UPDATE ON guardian_learner_relationships
        FOR EACH ROW EXECUTE FUNCTION protect_guardian_learner_relationships_history();
    """)
    op.execute("""
        CREATE FUNCTION protect_educator_learner_relationships_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.educator_user_id IS DISTINCT FROM OLD.educator_user_id
                OR NEW.learner_id IS DISTINCT FROM OLD.learner_id
                OR NEW.access_level IS DISTINCT FROM OLD.access_level
                OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
                OR NEW.granted_by_user_id IS DISTINCT FROM OLD.granted_by_user_id
                OR (OLD.revoked_at IS NOT NULL
                AND (NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
                OR NEW.revoked_by_user_id IS DISTINCT FROM OLD.revoked_by_user_id))
            THEN
                RAISE EXCEPTION 'Historical identity fields cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_educator_learner_relationships_history
        BEFORE UPDATE ON educator_learner_relationships
        FOR EACH ROW EXECUTE FUNCTION protect_educator_learner_relationships_history();
    """)
    op.execute("""
        CREATE FUNCTION protect_learner_preferences_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.learner_id IS DISTINCT FROM OLD.learner_id
            THEN
                RAISE EXCEPTION 'Historical identity fields cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_learner_preferences_history BEFORE UPDATE ON learner_preferences
        FOR EACH ROW EXECUTE FUNCTION protect_learner_preferences_history();
    """)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_learner_preferences_updated_by_user_id"), table_name="learner_preferences"
    )
    op.drop_table("learner_preferences")
    op.drop_index(
        "uq_guardian_relationship_open",
        table_name="guardian_learner_relationships",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_index("ix_guardian_relationship_verifier", table_name="guardian_learner_relationships")
    op.drop_index("ix_guardian_relationship_revoker", table_name="guardian_learner_relationships")
    op.drop_index("ix_guardian_relationship_learner", table_name="guardian_learner_relationships")
    op.drop_index("ix_guardian_relationship_history", table_name="guardian_learner_relationships")
    op.drop_index("ix_guardian_relationship_grantor", table_name="guardian_learner_relationships")
    op.drop_table("guardian_learner_relationships")
    op.drop_index(
        "uq_educator_relationship_open",
        table_name="educator_learner_relationships",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_index("ix_educator_relationship_revoker", table_name="educator_learner_relationships")
    op.drop_index("ix_educator_relationship_learner", table_name="educator_learner_relationships")
    op.drop_index("ix_educator_relationship_history", table_name="educator_learner_relationships")
    op.drop_index("ix_educator_relationship_grantor", table_name="educator_learner_relationships")
    op.drop_index(
        "ix_educator_relationship_expiry",
        table_name="educator_learner_relationships",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_table("educator_learner_relationships")
    op.drop_index(op.f("ix_learner_profiles_created_by_user_id"), table_name="learner_profiles")
    op.drop_index(
        "ix_learner_profiles_archived_at",
        table_name="learner_profiles",
        postgresql_where=sa.text("archived_at IS NOT NULL"),
    )
    op.drop_table("learner_profiles")

    op.execute("DROP FUNCTION protect_learner_preferences_history()")
    op.execute("DROP FUNCTION protect_educator_learner_relationships_history()")
    op.execute("DROP FUNCTION protect_guardian_learner_relationships_history()")
    op.execute("DROP FUNCTION protect_learner_profiles_history()")
