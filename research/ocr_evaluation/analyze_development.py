"""Geometry-linked diagnostics, separate from primary raw transcription metrics."""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from confidence import pearson
from integrity import canonical
from layout import precedence


def bounds(polygon):
    return (
        min(p[0] for p in polygon),
        min(p[1] for p in polygon),
        max(p[0] for p in polygon),
        max(p[1] for p in polygon),
    )


def match_region(polygon, blocks):
    if not polygon:
        return None
    x0, y0, x1, y1 = bounds(polygon)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    candidates = []
    for block in blocks:
        a, b, c, d = bounds(block["polygon"])
        # Fixed 12 source-pixel tolerance; only geometry is used, never recognized text.
        if a - 12 <= cx <= c + 12 and b - 12 <= cy <= d + 12:
            overlap = max(0, min(x1, c + 12) - max(x0, a - 12)) * max(
                0, min(y1, d + 12) - max(y0, b - 12)
            )
            candidates.append((overlap, block["id"]))
    return max(candidates)[1] if candidates else None


def diagnose(row, truth):
    blocks = truth["layout"]["blocks"]
    by_id = {b["id"]: b for b in blocks}
    grouped = {b["id"]: [] for b in blocks}
    sequence = []
    unmatched = 0
    confidence_correct = []
    confidence_error = []
    missing_confidence = 0
    remaining = {b["id"]: Counter(b["text"].split()) for b in blocks}
    for unit in row["evidence"]["units"]:
        region = match_region(unit.get("polygon"), blocks)
        if region is None:
            unmatched += 1
        else:
            grouped[region].append(unit["text"])
            if not sequence or sequence[-1] != region:
                sequence.append(region)
        if row["engine"] == "paddle":
            correct = region is not None and unit["text"] == by_id[region]["text"]
        else:
            correct = region is not None and remaining[region][unit["text"]] > 0
            if correct:
                remaining[region][unit["text"]] -= 1
        conf = unit["confidence"]
        if conf is None:
            missing_confidence += 1
        elif correct:
            confidence_correct.append(conf)
        else:
            confidence_error.append(conf)
    cells = truth["layout"]["cells"]
    return dict(
        fixture_id=row["fixture_id"],
        category=row["category"],
        block_precedence=precedence(sequence, [tuple(p) for p in truth["layout"]["precedence"]]),
        observed_region_sequence=sequence,
        missing_regions=sum(not v for v in grouped.values()),
        duplicate_region_segments=sum(max(0, sequence.count(k) - 1) for k in grouped),
        unmatched_units=unmatched,
        table_cells=len(cells),
        table_exact_cells=sum(" ".join(grouped[c["id"]]) == c["text"] for c in cells),
        table_missing_cells=sum(not grouped[c["id"]] for c in cells),
        native_table_row_association=None,
        native_table_column_association=None,
        table_association_reason=(
            "Neither adapter emits semantic table membership; geometry matching is diagnostic only."
        ),
        confidence_correct=confidence_correct,
        confidence_error=confidence_error,
        missing_confidence=missing_confidence,
        confidence_method=(
            "geometry-linked exact line (Paddle) or token multiset (Tesseract); "
            "not a calibrated comparison"
        ),
    )


def aggregate(rows):
    success = [r for r in rows if r["outcome"] == "success"]
    result = dict(
        pages=len(rows),
        successful=len(success),
        failed=len(rows) - len(success),
        exact_match=sum(r["exact_match"] is True for r in success),
    )
    for kind, rate in [("character", "cer"), ("word", "wer")]:
        denominator = sum(r[f"reference_{kind}_count"] for r in success)
        errors = sum(
            r[f"{kind}_{op}"]
            for r in success
            for op in ["substitutions", "deletions", "insertions"]
        )
        result[rate] = errors / denominator if denominator else None
        result[rate + "_errors"] = errors
        result[rate + "_denominator"] = denominator
    times = [r["latency_ms"]["engine_process_including_load"] for r in success]
    result["cold_engine_ms"] = (
        dict(
            median=statistics.median(times),
            minimum=min(times),
            maximum=max(times),
            population_sd=statistics.pstdev(times),
        )
        if times
        else None
    )
    confidence = []
    cers = []
    for r in success:
        values = [u["confidence"] for u in r["evidence"]["units"] if u["confidence"] is not None]
        if values and r["cer"] is not None:
            confidence.append(statistics.mean(values))
            cers.append(r["cer"])
    result["mean_page_confidence_vs_cer_pearson"] = pearson(confidence, cers)
    return result


def analyze(run_dir, corpus_dir):
    rows = [json.loads(line) for line in (run_dir / "pages.jsonl").read_text().splitlines()]
    diagnostics = []
    memory = []
    load = []
    ocr = []
    for row in rows:
        if row["outcome"] != "success":
            continue
        truth = json.loads((corpus_dir / (row["fixture_id"] + ".truth.json")).read_bytes())
        diagnostics.append(diagnose(row, truth))
        if row["engine"] == "paddle":
            native = json.loads((run_dir / (row["fixture_id"] + ".native.txt")).read_bytes())
            measurements = native.get("research_measurements", {})
            if measurements:
                memory.append(measurements["worker_peak_rss_bytes"])
                load.append(measurements["load_ms"])
                ocr.append(measurements["ocr_ms"])
    summary = aggregate(rows)
    summary["categories"] = {
        cat: aggregate([r for r in rows if r["category"] == cat])
        for cat in sorted({r["category"] for r in rows})
    }
    summary["worker_rss_bytes"] = (
        dict(median=statistics.median(memory), maximum=max(memory)) if memory else None
    )
    summary["memory_method"] = "Paddle worker-only getrusage; process-tree peak unavailable"
    summary["paddle_model_load_median_ms"] = statistics.median(load) if load else None
    summary["paddle_ocr_median_ms"] = statistics.median(ocr) if ocr else None
    summary["layout"] = diagnostics
    with (run_dir / "diagnostics.json").open("xb") as stream:
        stream.write(canonical(summary))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--corpus", type=Path, default=Path("artifacts/development-drafts-v3"))
    args = parser.parse_args()
    print(json.dumps(analyze(args.run_dir, args.corpus), indent=2))
