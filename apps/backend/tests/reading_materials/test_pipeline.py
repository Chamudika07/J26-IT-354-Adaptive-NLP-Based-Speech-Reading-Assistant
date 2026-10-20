import hashlib
import json
import unicodedata
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.reading_materials import pipeline
from app.modules.reading_materials.normalization import normalize, validate_text
from app.modules.reading_materials.profiles import ratio
from app.modules.reading_materials.schemas import MaterialCreate, RevisionCreate
from app.modules.reading_materials.segmentation import sentence_spans, words


@pytest.mark.parametrize(
    "source,expected",
    [
        ("Cafe\u0301.", "Café."),
        ("A\r\nB\rC", "A\nB\nC"),
        ("A\t  B", "A B"),
        (" A\n\n B ", " A\n\n B "),
        ("a\u00a0\u2003b", "a b"),
        ("naïve “can’t” co-operate!", "naïve “can’t” co-operate!"),
        ("A\u2028B\u2029C", "A\nB\n\nC"),
        ("\u1100\u1161\u11a8", "각"),
    ],
)
def test_normalization_and_source_preservation(source, expected):
    result = normalize(source)
    assert result.text == expected
    assert len(result.source_spans) == len(expected)
    assert result.source_range(0, len(expected)) == (0, len(source))


@pytest.mark.parametrize(
    "source", ["", " \t\r\n", "a\x00b", "a\x01b", "a\x7fb", "a\u200bb", "\ud800", "a" * 50001]
)
def test_invalid_source(source):
    with pytest.raises(ValueError):
        validate_text(source)


def test_max_source_length_and_nfc_offset_mapping():
    assert len(validate_text("a" * 50000)) == 50000
    source = "Cafe\u0301!\r\n\r\nA dog."
    result = pipeline.process(source)
    assert result.normalized_text == "Café!\n\nA dog."
    first, second = result.sentences
    assert (first.source_start, first.source_end, first.analysis_start, first.analysis_end) == (
        0,
        6,
        0,
        5,
    )
    assert source[second.source_start : second.source_end] == "A dog."
    assert result.normalized_text[second.analysis_start : second.analysis_end] == "A dog."


@pytest.mark.parametrize(
    "source,expected",
    [
        ("Hello. Bye?", ["Hello.", "Bye?"]),
        ("“Hello?!” Fine.", ["“Hello?!”", "Fine."]),
        ("Dr. Fox rests. Ms. May runs!", ["Dr. Fox rests.", "Ms. May runs!"]),
        ("Use e.g. a pen. Use i.e. carefully.", ["Use e.g. a pen.", "Use i.e. carefully."]),
        ("It is 3.14 long. Done", ["It is 3.14 long.", "Done"]),
        ("First\nline\n\nSecond fragment", ["First\nline", "Second fragment"]),
        ("First\n \nSecond", ["First", "Second"]),
        ("... 123 !!! Cat.", ["Cat."]),
        ("One... Two!!!", ["One...", "Two!!!"]),
    ],
)
def test_sentence_boundaries(source, expected):
    assert [source[s:e] for s, e in sentence_spans(source)] == expected


@pytest.mark.parametrize(
    "text,keys,lengths",
    [
        ("Can't can’t", ["can't", "can't"], [4, 4]),
        ("co-operate co‐operate co‑operate", ["co-operate"] * 3, [9] * 3),
        ("one–two—three", ["one", "two", "three"], [3, 3, 5]),
        ("'cat' -dog-", ["cat", "dog"], [3, 3]),
        ("123 3.14 !", [], []),
        ("Café CAFE\u0301", ["café", "cafe\u0301"], [4, 4]),
    ],
)
def test_word_policy(text, keys, lengths):
    tokens = words(text)
    assert [t.key for t in tokens] == keys
    assert [t.letter_count for t in tokens] == lengths


def test_exact_features_and_reproducible_manifest():
    result = pipeline.process("A cat rests. A dog runs!")
    assert result.document.character_count == 24
    assert result.document.word_count == 6
    assert result.document.unique_word_count == 5
    assert result.document.sentence_count == 2
    assert result.document.total_word_letter_count == 17
    assert result.document.max_word_letter_count == 5
    assert result.document.max_sentence_word_count == 3
    assert [s.word_count for s in result.sentences] == [3, 3]
    canonical = json.dumps(
        pipeline.manifest(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    assert pipeline.fingerprint() == hashlib.sha256(canonical.encode()).hexdigest()
    assert pipeline.manifest()["unicode_version"] == unicodedata.unidata_version
    assert pipeline.process("A cat rests. A dog runs!") == result


def test_version_change_changes_fingerprint(monkeypatch):
    previous = pipeline.fingerprint()
    monkeypatch.setattr(pipeline, "VERSION", "reading-pipeline-v2-test")
    assert pipeline.fingerprint() != previous


@pytest.mark.parametrize("text", ["... !!!", "123 3.14"])
def test_no_lexical_words(text):
    with pytest.raises(ValueError):
        pipeline.process(text)


def test_ratio_rounding():
    assert ratio(17, 6) == Decimal("2.83")
    assert ratio(1, 8) == Decimal("0.13")
    assert ratio(5, 6) == Decimal("0.83")
    with pytest.raises(ValueError):
        ratio(0, 0)


@pytest.mark.parametrize(
    "change",
    [
        {"language_tag": "si"},
        {"language_tag": "en-US"},
        {"title": " "},
        {"actor_id": "forged"},
        {"text": "\x00"},
        {"text": " "},
        {"title": "x" * 201},
    ],
)
def test_request_validation(change):
    with pytest.raises(ValidationError):
        MaterialCreate(**({"title": "Synthetic", "language_tag": "en", "text": "A cat."} | change))


@pytest.mark.parametrize("version", [True, "1", 1.5, 0, -1])
def test_strict_version(version):
    with pytest.raises(ValidationError):
        RevisionCreate(title="Synthetic", language_tag="en", text="A cat.", row_version=version)


def test_scanner_is_bounded_for_long_abbreviation_like_input():
    output = pipeline.process("a." * 25000)
    assert output.document.word_count == 25000
