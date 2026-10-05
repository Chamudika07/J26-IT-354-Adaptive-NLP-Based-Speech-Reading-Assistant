"""Learner identities, explicit access grants, preferences, and consent evidence."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class LearnerProfile(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "learner_profiles"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("length(btrim(display_name)) > 0", name="display_name_nonblank"),
        CheckConstraint("archived_at IS NULL OR archived_at >= created_at", name="archive_order"),
        CheckConstraint("age_band IS NULL OR age_band BETWEEN 9 AND 12", name="age_band_range"),
        CheckConstraint(
            "grade_level IS NULL OR grade_level BETWEEN 3 AND 8", name="grade_level_range"
        ),
        Index(
            "ix_learner_profiles_archived_at",
            "archived_at",
            postgresql_where=text("archived_at IS NOT NULL"),
        ),
    )

    learner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    display_name: Mapped[str] = mapped_column(String(80))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    age_band: Mapped[int | None] = mapped_column(SmallInteger)
    grade_level: Mapped[int | None] = mapped_column(SmallInteger)


class GuardianLearnerRelationship(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "guardian_learner_relationships"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("access_level IN ('viewer', 'manager')", name="access_values"),
        CheckConstraint(
            "(authority_verified_at IS NULL) = (authority_verified_by_user_id IS NULL)",
            name="verification_pair",
        ),
        CheckConstraint(
            "NOT can_provide_consent OR (authority_verified_at IS NOT NULL "
            "AND authority_verified_by_user_id IS NOT NULL)",
            name="consent_authority",
        ),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoked_by_user_id IS NULL)", name="revocation_pair"
        ),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="revocation_order"),
        UniqueConstraint("id", "learner_id", name="uq_guardian_relationship_scope"),
        Index(
            "uq_guardian_relationship_open",
            "guardian_user_id",
            "learner_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_guardian_relationship_history",
            "guardian_user_id",
            "learner_id",
            text("created_at DESC"),
        ),
        Index("ix_guardian_relationship_learner", "learner_id", text("created_at DESC")),
        Index("ix_guardian_relationship_grantor", "granted_by_user_id"),
        Index("ix_guardian_relationship_verifier", "authority_verified_by_user_id"),
        Index("ix_guardian_relationship_revoker", "revoked_by_user_id"),
    )

    guardian_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learner_profiles.id", ondelete="RESTRICT")
    )
    access_level: Mapped[str] = mapped_column(String(16))
    can_provide_consent: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    authority_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authority_verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class EducatorLearnerRelationship(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "educator_learner_relationships"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("access_level IN ('viewer', 'instructor')", name="access_values"),
        CheckConstraint("expires_at > created_at", name="expiry_order"),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoked_by_user_id IS NULL)", name="revocation_pair"
        ),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="revocation_order"),
        Index(
            "uq_educator_relationship_open",
            "educator_user_id",
            "learner_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "ix_educator_relationship_history",
            "educator_user_id",
            "learner_id",
            text("created_at DESC"),
        ),
        Index("ix_educator_relationship_learner", "learner_id", text("created_at DESC")),
        Index("ix_educator_relationship_grantor", "granted_by_user_id"),
        Index("ix_educator_relationship_revoker", "revoked_by_user_id"),
        Index(
            "ix_educator_relationship_expiry",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    educator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learner_profiles.id", ondelete="RESTRICT")
    )
    access_level: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class LearnerPreferences(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "learner_preferences"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint(
            "preferred_language_tag IS NULL OR length(btrim(preferred_language_tag)) > 0",
            name="language_nonblank",
        ),
        CheckConstraint(
            "text_scale IS NULL OR text_scale BETWEEN 0.75 AND 3.00", name="text_scale_range"
        ),
        CheckConstraint(
            "line_spacing IS NULL OR line_spacing BETWEEN 1.00 AND 3.00", name="line_spacing_range"
        ),
        CheckConstraint(
            "theme IS NULL OR theme IN ('system', 'light', 'dark', 'high_contrast')",
            name="theme_values",
        ),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learner_profiles.id", ondelete="CASCADE"), unique=True
    )
    preferred_language_tag: Mapped[str | None] = mapped_column(String(35))
    text_scale: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    line_spacing: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    theme: Mapped[str | None] = mapped_column(String(20))
    reduce_motion: Mapped[bool | None] = mapped_column(Boolean)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )


class ConsentNoticeVersion(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "consent_notice_versions"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint(
            "purpose_code IN ('learning_support', 'research_participation', 'audio_retention')",
            name="purpose_values",
        ),
        CheckConstraint(
            "record_kind IN ('guardian_consent', 'learner_assent')", name="kind_values"
        ),
        CheckConstraint("length(btrim(version_label)) > 0", name="version_nonblank"),
        CheckConstraint("length(btrim(language_tag)) > 0", name="language_nonblank"),
        CheckConstraint("length(btrim(notice_text)) > 0", name="notice_nonblank"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="digest_format"),
        CheckConstraint(
            "content_sha256 = encode(sha256(convert_to(notice_text, 'UTF8')), 'hex')",
            name="digest_matches_content",
        ),
        CheckConstraint(
            "(retired_at IS NULL) = (retired_by_user_id IS NULL)", name="retirement_pair"
        ),
        CheckConstraint(
            "retired_at IS NULL OR retired_at >= published_at", name="retirement_order"
        ),
        UniqueConstraint(
            "purpose_code",
            "record_kind",
            "version_label",
            "language_tag",
            name="uq_consent_notice_version_language",
        ),
        UniqueConstraint("id", "purpose_code", "record_kind", name="uq_consent_notice_scope"),
        Index(
            "uq_consent_notice_current",
            "purpose_code",
            "record_kind",
            "language_tag",
            unique=True,
            postgresql_where=text("retired_at IS NULL"),
        ),
    )

    purpose_code: Mapped[str] = mapped_column(String(40))
    record_kind: Mapped[str] = mapped_column(String(20))
    version_label: Mapped[str] = mapped_column(String(32))
    language_tag: Mapped[str] = mapped_column(String(35))
    notice_text: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(CHAR(64))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )


class ConsentRecord(UUIDPrimaryKeyMixin, Base):
    """Append-only events; no mutable timestamps or optimistic update counter."""

    __tablename__ = "consent_records"
    __table_args__ = (
        CheckConstraint("sequence_no > 0", name="sequence_positive"),
        CheckConstraint("decision IN ('granted', 'declined', 'withdrawn')", name="decision_values"),
        CheckConstraint(
            "capture_method IN ('self_service', 'assisted_in_person')", name="capture_method_values"
        ),
        CheckConstraint(
            "(record_kind = 'guardian_consent' AND guardian_relationship_id IS NOT NULL) OR "
            "(record_kind = 'learner_assent' AND guardian_relationship_id IS NULL)",
            name="respondent_scope",
        ),
        CheckConstraint("occurred_at <= recorded_at", name="recording_order"),
        ForeignKeyConstraint(
            ["notice_version_id", "purpose_code", "record_kind"],
            [
                "consent_notice_versions.id",
                "consent_notice_versions.purpose_code",
                "consent_notice_versions.record_kind",
            ],
            name="fk_consent_record_notice_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["guardian_relationship_id", "learner_id"],
            ["guardian_learner_relationships.id", "guardian_learner_relationships.learner_id"],
            name="fk_consent_record_guardian_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "learner_id",
            "purpose_code",
            "record_kind",
            "guardian_relationship_id",
            "sequence_no",
            name="uq_consent_record_stream_sequence",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_consent_record_learner_history", "learner_id", text("recorded_at DESC")),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learner_profiles.id", ondelete="RESTRICT")
    )
    notice_version_id: Mapped[uuid.UUID] = mapped_column(index=True)
    purpose_code: Mapped[str] = mapped_column(String(40))
    record_kind: Mapped[str] = mapped_column(String(20))
    guardian_relationship_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    decision: Mapped[str] = mapped_column(String(16))
    sequence_no: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    capture_method: Mapped[str] = mapped_column(String(24))
