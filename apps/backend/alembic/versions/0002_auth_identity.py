"""auth identity and role grants

Revision ID: 0002_auth_identity
Revises: 0001_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_auth_identity"
down_revision: str | Sequence[str] | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=160), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            "code IN ('guardian', 'educator', 'learner', 'administrator')",
            name=op.f("ck_roles_code_values"),
        ),
        sa.CheckConstraint(
            "length(btrim(description)) > 0", name=op.f("ck_roles_description_nonblank")
        ),
        sa.CheckConstraint("row_version > 0", name=op.f("ck_roles_row_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("code", name=op.f("uq_roles_code")),
    )
    op.create_table(
        "users",
        sa.Column("login_handle", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="disabled", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
            "login_handle IS NULL OR login_handle ~ '^[a-z0-9][a-z0-9._-]{2,63}$'",
            name=op.f("ck_users_handle_format"),
        ),
        sa.CheckConstraint(
            "status <> 'active' OR (password_hash IS NOT NULL AND deleted_at IS NULL)",
            name=op.f("ck_users_active_credentials"),
        ),
        sa.CheckConstraint(
            "status <> 'anonymized' OR (deleted_at IS NOT NULL AND login_handle IS NULL AND"
            " email IS NULL AND email_verified_at IS NULL AND password_hash IS NULL)",
            name=op.f("ck_users_anonymized_fields"),
        ),
        sa.CheckConstraint(
            "status = 'anonymized' OR login_handle IS NOT NULL",
            name=op.f("ck_users_handle_required"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'anonymized')", name=op.f("ck_users_status_values")
        ),
        sa.CheckConstraint(
            "email IS NULL OR (length(btrim(email)) > 0 AND email = lower(btrim(email)))",
            name=op.f("ck_users_email_normalized"),
        ),
        sa.CheckConstraint(
            "email_verified_at IS NULL OR email IS NOT NULL",
            name=op.f("ck_users_email_verification"),
        ),
        sa.CheckConstraint(
            "password_hash IS NULL OR length(btrim(password_hash)) > 0",
            name=op.f("ck_users_password_nonblank"),
        ),
        sa.CheckConstraint("row_version > 0", name=op.f("ck_users_row_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("login_handle", name=op.f("uq_users_login_handle")),
    )
    op.create_index(
        "ix_users_deleted_at",
        "users",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
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
            "(revoked_at IS NULL) = (revoked_by_user_id IS NULL)",
            name=op.f("ck_user_roles_revocation_pair"),
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name=op.f("ck_user_roles_revocation_order"),
        ),
        sa.CheckConstraint("row_version > 0", name=op.f("ck_user_roles_row_version_positive")),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_granted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_revoked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_user_roles_role_id_roles"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
    )
    op.create_index(
        op.f("ix_user_roles_granted_by_user_id"), "user_roles", ["granted_by_user_id"], unique=False
    )
    op.create_index(
        "ix_user_roles_history",
        "user_roles",
        ["user_id", "role_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_roles_revoked_by_user_id"), "user_roles", ["revoked_by_user_id"], unique=False
    )
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False)
    op.create_index(
        "uq_user_roles_open",
        "user_roles",
        ["user_id", "role_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.execute("""
        INSERT INTO roles (id, code, description) VALUES
        ('0e9e6303-f2a6-40cc-b881-d3a177c1ddc1', 'guardian', 'Learner-specific guardian access'),
        ('b2d9412e-25a2-4a24-83e1-6ce762f68b37', 'educator', 'Learner-specific educator access'),
        ('c960e341-af01-4cee-a2c3-ad8fbb876893', 'learner', 'Personal learner access'),
        ('9d7a05bf-f7ca-4ca5-857f-7474a2ec0d11', 'administrator',
            'Explicit administrative capabilities')
    """)
    op.execute("""
        CREATE FUNCTION protect_users_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'Historical identity fields cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_users_history BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION protect_users_history();
    """)
    op.execute("""
        CREATE FUNCTION protect_roles_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.code IS DISTINCT FROM OLD.code
            THEN
                RAISE EXCEPTION 'Historical identity fields cannot be rewritten'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_roles_history BEFORE UPDATE ON roles
        FOR EACH ROW EXECUTE FUNCTION protect_roles_history();
    """)
    op.execute("""
        CREATE FUNCTION protect_user_roles_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.user_id IS DISTINCT FROM OLD.user_id
                OR NEW.role_id IS DISTINCT FROM OLD.role_id
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
        CREATE TRIGGER trg_user_roles_history BEFORE UPDATE ON user_roles
        FOR EACH ROW EXECUTE FUNCTION protect_user_roles_history();
    """)


def downgrade() -> None:
    op.drop_index(
        "uq_user_roles_open",
        table_name="user_roles",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles")
    op.drop_index(op.f("ix_user_roles_revoked_by_user_id"), table_name="user_roles")
    op.drop_index("ix_user_roles_history", table_name="user_roles")
    op.drop_index(op.f("ix_user_roles_granted_by_user_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index(
        "ix_users_deleted_at",
        table_name="users",
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )
    op.drop_table("users")
    op.drop_table("roles")

    op.execute("DROP FUNCTION protect_user_roles_history()")
    op.execute("DROP FUNCTION protect_users_history()")
    op.execute("DROP FUNCTION protect_roles_history()")
