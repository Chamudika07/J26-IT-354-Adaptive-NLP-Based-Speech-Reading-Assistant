"""Independent, deterministic unit-cost edit counts; no production tokenizer."""

import re
import unicodedata
from collections.abc import Sequence
from typing import TypedDict

VERSION = "pdf-fidelity-v1"


class Edits(TypedDict):
    substitutions: int
    deletions: int
    insertions: int
    reference_units: int
    rate: float | None
    metric_status: str
    spurious_units: int
    exact_match: bool


def edits(reference: Sequence[str], hypothesis: Sequence[str]) -> Edits:
    """Linear-memory DP. Equal-cost preference: diagonal, deletion, insertion."""
    n = len(reference)
    exact = reference == hypothesis
    # Remove an equal prefix only; counts remain associated with the full reference.
    prefix = 0
    while prefix < min(len(reference), len(hypothesis)):
        if reference[prefix] != hypothesis[prefix]:
            break
        prefix += 1
    r, h = reference[prefix:], hypothesis[prefix:]
    previous = [(0, 0, j) for j in range(len(h) + 1)]
    for i, a in enumerate(r, 1):
        current = [(0, i, 0)]
        for j, b in enumerate(h, 1):
            s, d, ins = previous[j - 1]
            diagonal = (s + int(a != b), d, ins)
            s, d, ins = previous[j]
            deletion = (s, d + 1, ins)
            s, d, ins = current[j - 1]
            insertion = (s, d, ins + 1)
            current.append(min((diagonal, deletion, insertion), key=sum))
        previous = current
    s, d, ins = previous[-1]
    return Edits(
        substitutions=s,
        deletions=d,
        insertions=ins,
        reference_units=n,
        rate=(s + d + ins) / n if n else None,
        metric_status="defined" if n else "undefined_zero_reference",
        spurious_units=len(hypothesis) if not n else 0,
        exact_match=exact,
    )


def fidelity(reference: str, hypothesis: str) -> dict[str, Edits | bool]:
    return {
        "characters": edits(reference, hypothesis),
        "words": edits(re.findall(r"\S+", reference), re.findall(r"\S+", hypothesis)),
        "nfc_exact_match": unicodedata.normalize("NFC", reference)
        == unicodedata.normalize("NFC", hypothesis),
    }


def precedence(text: str, pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    return sum(
        text.count(a) == 1 and text.count(b) == 1 and text.index(a) < text.index(b)
        for a, b in pairs
    ) / len(pairs)


def page_order(expected: list[str], observed: list[str]) -> bool:
    return len(set(observed)) == len(observed) and expected == observed


def micro(rows: list[Edits]) -> Edits:
    n = sum(r["reference_units"] for r in rows)
    s = sum(r["substitutions"] for r in rows)
    d = sum(r["deletions"] for r in rows)
    i = sum(r["insertions"] for r in rows)
    return Edits(
        substitutions=s,
        deletions=d,
        insertions=i,
        reference_units=n,
        rate=(s + d + i) / n if n else None,
        metric_status="defined" if n else "undefined_zero_reference",
        spurious_units=sum(r["spurious_units"] for r in rows),
        exact_match=all(r["exact_match"] for r in rows),
    )
