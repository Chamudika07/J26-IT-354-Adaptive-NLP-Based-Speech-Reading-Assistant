"""Module-owned immutable source revisions and processing evidence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class ReadingMaterial(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "reading_materials"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint("archived_at IS NULL OR archived_at >= created_at", name="archive_order"),
        Index(
            "ix_reading_material_history", "learner_id", text("created_at DESC"), text("id DESC")
        ),
    )
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner_profiles.id", ondelete="RESTRICT"))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReadingMaterialRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reading_material_revisions"
    __table_args__ = (
        UniqueConstraint("material_id", "revision_number", name="uq_reading_revision_number"),
        CheckConstraint("revision_number > 0", name="number_positive"),
        CheckConstraint("length(btrim(title)) > 0", name="title_nonblank"),
        CheckConstraint("language_tag = 'en'", name="language_english"),
        CheckConstraint(
            "(source_kind = 'plain_text' AND extraction_run_id IS NULL) OR "
            "(source_kind = 'pdf_text' AND extraction_run_id IS NOT NULL)",
            name="source_provenance",
        ),
        UniqueConstraint("extraction_run_id", name="uq_revision_extraction"),
        CheckConstraint("length(original_text) BETWEEN 1 AND 50000", name="text_length"),
        CheckConstraint("source_sha256 ~ '^[0-9a-f]{64}$'", name="hash_format"),
        CheckConstraint(
            "source_sha256 = encode(sha256(convert_to(original_text, 'UTF8')), 'hex')",
            name="hash_matches",
        ),
    )
    material_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_materials.id", ondelete="RESTRICT")
    )
    extraction_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reading_material_extraction_runs.id", ondelete="RESTRICT")
    )
    revision_number: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    language_tag: Mapped[str] = mapped_column(String(35))
    source_kind: Mapped[str] = mapped_column(String(24))
    original_text: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


OUTPUT_FIELDS = (
    "normalized_text",
    "normalized_sha256",
    "character_count",
    "word_count",
    "unique_word_count",
    "sentence_count",
    "total_word_letter_count",
    "max_word_letter_count",
    "max_sentence_word_count",
)
PROVENANCE_FIELDS = (
    "pipeline_version",
    "pipeline_fingerprint",
    "normalization_version",
    "sentence_segmenter_version",
    "word_tokenizer_version",
    "feature_extractor_version",
    "profile_schema_version",
    "unicode_version",
    "vocabulary_mode",
)


class ReadingMaterialProcessingRun(UUIDPrimaryKeyMixin, VersionMixin, Base):
    __tablename__ = "reading_material_processing_runs"
    __table_args__ = (
        UniqueConstraint(
            "revision_id", "pipeline_fingerprint", "attempt_number", name="uq_material_run_attempt"
        ),
        Index(
            "uq_material_run_running",
            "revision_id",
            "pipeline_fingerprint",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "uq_material_run_succeeded",
            "revision_id",
            "pipeline_fingerprint",
            unique=True,
            postgresql_where=text("status = 'succeeded'"),
        ),
        Index("ix_material_run_history", "revision_id", text("started_at DESC"), text("id DESC")),
        Index(
            "ix_material_run_lease", "lease_expires_at", postgresql_where=text("status = 'running'")
        ),
        CheckConstraint("attempt_number > 0 AND row_version > 0", name="positive_versions"),
        CheckConstraint("lease_expires_at > started_at", name="lease_order"),
        CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name="finish_order"),
        CheckConstraint("pipeline_fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint_format"),
        CheckConstraint("vocabulary_mode = 'none'", name="vocabulary_none"),
        *(
            CheckConstraint(f"length(btrim({name})) > 0", name=f"{name}_nonblank")
            for name in PROVENANCE_FIELDS[:-1]
        ),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL AND failure_code IS NULL AND "
            + " AND ".join(f"{name} IS NULL" for name in OUTPUT_FIELDS)
            + ") OR "
            + "(status = 'failed' AND finished_at IS NOT NULL AND failure_code IS NOT NULL AND "
            + " AND ".join(f"{name} IS NULL" for name in OUTPUT_FIELDS)
            + ") OR "
            + "(status = 'succeeded' AND finished_at IS NOT NULL AND failure_code IS NULL AND "
            + " AND ".join(f"{name} IS NOT NULL" for name in OUTPUT_FIELDS)
            + ")",
            name="state_output",
        ),
        CheckConstraint(
            "failure_code IS NULL OR failure_code IN ('pipeline_failed', 'processing_interrupted')",
            name="failure_values",
        ),
        *(
            CheckConstraint(f"{name} IS NULL OR {name} >= 0", name=f"{name}_nonnegative")
            for name in OUTPUT_FIELDS[2:]
        ),
        CheckConstraint(
            "word_count IS NULL OR (word_count >= 1 AND unique_word_count BETWEEN "
            "1 AND word_count AND sentence_count BETWEEN 1 AND word_count)",
            name="count_relationships",
        ),
        CheckConstraint(
            "normalized_text IS NULL OR (character_count = "
            "length(normalized_text) AND length(normalized_text) > 0)",
            name="character_count_matches",
        ),
        CheckConstraint(
            "normalized_sha256 IS NULL OR (normalized_sha256 ~ '^[0-9a-f]{64}$' "
            "AND normalized_sha256 = encode(sha256(convert_to(normalized_text, "
            "'UTF8')), 'hex'))",
            name="normalized_hash_matches",
        ),
    )
    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_material_revisions.id", ondelete="RESTRICT")
    )
    attempt_number: Mapped[int]
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(32))
    pipeline_version: Mapped[str] = mapped_column(String(80))
    pipeline_fingerprint: Mapped[str] = mapped_column(String(64))
    normalization_version: Mapped[str] = mapped_column(String(80))
    sentence_segmenter_version: Mapped[str] = mapped_column(String(80))
    word_tokenizer_version: Mapped[str] = mapped_column(String(80))
    feature_extractor_version: Mapped[str] = mapped_column(String(80))
    profile_schema_version: Mapped[str] = mapped_column(String(80))
    unicode_version: Mapped[str] = mapped_column(String(24))
    vocabulary_mode: Mapped[str] = mapped_column(String(16))
    normalized_text: Mapped[str | None] = mapped_column(Text)
    normalized_sha256: Mapped[str | None] = mapped_column(String(64))
    character_count: Mapped[int | None]
    word_count: Mapped[int | None]
    unique_word_count: Mapped[int | None]
    sentence_count: Mapped[int | None]
    total_word_letter_count: Mapped[int | None]
    max_word_letter_count: Mapped[int | None]
    max_sentence_word_count: Mapped[int | None]


class ReadingMaterialSentenceFeature(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reading_material_sentence_features"
    __table_args__ = (
        UniqueConstraint("run_id", "ordinal", name="uq_material_sentence_ordinal"),
        CheckConstraint("ordinal > 0 AND word_count > 0", name="positive_counts"),
        CheckConstraint(
            "source_start >= 0 AND source_end > source_start AND analysis_start "
            ">= 0 AND analysis_end > analysis_start",
            name="offset_ranges",
        ),
        CheckConstraint(
            "max_word_letter_count > 0 AND total_word_letter_count >= word_count "
            "AND max_word_letter_count <= total_word_letter_count",
            name="letter_counts",
        ),
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_material_processing_runs.id", ondelete="RESTRICT")
    )
    ordinal: Mapped[int]
    source_start: Mapped[int]
    source_end: Mapped[int]
    analysis_start: Mapped[int]
    analysis_end: Mapped[int]
    word_count: Mapped[int]
    total_word_letter_count: Mapped[int]
    max_word_letter_count: Mapped[int]
