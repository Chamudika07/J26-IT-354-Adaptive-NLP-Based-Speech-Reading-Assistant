"""Deterministic JSON, CSV and Markdown summaries from validated authoritative JSONL."""

import csv
import json
from collections import Counter

from metrics import micro
from schemas import OUTCOMES, Result


def aggregate(records):
    eligible = [r for r in records if r.detail["metric_eligible"]]
    returned = [r for r in eligible if not r.detail["missing_output"]]
    matrix = {e: {a: 0 for a in OUTCOMES} for e in OUTCOMES}
    for r in records:
        matrix[r.expected_outcome][r.actual_outcome] += 1

    def fidelity_summary(rows):
        return {
            unit: micro([r.detail["fidelity"][unit] for r in rows])
            for unit in ("characters", "words")
        }

    complete = [r for r in records if r.detail["content_assessment"] == "complete"]
    return {
        "documents": len(records),
        "categories": dict(Counter(r.category for r in records)),
        "operational_fidelity": fidelity_summary(eligible),
        "returned_fidelity": fidelity_summary(returned),
        "raw_page_micro_cer": micro(
            [p["characters"] for r in eligible for p in r.detail["raw_pages"]]
        ),
        "visible_fidelity": {
            unit: micro([r.detail["visible_fidelity"][unit] for r in eligible])
            for unit in ("characters", "words")
        },
        "normalized_secondary": {
            unit: micro(
                [
                    r.detail["normalized"][unit]
                    for r in eligible
                    if r.detail["normalized"] is not None
                ]
            )
            for unit in ("characters", "words")
        },
        "page_order": dict(Counter(str(r.page_order_correct) for r in eligible)),
        "block_order": {
            "documents_with_pairs": sum(r.block_order_score is not None for r in eligible),
            "documents_with_failures": sum(r.block_order_score not in (None, 1) for r in eligible),
        },
        "tables": {
            key: sum(len(r.detail["table_failures"][key]) for r in eligible)
            for key in (
                "missing_or_altered_cells",
                "broken_row_associations",
                "broken_column_associations",
            )
        },
        "required_exact_match_failures": [
            r.fixture_id for r in eligible if r.detail["exact_match_required"] and not r.exact_match
        ],
        "category_fidelity": {
            c: fidelity_summary([r for r in eligible if r.category == c])
            for c in sorted({r.category for r in eligible})
        },
        "exact_match": {
            c: {
                "exact": sum(r.exact_match is True for r in eligible if r.category == c),
                "eligible": sum(r.category == c for r in eligible),
            }
            for c in sorted({r.category for r in eligible})
        },
        "routing_counts": matrix,
        "routing_row_percent": {
            e: {
                a: 100 * n / sum(row.values()) if sum(row.values()) else None
                for a, n in row.items()
            }
            for e, row in matrix.items()
        },
        "policy_agreement": sum(r.expected_outcome == r.actual_outcome for r in records)
        / len(records)
        if records
        else None,
        "review_labels": dict(Counter(r.review_label for r in records)),
        "failure_codes": dict(Counter(r.outcome_code for r in records if r.outcome_code)),
        "metric_statuses": dict(Counter(r.metric_status for r in records)),
        "complete_documents": len(complete),
        "unnecessary_review_complete": sum(r.actual_outcome == "needs_review" for r in complete),
        "accepted_visible_omissions": sum(
            r.actual_outcome == "extracted"
            and r.detail["content_assessment"] == "missing_visible_content"
            for r in records
        ),
        "accepted_ordering_problems": sum(
            r.actual_outcome == "extracted"
            and (
                r.detail["content_assessment"] == "ordering_problem"
                or r.block_order_score not in (None, 1)
                or r.page_order_correct is False
            )
            for r in records
        ),
        "performance": [
            {
                "fixture_id": r.fixture_id,
                "median_ms": r.latency_median_ms,
                **{k: v for k, v in r.detail.items() if k.startswith("latency_")},
            }
            for r in records
        ],
        "limitations": [
            "Exploratory synthetic corpus; not representative PDF accuracy or OCR accuracy.",
            "One authoring engine; logical source annotations have no independent human raters.",
            "Missing output is empty in operational metrics; unsupported files excluded.",
            "Primary embedded metrics exclude raster text; visible diagnostic separate.",
            "No reliable child peak RSS; no macOS hard memory cap. Laptop timings are local only.",
            "Ten repetitions do not establish a stable p95. Dedicated subset uses 100.",
        ],
    }


def report(output):
    records = [
        Result.model_validate_json(line)
        for line in (output / "results.jsonl").read_text().splitlines()
    ]
    if len({r.fixture_id for r in records}) != len(records):
        raise ValueError("duplicate result IDs")
    summary = aggregate(records)
    timing_path = output / "timings.jsonl"
    if timing_path.exists():
        repetitions = [json.loads(line) for line in timing_path.read_text().splitlines()]
        primary = {r.fixture_id: r.actual_outcome for r in records}
        summary["repetition_outcomes"] = dict(Counter(t["raw"]["status"] for t in repetitions))
        summary["repetition_outcome_disagreements"] = sum(
            t["raw"]["status"] != primary.get(t["fixture_id"]) for t in repetitions
        )
    environment_path = output / "environment.json"
    if environment_path.exists():
        summary["provenance"] = json.loads(environment_path.read_text())
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (output / "summary.csv").open("w", newline="") as stream:
        fields = [k for k in Result.model_fields if k not in {"detail", "notes", "review_codes"}]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({k: v for k, v in record.model_dump().items() if k in fields})
    lines = [
        "# Direct PDF extraction evaluation",
        "",
        f"Documents: {len(records)}",
        "",
        "## Routing (expected rows, actual columns)",
        "",
        "| Expected | " + " | ".join(OUTCOMES) + " |",
        "|---|---|---|---|---|",
    ]
    for expected, row in summary["routing_counts"].items():
        lines.append("| " + expected + " | " + " | ".join(str(n) for n in row.values()) + " |")
    lines += [
        "",
        "## Fidelity and findings",
        "",
        "```json",
        json.dumps({k: v for k, v in summary.items() if k != "performance"}, indent=2),
        "```",
        "",
        "## Performance",
        "",
        "| Fixture | Median ms | Min ms | Max ms | SD ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summary["performance"]:
        lines.append(
            f"| {row['fixture_id']} | {row['median_ms']:.3f} | "
            f"{row['latency_min_ms']:.3f} | {row['latency_max_ms']:.3f} | "
            f"{row['latency_population_stdev_ms']:.3f} |"
        )
    (output / "report.md").write_text("\n".join(lines) + "\n")
