"""Strict metadata and artifact validation; paths are relative to one corpus root."""

import hashlib
import json
import re
from pathlib import Path
from typing import Annotated, Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

SHA = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Nonempty = Annotated[str, Field(min_length=1)]
Outcome = Literal["extracted", "ocr_required", "needs_review", "failed"]
Split = Literal["development", "heldout"]
Category = Literal[
    "simple_single_column",
    "multipage",
    "headings_paragraphs",
    "tables",
    "two_column",
    "headers_footers_page_numbers",
    "unicode",
    "punctuation_hyphenation",
    "mixed_text_images",
    "image_only_or_scanned_like",
    "invalid_or_unsupported",
]
CATEGORIES = list(get_args(Category))
OUTCOMES = ["extracted", "ocr_required", "needs_review", "failed"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Artifact(Strict):
    reference: Nonempty
    sha256: SHA


class Fixture(Strict):
    fixture_id: Nonempty
    primary_category: Category
    feature_tags: list[str]
    split: Split
    template_family_id: Nonempty
    provenance_type: Literal["original", "public_domain", "permission_cleared"]
    creator_or_source_reference: Nonempty
    license_or_permission_reference: Nonempty
    generator_name: Nonempty
    generator_version: Nonempty
    generator_configuration: dict[str, str | int | bool]
    generator_seed: int | None
    source_artifact_reference: Nonempty
    source_sha256: SHA
    source_byte_count: int = Field(gt=0)
    expected_page_count: int | None = Field(default=None, ge=0)
    expected_policy_outcome: Outcome
    expected_outcome_code: str | None
    content_assessment: Literal[
        "complete", "missing_visible_content", "ordering_problem", "unusable"
    ]
    reference_scope: Literal["embedded_and_visible", "embedded_only", "not_applicable"]
    page_ground_truth: list[Artifact]
    assembled_ground_truth: Artifact
    structural_annotation: Artifact
    authoring_source: Artifact
    exact_match_required: bool
    metric_eligibility: bool
    known_limitations: list[str]
    notes: str


class Manifest(Strict):
    schema_version: Literal["1"] = "1"
    benchmark_version: Literal["benchmark-v1"] = "benchmark-v1"
    protocol_version: Literal["protocol-v1"] = "protocol-v1"
    corpus_id: str = "original-pdf-66-v1"
    split_seed: int = 22081766
    production_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    fixture_entries: list[Fixture]

    @model_validator(mode="after")
    def identities(self) -> Self:
        ids = [f.fixture_id for f in self.fixture_entries]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate fixture IDs")
        hashes = [f.source_sha256 for f in self.fixture_entries]
        if len(set(hashes)) != len(hashes):
            raise ValueError("duplicate PDF bytes in independent corpus")
        families: dict[str, str] = {}
        for f in self.fixture_entries:
            previous = families.setdefault(f.template_family_id, f.split)
            if previous != f.split:
                raise ValueError("template family crosses split")
        return self


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: Path) -> str:
    """Decode UTF-8 without universal-newline translation."""
    return path.read_bytes().decode("utf-8")


def resolve(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("artifact path escapes root")
    return path


def validate_artifacts(manifest: Manifest, root: Path) -> None:
    for f in manifest.fixture_entries:
        source = resolve(root, f.source_artifact_reference)
        if digest(source) != f.source_sha256 or source.stat().st_size != f.source_byte_count:
            raise ValueError("PDF hash/size mismatch")
        refs = [
            *f.page_ground_truth,
            f.assembled_ground_truth,
            f.structural_annotation,
            f.authoring_source,
        ]
        for ref in refs:
            if digest(resolve(root, ref.reference)) != ref.sha256:
                raise ValueError("ground truth hash mismatch")
        pages = [read_text(resolve(root, ref.reference)) for ref in f.page_ground_truth]
        if "\n\n".join(pages) != read_text(resolve(root, f.assembled_ground_truth.reference)):
            raise ValueError("ground truth assembly mismatch")
        author = json.loads(resolve(root, f.authoring_source.reference).read_text())
        if pages != ["".join(b["text"] + "\n" for b in p["blocks"]) for p in author["pages"]]:
            raise ValueError("ground truth disagrees with independent authoring source")
        structure = json.loads(read_text(resolve(root, f.structural_annotation.reference)))
        visible = Artifact.model_validate(structure["visible_ground_truth"])
        if digest(resolve(root, visible.reference)) != visible.sha256:
            raise ValueError("visible reference hash mismatch")
        expected_visible = "\n\n".join(
            text + (page["image_text"] or "")
            for text, page in zip(pages, author["pages"], strict=True)
        )
        if read_text(resolve(root, visible.reference)) != expected_visible:
            raise ValueError("visible reference disagrees with authoring source")
        expected_offsets, start = [], 0
        for page in pages:
            expected_offsets.append([start, start + len(page)])
            start += len(page) + 2
        if structure["offsets"] != expected_offsets:
            raise ValueError("invalid reference offsets")
        if structure["tokens"] != re.findall(r"\S+", "\n\n".join(pages)):
            raise ValueError("invalid reference tokens")
        if structure["page_ids"] != [p["id"] for p in author["pages"]]:
            raise ValueError("invalid page IDs")
        if f.expected_page_count is not None and len(pages) != f.expected_page_count:
            raise ValueError("page count mismatch")


class Result(Strict):
    experiment_id: str
    fixture_id: str
    category: Category
    split: Split
    source_sha256: SHA
    source_byte_count: int = Field(ge=0)
    expected_page_count: int | None
    observed_page_count: int | None
    expected_outcome: Outcome
    actual_outcome: Outcome
    outcome_code: str | None
    extraction_fingerprint: SHA
    production_commit: str
    metric_version: str
    character_substitutions: int = Field(ge=0)
    character_deletions: int = Field(ge=0)
    character_insertions: int = Field(ge=0)
    reference_character_count: int = Field(ge=0)
    word_substitutions: int = Field(ge=0)
    word_deletions: int = Field(ge=0)
    word_insertions: int = Field(ge=0)
    reference_word_count: int = Field(ge=0)
    raw_page_cer: float | None = Field(ge=0)
    raw_assembled_cer: float | None = Field(ge=0)
    raw_wer: float | None = Field(ge=0)
    normalized_cer: float | None = Field(ge=0)
    normalized_wer: float | None = Field(ge=0)
    exact_match: bool | None
    metric_status: str
    lexical_page_coverage: float | None = Field(ge=0, le=1)
    page_order_correct: bool | None
    block_order_score: float | None = Field(ge=0, le=1)
    review_label: Literal[
        "correct", "acceptable_with_limitation", "needs_review", "extraction_failure"
    ]
    review_codes: list[str]
    latency_median_ms: Annotated[float, Field(ge=0)]
    peak_memory_bytes: int | None = None
    memory_measurement_method: str = "unavailable: runner does not expose per-child RSS"
    notes: list[str]
    detail: dict[str, object]
