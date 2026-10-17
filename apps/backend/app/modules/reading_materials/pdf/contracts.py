"""Bounded child-process protocol and frozen extraction policy."""

import hashlib
import json
import platform
import unicodedata
from importlib.metadata import version
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.reading_materials.segmentation import WORD_VERSION

MAX_BYTES = 10 * 1024 * 1024
MAX_BODY = MAX_BYTES + 65536
MAX_PAGES = 25
MAX_TEXT = 50000
LEASE_SECONDS = 90
WALL_SECONDS = 30
CPU_SECONDS = 15
MEMORY_BYTES = 512 * 1024 * 1024
MAX_RESULT = 1024 * 1024
OUTCOMES = (
    "malformed_pdf",
    "encrypted_pdf",
    "unsupported_pdf_features",
    "page_limit_exceeded",
    "text_limit_exceeded",
    "unsupported_extracted_text",
    "resource_limit_exceeded",
    "extraction_interrupted",
    "backend_failed",
    "integrity_failed",
    "no_usable_text",
    "image_without_text",
    "ambiguous_content",
)
WARNINGS = ("painted_image", "vector_content", "inspection_uncertain", "replacement_character")
REJECT_KEYS = (
    "/A",
    "/RichMediaContent",
    "/RichMediaSettings",
    "/Movie",
    "/Sound",
    "/JavaScript",
    "/JS",
    "/OpenAction",
    "/AA",
    "/EmbeddedFiles",
    "/EF",
    "/AcroForm",
    "/XFA",
    "/Launch",
)
REJECT_ACTIONS = (
    "/JavaScript",
    "/Launch",
    "/GoToR",
    "/GoToE",
    "/SubmitForm",
    "/ImportData",
    "/Rendition",
    "/Movie",
    "/Sound",
)


def provenance() -> dict[str, str]:
    return dict(
        extraction_version="pdf-extraction-v1",
        validation_version="pdf-validation-v1",
        assembly_version="pdf-assembly-v1",
        quality_version="pdf-quality-v1",
        extractor_name="pypdf",
        extractor_package_version=version("pypdf"),
        python_version=platform.python_version(),
        unicode_version=unicodedata.unidata_version,
        quality_tokenizer_version=WORD_VERSION,
    )


def manifest() -> dict[str, object]:
    return dict(
        **provenance(),
        strict=True,
        extraction_mode="plain",
        orientations=[0, 90, 180, 270],
        space_width=200,
        max_bytes=MAX_BYTES,
        max_pages=MAX_PAGES,
        max_text=MAX_TEXT,
        separator="\n\n",
        reject_keys=REJECT_KEYS,
        reject_actions=REJECT_ACTIONS,
        warnings=WARNINGS,
        max_objects=10000,
        max_operations=100000,
        max_depth=32,
        wall_seconds=WALL_SECONDS,
        cpu_seconds=CPU_SECONDS,
        memory_bytes=MEMORY_BYTES,
        max_result=MAX_RESULT,
        quality_policy="raster/no-word->ocr; raster+word/vector/replacement/unknown->review",
        encrypted_policy="reject-all",
        invalid_characters="current-text-validator",
        lexical_policy="raw-page Unicode letters; no completeness percentage",
    )


def fingerprint() -> str:
    return hashlib.sha256(
        json.dumps(manifest(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


class PageEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    page_number: int = Field(ge=1, le=MAX_PAGES)
    text_start: int = Field(ge=0, le=MAX_TEXT)
    text_end: int = Field(ge=0, le=MAX_TEXT)
    raw_character_count: int = Field(ge=0, le=MAX_TEXT)
    lexical_word_count: int = Field(ge=0, le=MAX_TEXT)
    text_status: Literal["lexical", "nonlexical", "empty"]
    warning_codes: list[
        Literal["painted_image", "vector_content", "inspection_uncertain", "replacement_character"]
    ] = Field(max_length=4)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["extracted", "ocr_required", "needs_review", "failed"]
    outcome_code: str | None = None
    assembled_text: str | None = Field(default=None, max_length=MAX_TEXT, repr=False)
    pages: list[PageEvidence] = Field(default_factory=list, max_length=MAX_PAGES)


def failed(code: str) -> ExtractionResult:
    return ExtractionResult(status="failed", outcome_code=code)
