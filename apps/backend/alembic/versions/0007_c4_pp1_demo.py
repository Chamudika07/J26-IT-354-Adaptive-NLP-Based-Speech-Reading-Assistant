"""Component 4 fictional PP1 dataset storage only; never seeds data."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_c4_pp1_demo"
down_revision = "0006_learner_reading_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "component4_pp1_demo_datasets",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("dataset_key", sa.String(64), nullable=False),
        sa.Column("fixture_version", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("source_payload", postgresql.JSONB(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("dataset_key", name="uq_component4_pp1_demo_datasets_dataset_key"),
        sa.CheckConstraint(
            "dataset_key = 'pp1-six-session-journey'",
            name=op.f("ck_component4_pp1_demo_datasets_fixed_dataset"),
        ),
        sa.CheckConstraint(
            "fixture_version = 1",
            name=op.f("ck_component4_pp1_demo_datasets_supported_version"),
        ),
        sa.CheckConstraint(
            "source_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_component4_pp1_demo_datasets_digest_format"),
        ),
        sa.CheckConstraint(
            sa.and_(
                sa.func.jsonb_typeof(sa.column("source_payload", postgresql.JSONB)) == "object",
                sa.column("source_payload", postgresql.JSONB).contains(
                    sa.func.jsonb_build_object(
                        "version", 2, "synthetic", True, "verifiedTelemetry", False
                    )
                ),
                sa.case(
                    (
                        sa.func.jsonb_typeof(
                            sa.column("source_payload", postgresql.JSONB)["records"]
                        )
                        == "array",
                        sa.func.jsonb_array_length(
                            sa.column("source_payload", postgresql.JSONB)["records"]
                        )
                        == 6,
                    ),
                    else_=False,
                ),
            ),
            name=op.f("ck_component4_pp1_demo_datasets_six_fictional_sessions"),
        ),
        sa.CheckConstraint(
            sa.and_(
                sa.func.jsonb_typeof(sa.column("provenance", postgresql.JSONB)) == "object",
                sa.column("provenance", postgresql.JSONB).contains(
                    sa.func.jsonb_build_object(
                        "synthetic",
                        True,
                        "fixture",
                        "pp1_fixture.json",
                        "generator",
                        "component4-python-engines-v1",
                    )
                ),
            ),
            name=op.f("ck_component4_pp1_demo_datasets_fictional_provenance"),
        ),
    )


def downgrade() -> None:
    op.drop_table("component4_pp1_demo_datasets")
