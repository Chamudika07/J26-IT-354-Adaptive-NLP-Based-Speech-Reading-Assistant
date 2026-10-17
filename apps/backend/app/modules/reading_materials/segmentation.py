"""Frozen English boundary heuristics; not a grammatical or multilingual model."""

import unicodedata as ud
from dataclasses import dataclass

SENTENCE_VERSION = "reading-sentence-segmentation-v1"
WORD_VERSION = "reading-word-tokenization-v1"
APOSTROPHES = "'\u2019"
HYPHENS = "-\u2010\u2011"
ABBREVIATIONS = ("dr", "mr", "mrs", "ms", "prof", "sr", "jr", "e.g", "i.e")
CLOSERS = "\"'\u2019\u201d)]}"


def is_letter(c: str) -> bool:
    return ud.category(c).startswith("L")


@dataclass(frozen=True)
class Word:
    start: int
    end: int
    key: str
    letter_count: int


def words(text: str) -> list[Word]:
    result = []
    i = 0
    while i < len(text):
        if not is_letter(text[i]):
            i += 1
            continue
        start = i
        letters = 1
        i += 1
        while i < len(text):
            if is_letter(text[i]):
                letters += 1
                i += 1
            elif ud.category(text[i]).startswith("M"):
                i += 1
            elif text[i] in APOSTROPHES + HYPHENS and i + 1 < len(text) and is_letter(text[i + 1]):
                i += 1
            else:
                break
        key = text[start:i].casefold().replace("\u2019", "'")
        key = key.replace("\u2010", "-").replace("\u2011", "-")
        result.append(Word(start, i, key, letters))
    return result


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Single newlines are retained; blank lines force a boundary. Exclude nonlexical spans."""
    spans = []
    start = i = 0

    def emit(end: int) -> None:
        nonlocal start
        left, right = start, end
        while left < right and text[left].isspace():
            left += 1
        while right > left and text[right - 1].isspace():
            right -= 1
        if left < right and any(is_letter(c) for c in text[left:right]):
            spans.append((left, right))
        start = end

    while i < len(text):
        c = text[i]
        if c == "\n":
            j = i + 1
            while j < len(text) and text[j] == " ":
                j += 1
            if j < len(text) and text[j] == "\n":
                emit(i)
                start = j + 1
                i = j + 1
                continue
        if c in ".?!":
            decimal = (
                c == "."
                and i > 0
                and i + 1 < len(text)
                and text[i - 1].isdigit()
                and text[i + 1].isdigit()
            )
            j = i - 1
            while j >= max(start, i - 5) and (is_letter(text[j]) or text[j] == "."):
                j -= 1
            token = text[j + 1 : i].casefold()
            abbreviation = c == "." and token in ABBREVIATIONS
            # Interior acronym/abbreviation periods (e.g. the first period in e.g.).
            interior = c == "." and i + 1 < len(text) and is_letter(text[i + 1])
            if not (decimal or abbreviation or interior):
                end = i + 1
                while end < len(text) and (
                    text[end] in ".?!" + CLOSERS or ud.category(text[end]).startswith("M")
                ):
                    end += 1
                emit(end)
                i = end
                continue
        i += 1
    emit(len(text))
    return spans
