"""Append-only synthetic PP1 sample records. No fixture or account seed."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008_c4_pp1_saved"
down_revision = "0007_c4_pp1_demo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "component4_pp1_saved_sessions",
        sa.Column("id", sa.Uuid(), nullable=False, primary_key=True),
        sa.Column(
            "account_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("sample_session_id", sa.Uuid(), nullable=False),
        sa.Column("fixture_version", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("measurements", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("account_id", "sequence", name="uq_pp1_saved_account_sequence"),
        sa.UniqueConstraint("account_id", "sample_session_id", name="uq_pp1_saved_account_sample"),
        sa.CheckConstraint(
            "sequence BETWEEN 1 AND 6",
            name=op.f("ck_component4_pp1_saved_sessions_sample_sequence"),
        ),
        sa.CheckConstraint(
            "fixture_version = 1", name=op.f("ck_component4_pp1_saved_sessions_fixture_version")
        ),
        sa.CheckConstraint(
            "source_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_component4_pp1_saved_sessions_source_digest"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(measurements) = 'object'",
            name=op.f("ck_component4_pp1_saved_sessions_measurement_object"),
        ),
    )


def downgrade() -> None:
    op.drop_table("component4_pp1_saved_sessions")
