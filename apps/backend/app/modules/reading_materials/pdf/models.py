"""PDF sources and immutable direct-extraction evidence on the shared Base."""

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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class Source(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "reading_material_sources"
    __table_args__ = (
        UniqueConstraint("storage_backend", "storage_key", name="uq_pdf_storage"),
        UniqueConstraint(
            "learner_id", "created_by_user_id", "upload_request_id", name="uq_pdf_upload"
        ),
        UniqueConstraint("material_id", name="uq_pdf_material"),
        CheckConstraint(
            "source_kind = 'pdf' AND language_tag = 'en' AND media_type = 'application/pdf'",
            name="pdf_scope",
        ),
        CheckConstraint("length(btrim(title)) > 0", name="title_nonblank"),
        CheckConstraint("byte_count BETWEEN 1 AND 10485760", name="byte_limit"),
        CheckConstraint("file_sha256 ~ '^[0-9a-f]{64}$'", name="hash_format"),
        CheckConstraint(
            "storage_backend = 'local-v1' AND storage_key ~ '^[0-9a-f]{32}$'", name="storage_format"
        ),
        CheckConstraint("row_version > 0", name="positive_version"),
        CheckConstraint("archived_at IS NULL OR archived_at >= created_at", name="archive_order"),
        Index("ix_pdf_source_history", "learner_id", text("created_at DESC"), text("id DESC")),
    )
    learner_id: Mapped[UUID] = mapped_column(ForeignKey("learner_profiles.id", ondelete="RESTRICT"))
    material_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reading_materials.id", ondelete="RESTRICT")
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    language_tag: Mapped[str] = mapped_column(String(35))
    source_kind: Mapped[str] = mapped_column(String(24))
    media_type: Mapped[str] = mapped_column(String(40))
    byte_count: Mapped[int]
    file_sha256: Mapped[str] = mapped_column(String(64))
    storage_backend: Mapped[str] = mapped_column(String(24))
    storage_key: Mapped[str] = mapped_column(String(32))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    upload_request_id: Mapped[UUID]


PROVENANCE = (
    "extraction_version",
    "validation_version",
    "assembly_version",
    "quality_version",
    "extractor_name",
    "extractor_package_version",
    "python_version",
    "unicode_version",
    "quality_tokenizer_version",
    "extraction_fingerprint",
)
COUNTS = (
    "total_page_count",
    "pages_with_lexical_text",
    "pages_with_zero_characters",
    "pages_with_zero_lexical_words",
    "extracted_character_count",
    "assembled_character_count",
    "lexical_word_count",
)
OUTPUT = ("assembled_text", "assembled_text_sha256", *COUNTS)
CODES = (
    "'malformed_pdf','encrypted_pdf','unsupported_pdf_features','page_limit_exceeded',"
    "'text_limit_exceeded','unsupported_extracted_text','resource_limit_exceeded',"
    "'extraction_interrupted','backend_failed','integrity_failed','no_usable_text'"
)


class ExtractionRun(UUIDPrimaryKeyMixin, VersionMixin, Base):
    __tablename__ = "reading_material_extraction_runs"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "extraction_fingerprint", "attempt_number", name="uq_pdf_attempt"
        ),
        Index(
            "uq_pdf_running",
            "source_id",
            "extraction_fingerprint",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "uq_pdf_extracted",
            "source_id",
            "extraction_fingerprint",
            unique=True,
            postgresql_where=text("status = 'extracted'"),
        ),
        Index("ix_pdf_run_history", "source_id", text("started_at DESC"), text("id DESC")),
        Index("ix_pdf_run_lease", "lease_expires_at", postgresql_where=text("status = 'running'")),
        CheckConstraint("attempt_number > 0 AND row_version > 0", name="positive_versions"),
        CheckConstraint(
            (
                "lease_expires_at > started_at AND (finished_at IS NULL OR "
                "finished_at >= started_at)"
            ),
            name="time_order",
        ),
        CheckConstraint("extraction_fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint_format"),
        *(
            CheckConstraint(f"length(btrim({name})) > 0", name=f"{name}_nonblank")
            for name in PROVENANCE[:-1]
        ),
        CheckConstraint(
            "(status='running' AND finished_at IS NULL AND outcome_code IS NULL AND "
            + " AND ".join(f"{n} IS NULL" for n in OUTPUT)
            + ") OR "
            + (
                "(status='failed' AND finished_at IS NOT NULL AND outcome_code IS "
                "NOT NULL AND outcome_code IN ("
            )
            + CODES
            + ") AND "
            + " AND ".join(f"{n} IS NULL" for n in OUTPUT)
            + ") OR "
            + (
                "(status IN ('extracted','ocr_required','needs_review') AND "
                "finished_at IS NOT NULL AND "
            )
            + " AND ".join(f"{n} IS NOT NULL" for n in OUTPUT)
            + (
                " AND ((status='extracted' AND outcome_code IS NULL AND "
                "lexical_word_count > 0) OR (status='ocr_required' AND "
                "outcome_code='image_without_text') OR (status='needs_review' AND "
                "outcome_code='ambiguous_content')))"
            ),
            name="state_output",
        ),
        *(CheckConstraint(f"{n} IS NULL OR {n} >= 0", name=f"{n}_nonnegative") for n in COUNTS),
        CheckConstraint(
            (
                "total_page_count IS NULL OR (total_page_count BETWEEN 1 AND 25 "
                "AND pages_with_lexical_text + pages_with_zero_lexical_words = "
                "total_page_count AND pages_with_zero_characters <= "
                "pages_with_zero_lexical_words)"
            ),
            name="page_counts",
        ),
        CheckConstraint(
            (
                "assembled_text IS NULL OR (length(assembled_text) <= 50000 AND "
                "assembled_character_count = length(assembled_text) AND "
                "assembled_character_count = extracted_character_count + "
                "2*(total_page_count-1) AND assembled_text_sha256 = "
                "encode(sha256(convert_to(assembled_text,'UTF8')),'hex'))"
            ),
            name="text_evidence",
        ),
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_material_sources.id", ondelete="RESTRICT")
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    attempt_number: Mapped[int]
    status: Mapped[str] = mapped_column(String(24))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    extraction_version: Mapped[str] = mapped_column(String(80))
    validation_version: Mapped[str] = mapped_column(String(80))
    assembly_version: Mapped[str] = mapped_column(String(80))
    quality_version: Mapped[str] = mapped_column(String(80))
    extractor_name: Mapped[str] = mapped_column(String(80))
    extractor_package_version: Mapped[str] = mapped_column(String(80))
    extraction_fingerprint: Mapped[str] = mapped_column(String(64))
    python_version: Mapped[str] = mapped_column(String(80))
    unicode_version: Mapped[str] = mapped_column(String(80))
    quality_tokenizer_version: Mapped[str] = mapped_column(String(80))
    outcome_code: Mapped[str | None] = mapped_column(String(40))
    assembled_text: Mapped[str | None] = mapped_column(Text)
    assembled_text_sha256: Mapped[str | None] = mapped_column(String(64))
    total_page_count: Mapped[int | None]
    pages_with_lexical_text: Mapped[int | None]
    pages_with_zero_characters: Mapped[int | None]
    pages_with_zero_lexical_words: Mapped[int | None]
    extracted_character_count: Mapped[int | None]
    assembled_character_count: Mapped[int | None]
    lexical_word_count: Mapped[int | None]


class ExtractionPage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reading_material_extraction_pages"
    __table_args__ = (
        UniqueConstraint("extraction_run_id", "page_number", name="uq_pdf_page"),
        CheckConstraint("page_number BETWEEN 1 AND 25", name="page_number"),
        CheckConstraint(
            (
                "text_start >= 0 AND text_end >= text_start AND text_end <= 50000 "
                "AND raw_character_count = text_end-text_start AND "
                "lexical_word_count BETWEEN 0 AND raw_character_count"
            ),
            name="page_counts",
        ),
        CheckConstraint(
            (
                "(text_status='empty' AND raw_character_count=0 AND "
                "lexical_word_count=0) OR (text_status='nonlexical' AND "
                "raw_character_count>0 AND lexical_word_count=0) OR "
                "(text_status='lexical' AND lexical_word_count>0)"
            ),
            name="text_status",
        ),
        CheckConstraint(
            (
                "cardinality(warning_codes) <= 4 AND "
                "array_position(warning_codes,NULL) IS NULL AND warning_codes <@ "
                "ARRAY['painted_image','vector_content','inspection_uncertain','replacement_character']::varchar[]"
            ),
            name="warnings",
        ),
    )
    extraction_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("reading_material_extraction_runs.id", ondelete="RESTRICT")
    )
    page_number: Mapped[int]
    text_start: Mapped[int]
    text_end: Mapped[int]
    raw_character_count: Mapped[int]
    lexical_word_count: Mapped[int]
    text_status: Mapped[str] = mapped_column(String(24))
    warning_codes: Mapped[list[str]] = mapped_column(ARRAY(String(40)))
