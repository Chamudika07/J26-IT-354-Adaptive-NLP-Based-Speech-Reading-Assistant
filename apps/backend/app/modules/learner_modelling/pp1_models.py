"""Fictional PP1-only storage, separate from learner telemetry and consent."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    and_,
    case,
    column,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class Pp1DemoDataset(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "component4_pp1_demo_datasets"
    __table_args__ = (
        CheckConstraint("dataset_key = 'pp1-six-session-journey'", name="fixed_dataset"),
        CheckConstraint("fixture_version = 1", name="supported_version"),
        CheckConstraint("source_digest ~ '^[0-9a-f]{64}$'", name="digest_format"),
        CheckConstraint(
            and_(
                func.jsonb_typeof(column("source_payload", JSONB)) == "object",
                column("source_payload", JSONB).contains(
                    func.jsonb_build_object(
                        "version", 2, "synthetic", True, "verifiedTelemetry", False
                    )
                ),
                case(
                    (
                        func.jsonb_typeof(column("source_payload", JSONB)["records"]) == "array",
                        func.jsonb_array_length(column("source_payload", JSONB)["records"]) == 6,
                    ),
                    else_=False,
                ),
            ),
            name="six_fictional_sessions",
        ),
        CheckConstraint(
            and_(
                func.jsonb_typeof(column("provenance", JSONB)) == "object",
                column("provenance", JSONB).contains(
                    func.jsonb_build_object(
                        "synthetic",
                        True,
                        "fixture",
                        "pp1_fixture.json",
                        "generator",
                        "component4-python-engines-v1",
                    )
                ),
            ),
            name="fictional_provenance",
        ),
    )
    dataset_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    fixture_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Pp1SavedSession(UUIDPrimaryKeyMixin, Base):
    """Append-only fictional measurements; never authoritative learner telemetry."""

    __tablename__ = "component4_pp1_saved_sessions"
    __table_args__ = (
        UniqueConstraint("account_id", "sequence", name="uq_pp1_saved_account_sequence"),
        UniqueConstraint("account_id", "sample_session_id", name="uq_pp1_saved_account_sample"),
        CheckConstraint("sequence BETWEEN 1 AND 6", name="sample_sequence"),
        CheckConstraint("fixture_version = 1", name="fixture_version"),
        CheckConstraint("source_digest ~ '^[0-9a-f]{64}$'", name="source_digest"),
        CheckConstraint("jsonb_typeof(measurements) = 'object'", name="measurement_object"),
    )
    account_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_session_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    fixture_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
