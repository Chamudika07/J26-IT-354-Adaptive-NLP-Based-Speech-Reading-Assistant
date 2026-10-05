"""auth sessions

Revision ID: 0005_auth_sessions
Revises: 0004_consent_evidence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_auth_sessions"
down_revision: str | Sequence[str] | None = "0004_consent_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=24), nullable=True),
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
            "revocation_reason IS NULL OR revocation_reason IN "
            "('logout', 'replay', 'account_security')",
            name=op.f("ck_auth_sessions_reason_values"),
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revocation_reason IS NULL)",
            name=op.f("ck_auth_sessions_revocation_pair"),
        ),
        sa.CheckConstraint(
            "authenticated_at <= created_at", name=op.f("ck_auth_sessions_authentication_order")
        ),
        sa.CheckConstraint("expires_at > created_at", name=op.f("ck_auth_sessions_expiry_order")),
        sa.CheckConstraint(
            "idle_expires_at > created_at AND idle_expires_at <= expires_at",
            name=op.f("ck_auth_sessions_idle_order"),
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name=op.f("ck_auth_sessions_revocation_order"),
        ),
        sa.CheckConstraint("row_version > 0", name=op.f("ck_auth_sessions_row_version_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
    )
    op.create_index(
        "ix_auth_sessions_active_user",
        "auth_sessions",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], unique=False)
    op.create_index(
        "ix_auth_sessions_idle_expires_at", "auth_sessions", ["idle_expires_at"], unique=False
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name=op.f("ck_auth_refresh_tokens_consumption_order"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_auth_refresh_tokens_expiry_order")
        ),
        sa.CheckConstraint(
            "generation >= 0", name=op.f("ck_auth_refresh_tokens_generation_nonnegative")
        ),
        sa.CheckConstraint(
            "octet_length(token_digest) = 32", name=op.f("ck_auth_refresh_tokens_digest_length")
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["auth_sessions.id"],
            name=op.f("fk_auth_refresh_tokens_session_id_auth_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_refresh_tokens")),
        sa.UniqueConstraint("session_id", "generation", name="uq_auth_refresh_tokens_generation"),
        sa.UniqueConstraint("token_digest", name=op.f("uq_auth_refresh_tokens_token_digest")),
    )
    op.create_index(
        "uq_auth_refresh_tokens_current",
        "auth_refresh_tokens",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_auth_refresh_tokens_current",
        table_name="auth_refresh_tokens",
        postgresql_where=sa.text("consumed_at IS NULL"),
    )
    op.drop_table("auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_idle_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index(
        "ix_auth_sessions_active_user",
        table_name="auth_sessions",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_table("auth_sessions")
