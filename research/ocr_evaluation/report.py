"""JSONL summaries: aggregate edit counts, never average page error rates."""

import argparse
import json
import math
import statistics
from pathlib import Path

from schemas import PageResult


def performance(values: list[float]) -> dict:
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("invalid timing sample")
    return {
        "n": len(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "population_sd": statistics.pstdev(values),
        "p95": sorted(values)[math.ceil(0.95 * len(values)) - 1] if len(values) >= 100 else None,
        "p95_reason": None if len(values) >= 100 else "requires dedicated 100-run subset",
    }


def summarize(rows: list[PageResult]) -> dict:
    groups = {}
    for row in rows:
        key = (row.engine, row.split, row.category)
        groups.setdefault(key, []).append(row)
    output = []
    for key, members in sorted(groups.items()):
        entry = dict(zip(("engine", "split", "category"), key, strict=True))
        entry["failures"] = sum(r.outcome == "failed" for r in members)
        entry["pages"] = len(members)
        for kind, rate in (("character", "cer"), ("word", "wer")):
            valid = [
                r
                for r in members
                if r.outcome == "success" and getattr(r, f"reference_{kind}_count") is not None
            ]
            denom = sum(getattr(r, f"reference_{kind}_count") for r in valid)
            errors = sum(
                getattr(r, f"{kind}_{e}") or 0
                for r in valid
                for e in ("substitutions", "deletions", "insertions")
            )
            entry[rate] = errors / denom if denom else None
            entry[rate + "_denominator"] = denom
            entry[rate + "_errors"] = errors
        output.append(entry)
    return {"groups": output, "selection": "not determined; mandatory gates and evidence required"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    args = parser.parse_args()
    rows = [PageResult.model_validate_json(line) for line in args.jsonl.read_bytes().splitlines()]
    print(json.dumps(summarize(rows), indent=2))
