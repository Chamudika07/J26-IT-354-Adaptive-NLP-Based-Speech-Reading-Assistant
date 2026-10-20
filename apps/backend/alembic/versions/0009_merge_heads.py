"""merge Component 2 and reading-material migration heads

Revision ID: 0009_merge_heads
Revises: 0006_simplification_tables, 0008_pdf_text_extraction
"""

from collections.abc import Sequence

revision: str = "0009_merge_heads"
down_revision: str | Sequence[str] | None = (
    "0006_simplification_tables",
    "0008_pdf_text_extraction",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two schema histories without additional DDL."""


def downgrade() -> None:
    """Split back to the two parent revisions without additional DDL."""
