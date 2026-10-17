"""Raw reproducible surface measurements only."""

from dataclasses import dataclass

from app.modules.reading_materials.normalization import NormalizedText
from app.modules.reading_materials.segmentation import sentence_spans, words

VERSION = "reading-features-v1"


@dataclass(frozen=True)
class SentenceFeatures:
    ordinal: int
    source_start: int
    source_end: int
    analysis_start: int
    analysis_end: int
    word_count: int
    total_word_letter_count: int
    max_word_letter_count: int


@dataclass(frozen=True)
class DocumentFeatures:
    character_count: int
    word_count: int
    unique_word_count: int
    sentence_count: int
    total_word_letter_count: int
    max_word_letter_count: int
    max_sentence_word_count: int


def extract(normalized: NormalizedText) -> tuple[DocumentFeatures, tuple[SentenceFeatures, ...]]:
    sentences = []
    keys: set[str] = set()
    for ordinal, (start, end) in enumerate(sentence_spans(normalized.text), 1):
        tokens = words(normalized.text[start:end])
        keys.update(t.key for t in tokens)
        source_start, source_end = normalized.source_range(start, end)
        sentences.append(
            SentenceFeatures(
                ordinal,
                source_start,
                source_end,
                start,
                end,
                len(tokens),
                sum(t.letter_count for t in tokens),
                max(t.letter_count for t in tokens),
            )
        )
    if not sentences:
        raise ValueError("No lexical words")
    return DocumentFeatures(
        len(normalized.text),
        sum(s.word_count for s in sentences),
        len(keys),
        len(sentences),
        sum(s.total_word_letter_count for s in sentences),
        max(s.max_word_letter_count for s in sentences),
        max(s.word_count for s in sentences),
    ), tuple(sentences)
