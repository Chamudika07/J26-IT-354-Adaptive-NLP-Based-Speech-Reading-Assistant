"""NFC and whitespace normalization with conservative source-span correspondence."""

import unicodedata as ud
from dataclasses import dataclass

VERSION = "reading-normalization-v1"
MAX_SOURCE_LENGTH = 50_000
ALLOWED_CONTROLS = "\t\n\r"


def validate_text(text: str) -> str:
    if not 0 < len(text) <= MAX_SOURCE_LENGTH or not text.strip():
        raise ValueError("Invalid text")
    if any(
        ud.category(c) in {"Cs", "Cf"} or (ud.category(c) == "Cc" and c not in ALLOWED_CONTROLS)
        for c in text
    ):
        raise ValueError("Invalid text")
    return text


@dataclass(frozen=True)
class NormalizedText:
    text: str
    source_spans: tuple[tuple[int, int], ...]

    def source_range(self, start: int, end: int) -> tuple[int, int]:
        spans = self.source_spans[start:end]
        if not spans or not 0 <= start < end <= len(self.text):
            raise ValueError("Invalid span")
        return min(s for s, _ in spans), max(e for _, e in spans)


def normalize(source: str) -> NormalizedText:
    validate_text(source)
    units: list[tuple[str, int, int]] = []
    i = 0
    while i < len(source):
        start = i
        c = source[i]
        i += 1
        if c == "\r":
            if i < len(source) and source[i] == "\n":
                i += 1
            c = "\n"
        elif c in "\u2028\u2029":
            c = "\n" if c == "\u2028" else "\n\n"
        if len(c) == 1 and c != "\n" and (c == "\t" or ud.category(c) == "Zs"):
            c = " "
            if units and units[-1][0] == " ":
                _, previous_start, _ = units.pop()
                start = previous_start
        units.append((c, start, i))

    output: list[str] = []
    spans: list[tuple[int, int]] = []
    cluster: list[tuple[str, int, int]] = []

    def emit() -> None:
        if cluster:
            text = ud.normalize("NFC", "".join(c for c, _, _ in cluster))
            output.extend(text)
            spans.extend([(cluster[0][1], cluster[-1][2])] * len(text))
            cluster.clear()

    for unit in units:
        c = unit[0]
        if cluster and ud.combining(c[0]) == 0:
            previous = "".join(part for part, _, _ in cluster)
            # Preserve canonical composition across starter boundaries (e.g. Hangul).
            if ud.normalize("NFC", previous + c) == ud.normalize("NFC", previous) + ud.normalize(
                "NFC", c
            ):
                emit()
        cluster.append(unit)
    emit()
    return NormalizedText("".join(output), tuple(spans))
