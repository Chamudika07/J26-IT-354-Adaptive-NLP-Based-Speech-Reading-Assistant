"""Strict, versioned research contracts; no production dependencies."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Digest = str
CATEGORIES = (
    "clean_digital_scan",
    "grayscale_scan",
    "low_resolution",
    "mild_blur",
    "skew_rotation",
    "uneven_lighting",
    "perspective_distortion",
    "low_contrast",
    "noise_compression",
    "mixed_fonts_sizes",
    "punctuation_numbers_symbols",
    "accented_english_unicode",
    "tables",
    "two_column",
    "illustration_text",
    "phone_camera_photo",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Artifact(Strict):
    identifier: str = Field(min_length=1)
    path: str = Field(min_length=1)
    engine: Literal["tesseract", "paddle"]
    engine_version: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    source: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    language: Literal["en"]
    role: Literal["recognition", "detection", "dictionary", "orientation", "layout", "runtime"]


class Case(Strict):
    fixture_id: str = Field(min_length=1)
    source_family_id: str = Field(min_length=1)
    category: str
    feature_tags: list[str]
    split: Literal["development", "heldout"]
    provenance: str = Field(min_length=1)
    parent_id: str | None = None
    status: Literal["planned", "authored", "verified"] = "planned"
    source_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    ground_truth_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Manifest(Strict):
    version: Literal["ocr-corpus-v1"]
    cases: list[Case]

    @model_validator(mode="after")
    def validate_families(self) -> "Manifest":
        by_id = {c.fixture_id: c for c in self.cases}
        if len(by_id) != len(self.cases):
            raise ValueError("duplicate fixture ID")
        families: dict[str, str] = {}
        base_families: set[str] = set()
        counts: dict[tuple[str, str], int] = {}
        for c in self.cases:
            if c.category not in CATEGORIES:
                raise ValueError("unknown category")
            if families.setdefault(c.source_family_id, c.split) != c.split:
                raise ValueError("source-family split leakage")
            if c.parent_id is not None:
                p = by_id.get(c.parent_id)
                if p is None or p.parent_id is not None or p.source_family_id != c.source_family_id:
                    raise ValueError("variant must reference its base family")
            else:
                if c.source_family_id in base_families:
                    raise ValueError("independent bases must have distinct source families")
                base_families.add(c.source_family_id)
                key = (c.category, c.split)
                counts[key] = counts.get(key, 0) + 1
            if c.status == "verified" and (not c.source_digest or not c.ground_truth_digest):
                raise ValueError("verified case needs digests")
        for category in CATEGORIES:
            for split, expected in (("development", 2), ("heldout", 3)):
                if counts.get((category, split)) != expected:
                    raise ValueError("expected 2 development and 3 heldout bases per category")
        return self


class Unit(Strict):
    text: str
    block: str
    line: str
    confidence: float | None
    polygon: list[tuple[float, float]] | None = None


class OCRResult(Strict):
    engine: Literal["tesseract", "paddle"]
    engine_version: str
    confidence_scale: str
    units: list[Unit]
    native_output: str


class PageResult(Strict):
    schema_version: Literal["ocr-result-v1"] = "ocr-result-v1"
    experiment_id: str
    fixture_id: str
    source_family_id: str
    category: str
    feature_tags: list[str]
    split: Literal["development", "heldout"]
    page_number: int = Field(ge=1)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ground_truth_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    engine: Literal["tesseract", "paddle"]
    configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome: Literal["success", "failed"]
    failure_stage: str | None
    failure_code: str | None
    character_substitutions: int | None = Field(ge=0)
    character_deletions: int | None = Field(ge=0)
    character_insertions: int | None = Field(ge=0)
    reference_character_count: int | None = Field(ge=0)
    cer: float | None = Field(ge=0)
    word_substitutions: int | None = Field(ge=0)
    word_deletions: int | None = Field(ge=0)
    word_insertions: int | None = Field(ge=0)
    reference_word_count: int | None = Field(ge=0)
    wer: float | None = Field(ge=0)
    exact_match: bool | None
    metric_status: str
    input_kind: str | None = None
    input_dimensions: tuple[int, int] | None = None
    input_pixel_digest: str | None = None
    rasterizer: str | None = None
    rasterizer_version: str | None = None
    render_dpi: int | None = None
    render_pixel_digest: str | None = None
    preprocessing_recipe: str | None = None
    preprocessing_version: str | None = None
    preprocessing_parameters: dict[str, object] | None = None
    preprocessed_pixel_digest: str | None = None
    engine_version: str | None = None
    runtime_version: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    model_digest: str | None = None
    native_output_digest: str | None = None
    assembled_text_digest: str | None = None
    line_order_result: bool | None = None
    block_order_score: float | None = None
    table_failure_counts: dict[str, int] | None = None
    confidence_scale: str | None = None
    confidence_summary: dict[str, object] | None = None
    latency_ms: dict[str, float | None] | None = None
    review_label: str | None = None
    evidence: dict[str, object]
    unavailable_reasons: dict[str, str]
    peak_memory_bytes: int | None = Field(ge=0)
    memory_method: str
    notes: list[str]

    @model_validator(mode="after")
    def consistent(self) -> "PageResult":
        if self.peak_memory_bytes is None and "peak_memory_bytes" not in self.unavailable_reasons:
            raise ValueError("missing memory reason")
        if self.outcome == "failed" and (not self.failure_code or not self.failure_stage):
            raise ValueError("failure requires stage/code")
        if self.outcome == "success" and (self.failure_code or self.failure_stage):
            raise ValueError("success cannot carry failure")
        return self
