"""Canonical server-owned manifest; no external resources or fabricated build digest."""

import hashlib
import json
import unicodedata
from dataclasses import dataclass

from app.modules.reading_materials import features, normalization, segmentation

VERSION = "reading-pipeline-v1"
PROFILE_VERSION = "reading-profile-v1"
LEASE_SECONDS = 60


def manifest() -> dict[str, object]:
    return {
        "pipeline_version": VERSION,
        "normalization_version": normalization.VERSION,
        "sentence_segmenter_version": segmentation.SENTENCE_VERSION,
        "word_tokenizer_version": segmentation.WORD_VERSION,
        "feature_extractor_version": features.VERSION,
        "profile_schema_version": PROFILE_VERSION,
        "unicode_version": unicodedata.unidata_version,
        "vocabulary_mode": "none",
        "language_tag": "en",
        "max_source_length": normalization.MAX_SOURCE_LENGTH,
        "allowed_controls": normalization.ALLOWED_CONTROLS,
        "apostrophes": segmentation.APOSTROPHES,
        "hyphens": segmentation.HYPHENS,
        "abbreviations": list(segmentation.ABBREVIATIONS),
        "closing_punctuation": segmentation.CLOSERS,
        "unicode_form": "NFC",
        "horizontal_whitespace": "TAB and Zs -> SPACE; collapse within lines",
        "line_separators": "CRLF/CR/U+2028 -> LF; U+2029 -> LF LF",
        "comparison_keys": "casefold; U+2019 -> apostrophe; U+2010/U+2011 -> hyphen",
        "rounding": "Decimal local precision 40; ROUND_HALF_UP; 2 decimal places",
        "offsets": "Unicode code points; zero based; exclusive end",
    }


def fingerprint() -> str:
    canonical = json.dumps(manifest(), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def provenance() -> dict[str, str]:
    value = manifest()
    names = (
        "pipeline_version",
        "normalization_version",
        "sentence_segmenter_version",
        "word_tokenizer_version",
        "feature_extractor_version",
        "profile_schema_version",
        "unicode_version",
        "vocabulary_mode",
    )
    return {**{name: str(value[name]) for name in names}, "pipeline_fingerprint": fingerprint()}


@dataclass(frozen=True)
class Output:
    normalized_text: str
    normalized_sha256: str
    document: features.DocumentFeatures
    sentences: tuple[features.SentenceFeatures, ...]


def process(source: str) -> Output:
    normalized = normalization.normalize(source)
    document, sentences = features.extract(normalized)
    return Output(
        normalized.text,
        hashlib.sha256(normalized.text.encode("utf-8")).hexdigest(),
        document,
        sentences,
    )
