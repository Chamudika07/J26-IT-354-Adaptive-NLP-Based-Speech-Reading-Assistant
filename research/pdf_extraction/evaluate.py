"""Serial source-validated experiments. JSONL is authoritative; no implicit reruns."""

import argparse
import json
import math
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

from adapters import production_extractor as adapter
from generators.corpus import generate, write_json
from metrics import VERSION, fidelity, micro, page_order, precedence
from schemas import Manifest, Result, digest, read_text, resolve, validate_artifacts

HERE = Path(__file__).resolve().parent
FROZEN_FILES = [
    "protocol.md",
    "metrics.py",
    "schemas/__init__.py",
    "adapters/production_extractor.py",
    "generators/corpus.py",
    "evaluate.py",
    "report.py",
    "uv.lock",
    "pyproject.toml",
    "manifests/benchmark.schema.json",
]


def ordered(fixtures, seed):
    items = sorted(fixtures, key=lambda f: f.fixture_id)
    random.Random(seed).shuffle(items)
    return items


def freeze_contract():
    return {
        "files": {p: digest(HERE / p) for p in FROZEN_FILES},
        "production_commit": adapter.commit(),
        "fingerprint": adapter.contracts.fingerprint(),
    }


def load_manifest(path, root):
    manifest = Manifest.model_validate_json(path.read_text())
    validate_artifacts(manifest, root)
    if manifest.production_commit != adapter.commit():
        raise ValueError("production commit differs from manifest")
    import subprocess

    if subprocess.check_output(
        ["git", "status", "--porcelain", "--", "apps/backend"], cwd=adapter.ROOT
    ):
        raise ValueError("production tree is modified")
    return manifest


def measure(fixture, root, raw, experiment, commit, timings):
    reference = read_text(resolve(root, fixture.assembled_ground_truth.reference))
    hypothesis = raw["assembled_text"] or ""
    assembled = fidelity(reference, hypothesis)
    c, w = assembled["characters"], assembled["words"]
    eligible = fixture.metric_eligibility
    expected_pages = [read_text(resolve(root, p.reference)) for p in fixture.page_ground_truth]
    observed_pages = [hypothesis[p["text_start"] : p["text_end"]] for p in raw["pages"]]
    if raw["pages"]:
        if "\n\n".join(observed_pages) != hypothesis:
            raise ValueError("runner offsets do not reproduce assembly")
        if [p["page_number"] for p in raw["pages"]] != list(range(1, len(observed_pages) + 1)):
            raise ValueError("invalid page numbering")
    per_page = [
        fidelity(
            expected_pages[i] if i < len(expected_pages) else "",
            observed_pages[i] if i < len(observed_pages) else "",
        )
        for i in range(max(len(expected_pages), len(observed_pages)))
    ]
    structure = json.loads(resolve(root, fixture.structural_annotation.reference).read_text())
    visible_ref = structure["visible_ground_truth"]
    if digest(resolve(root, visible_ref["reference"])) != visible_ref["sha256"]:
        raise ValueError("visible ground truth hash mismatch")
    visible = fidelity(read_text(resolve(root, visible_ref["reference"])), hypothesis)
    block_score = precedence(hypothesis, structure["precedence_pairs"])
    observed_ids = []
    for text in observed_pages:
        matches = [pid for pid in structure["page_ids"] if text.count(pid) == 1]
        observed_ids.append(matches[0] if len(matches) == 1 else "MISSING_OR_AMBIGUOUS")
    page_ok = (
        page_order(structure["page_ids"], observed_ids) if structure["page_id_testable"] else None
    )
    normalized, normalization_reason = None, None
    try:
        normalized = fidelity(adapter.normalized(reference), adapter.normalized(hypothesis))
    except ValueError:
        normalization_reason = "production normalization rejects reference or hypothesis"
    table = {
        "missing_or_altered_cells": [],
        "broken_row_associations": [],
        "broken_column_associations": [],
    }
    rows = structure["table_rows"]
    for row in rows:
        for cell in row:
            if hypothesis.count(cell) != 1:
                table["missing_or_altered_cells"].append(cell)
        if "\n".join(row) + "\n" not in hypothesis:
            table["broken_row_associations"].append(row)
    for column in zip(*rows, strict=True) if rows else []:
        if precedence(hypothesis, list(zip(column, column[1:], strict=False))) != 1:
            table["broken_column_associations"].append(list(column))
    codes = []
    if raw["status"] == "failed":
        label = "extraction_failure"
    elif (
        fixture.content_assessment in {"missing_visible_content", "ordering_problem"}
        or block_score not in (None, 1)
        or page_ok is False
    ):
        label = "needs_review"
        codes.append("visible_omission_or_order_failure")
    elif not c["exact_match"]:
        label = "acceptable_with_limitation" if w["exact_match"] else "needs_review"
        codes.append("raw_text_difference")
    else:
        label = "correct"
    return Result(
        experiment_id=experiment,
        fixture_id=fixture.fixture_id,
        category=fixture.primary_category,
        split=fixture.split,
        source_sha256=fixture.source_sha256,
        source_byte_count=fixture.source_byte_count,
        expected_page_count=fixture.expected_page_count,
        observed_page_count=len(raw["pages"]) if raw["status"] != "failed" else None,
        expected_outcome=fixture.expected_policy_outcome,
        actual_outcome=raw["status"],
        outcome_code=raw["outcome_code"],
        extraction_fingerprint=raw["fingerprint"],
        production_commit=commit,
        metric_version=VERSION,
        character_substitutions=c["substitutions"],
        character_deletions=c["deletions"],
        character_insertions=c["insertions"],
        reference_character_count=c["reference_units"],
        word_substitutions=w["substitutions"],
        word_deletions=w["deletions"],
        word_insertions=w["insertions"],
        reference_word_count=w["reference_units"],
        raw_page_cer=micro([p["characters"] for p in per_page])["rate"] if eligible else None,
        raw_assembled_cer=c["rate"] if eligible else None,
        raw_wer=w["rate"] if eligible else None,
        normalized_cer=normalized["characters"]["rate"] if normalized and eligible else None,
        normalized_wer=normalized["words"]["rate"] if normalized and eligible else None,
        exact_match=c["exact_match"] if eligible else None,
        metric_status=c["metric_status"] if eligible else "excluded_invalid_or_unsupported",
        lexical_page_coverage=sum(p["lexical_word_count"] > 0 for p in raw["pages"])
        / len(raw["pages"])
        if raw["pages"]
        else None,
        page_order_correct=page_ok,
        block_order_score=block_score,
        review_label=label,
        review_codes=codes,
        latency_median_ms=statistics.median(timings),
        notes=fixture.known_limitations,
        detail={
            "raw": raw,
            "fidelity": assembled,
            "visible_fidelity": visible,
            "raw_pages": per_page,
            "normalized": normalized,
            "normalization_reason": normalization_reason,
            "table_failures": table,
            "content_assessment": fixture.content_assessment,
            "metric_eligible": eligible,
            "exact_match_required": fixture.exact_match_required,
            "page_order_reason": None if page_ok is not None else "no embedded page ID available",
            "block_order_reason": None if block_score is not None else "no prescribed pairs",
            "missing_output": raw["assembled_text"] is None,
            "latency_min_ms": min(timings),
            "latency_max_ms": max(timings),
            "latency_population_stdev_ms": statistics.pstdev(timings),
        },
    )


def run(manifest, root, output, split, resume=False):
    fixtures = ordered(
        [f for f in manifest.fixture_entries if f.split == split], manifest.split_seed
    )
    expected_count = 22 if split == "development" else 44
    if len(fixtures) != expected_count:
        raise ValueError(f"expected exactly {expected_count} fixtures")
    if split == "heldout":
        frozen = json.loads((root / "freeze.json").read_text())
        if frozen != freeze_contract():
            raise ValueError("frozen harness differs; use a separately reviewed experiment")
        if (root / "heldout-manifest.sha256").read_text().strip() != digest(root / "manifest.json"):
            raise ValueError("held-out manifest changed")
    metadata = {
        "environment": adapter.environment(),
        "metric_version": VERSION,
        "manifest_sha256": digest(root / "manifest.json"),
        "benchmark_version": manifest.benchmark_version,
        "protocol_version": manifest.protocol_version,
        "order": [f.fixture_id for f in fixtures],
        "seed": manifest.split_seed,
        "warmups": 2,
        "repetitions": 10,
        "freeze": freeze_contract(),
    }
    if output.exists():
        if not resume or split == "heldout":
            raise ValueError(
                "output exists; held-out primary runs cannot be resumed or overwritten"
            )
        if json.loads((output / "environment.json").read_text()) != metadata:
            raise ValueError("resume provenance mismatch")
    else:
        output.mkdir(parents=True)
        write_json(output / "environment.json", metadata)
    result_path = output / "results.jsonl"
    completed = set()
    if result_path.exists():
        completed = {
            Result.model_validate_json(line).fixture_id
            for line in result_path.read_text().splitlines()
        }
    if split == "heldout":
        with (root / "heldout-primary-claim.json").open("x") as claim:
            json.dump(
                {"output": str(output.resolve()), "started_utc": datetime.now(UTC).isoformat()},
                claim,
            )
    # Preserve the exact manifest at execution time; later held-out generation extends it.
    if not (output / "manifest.json").exists():
        (output / "manifest.json").write_bytes((root / "manifest.json").read_bytes())
    with result_path.open("a") as results, (output / "timings.jsonl").open("a") as timing:
        for f in fixtures:
            if f.fixture_id in completed:
                continue
            path = resolve(root, f.source_artifact_reference)
            for _ in range(2):
                adapter.extract(path)
            times, primary = [], None
            for repetition in range(10):
                raw = adapter.extract(path)
                if primary is None:
                    primary = raw
                times.append(raw["elapsed_ms"])
                timing.write(
                    json.dumps({"fixture_id": f.fixture_id, "repetition": repetition, "raw": raw})
                    + "\n"
                )
                timing.flush()
            result = measure(f, root, primary, output.name, manifest.production_commit, times)
            results.write(result.model_dump_json() + "\n")
            results.flush()
            print(f"{f.fixture_id}: {result.actual_outcome}", flush=True)
    if metadata["freeze"] != freeze_contract():
        raise ValueError("harness changed during run; preserve as interrupted experiment")
    from report import report

    report(output)
    if split == "development":
        write_json(
            root / "development-complete.json",
            {
                "freeze": freeze_contract(),
                "manifest_sha256": digest(root / "manifest.json"),
                "results_sha256": digest(result_path),
                "output": str(output.resolve()),
            },
        )


def performance(manifest, root, output):
    # Development-only subset: simple, multipage, two-column; no held-out re-evaluation.
    fixtures = [
        next(
            f
            for f in manifest.fixture_entries
            if f.split == "development" and f.primary_category == c
        )
        for c in ("simple_single_column", "multipage", "two_column")
    ]
    output.mkdir(parents=True, exist_ok=False)
    write_json(
        output / "environment.json",
        {
            "environment": adapter.environment(),
            "manifest_sha256": digest(root / "manifest.json"),
            "metric_version": VERSION,
            "benchmark_version": manifest.benchmark_version,
            "protocol_version": manifest.protocol_version,
            "freeze": freeze_contract(),
            "order": [f.fixture_id for f in fixtures],
            "warmups": 2,
            "repetitions": 100,
        },
    )
    (output / "manifest.json").write_bytes((root / "manifest.json").read_bytes())
    summary = []
    with (output / "timings.jsonl").open("x") as stream:
        for f in fixtures:
            path = resolve(root, f.source_artifact_reference)
            for _ in range(2):
                adapter.extract(path)
            times = []
            for repetition in range(100):
                raw = adapter.extract(path)
                times.append(raw["elapsed_ms"])
                stream.write(
                    json.dumps({"fixture_id": f.fixture_id, "repetition": repetition, "raw": raw})
                    + "\n"
                )
                stream.flush()
            summary.append(
                {
                    "fixture_id": f.fixture_id,
                    "n": 100,
                    "min_ms": min(times),
                    "max_ms": max(times),
                    "population_stdev_ms": statistics.pstdev(times),
                    "median_ms": statistics.median(times),
                    "empirical_p95_ms": sorted(times)[math.ceil(0.95 * len(times)) - 1],
                }
            )
    write_json(output / "summary.json", summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["generate", "validate", "freeze", "run", "performance", "report"]
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "heldout"], default="development")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        # Require ignored artifact location or an external directory; never code/production paths.
        for path in [root, args.output.resolve() if args.output else root]:
            if path.is_relative_to(adapter.ROOT) and not (
                path.is_relative_to(adapter.ROOT / "research/artifacts")
                or path.is_relative_to(HERE / "artifacts")
            ):
                raise ValueError(
                    "repository outputs require an ignored research artifacts directory"
                )
        manifest_path = root / "manifest.json"
        if args.command == "generate":
            existing = load_manifest(manifest_path, root) if manifest_path.exists() else None
            if args.split == "heldout":
                if json.loads((root / "freeze.json").read_text()) != freeze_contract():
                    raise ValueError("freeze required before held-out generation")
            manifest = generate(root, args.split, adapter.commit(), existing)
            validate_artifacts(manifest, root)
            manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n")
            if args.split == "heldout":
                (root / "heldout-manifest.sha256").write_text(digest(manifest_path) + "\n")
        elif args.command == "report":
            from report import report

            if not args.output:
                raise ValueError("--output required")
            report(args.output)
        else:
            manifest = load_manifest(manifest_path, root)
            if args.command == "freeze":
                if (root / "freeze.json").exists():
                    raise ValueError("freeze already exists")
                development = json.loads((root / "development-complete.json").read_text())
                if development["freeze"] != freeze_contract():
                    raise ValueError("development run must use the final harness before freezing")
                if development["manifest_sha256"] != digest(manifest_path):
                    raise ValueError("development manifest changed")
                if development["results_sha256"] != digest(
                    Path(development["output"]) / "results.jsonl"
                ):
                    raise ValueError("development results changed")
                write_json(root / "freeze.json", freeze_contract())
            elif args.command in {"run", "performance"}:
                if not args.output:
                    raise ValueError("--output required")
                if args.command == "performance":
                    performance(manifest, root, args.output)
                else:
                    run(manifest, root, args.output, args.split, args.resume)
    except (ValueError, OSError) as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
