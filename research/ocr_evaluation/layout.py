"""Explicit annotation-based layout metrics, independent of transcription fidelity."""


def precedence(observed: list[str], pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    return sum(
        observed.count(a) == observed.count(b) == 1 and observed.index(a) < observed.index(b)
        for a, b in pairs
    ) / len(pairs)


def regions(expected: list[str], observed: list[str]) -> dict:
    return {
        "missing": sum(x not in observed for x in expected),
        "duplicate": sum(max(0, observed.count(x) - 1) for x in set(observed)),
        "unexpected": sum(x not in expected for x in observed),
        "line_order_correct": expected == observed,
    }


def table_associations(expected: dict, observed: dict) -> dict:
    counts = dict(missing=0, transcription=0, row=0, column=0)
    for cell, ref in expected.items():
        hyp = observed.get(cell)
        if hyp is None:
            counts["missing"] += 1
            continue
        for key in ("row", "column"):
            counts[key] += hyp[key] != ref[key]
        counts["transcription"] += hyp["text"] != ref["text"]
    return counts
