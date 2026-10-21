"""Per-engine diagnostics; native scores must never be pooled across engines."""

import math


def pearson(scores: list[float], errors: list[float]) -> float | None:
    if len(scores) != len(errors):
        raise ValueError("paired observations required")
    if len(scores) < 2:
        return None
    xmean, ymean = sum(scores) / len(scores), sum(errors) / len(errors)
    x, y = [v - xmean for v in scores], [v - ymean for v in errors]
    denominator = math.sqrt(sum(v * v for v in x) * sum(v * v for v in y))
    return sum(a * b for a, b in zip(x, y, strict=True)) / denominator if denominator else None


def summarize(engine: str, aligned: list[dict]) -> dict:
    if any(row["engine"] != engine for row in aligned):
        raise ValueError("native confidence scales cannot be pooled")
    correct = [r["confidence"] for r in aligned if r["correct"] and r["confidence"] is not None]
    incorrect = [
        r["confidence"] for r in aligned if not r["correct"] and r["confidence"] is not None
    ]
    return dict(
        engine=engine,
        correct_native_scores=correct,
        incorrect_native_scores=incorrect,
        omissions=sum(r.get("omitted", False) for r in aligned),
        missing_confidence=sum(r["confidence"] is None for r in aligned),
        interpretation="descriptive native scores, not calibrated probabilities",
    )
