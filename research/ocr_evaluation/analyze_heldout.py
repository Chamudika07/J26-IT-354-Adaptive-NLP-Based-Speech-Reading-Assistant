"""Read-only analysis using existing frozen fidelity and geometry diagnostic definitions."""

import json

from analyze_development import aggregate, diagnose, match_region
from heldout_execution import INDEX, ROOT, RUN, corpus, verify, write_new
from integrity import digest
from metrics import fidelity

SUMMARY = ROOT / "manifests/heldout-results.v1.json"


def summarize(rows):
    result = aggregate(rows)
    for kind in ("character", "word"):
        for op in ("substitutions", "deletions", "insertions"):
            key = f"{kind}_{op}"
            result[key] = sum(r[key] for r in rows if r["outcome"] == "success")
    result["newline_diagnostic_exact"] = sum(r.get("newline_diagnostic_exact", False) for r in rows)
    return result


def analyze():
    verify()
    cases = {r["fixture_id"]: (r, t, p) for r, t, p in corpus()}
    output = {
        "version": "ocr-heldout-results-v1",
        "execution_index_sha256": digest(INDEX.read_bytes()),
        "engines": {},
        "tuning": False,
    }
    frozen = json.loads((ROOT / "manifests/development-configuration-freeze.v1.json").read_bytes())
    for engine in ("tesseract", "paddle"):
        rows = [
            json.loads(line) for line in (RUN / engine / "pages.jsonl").read_text().splitlines()
        ]
        layouts, phone = [], []
        for row in rows:
            fixture = row["fixture_id"]
            _, truth, _ = cases[fixture]
            hypothesis = (RUN / engine / fixture / f"{fixture}.assembled.txt").read_text()
            reference = truth["transcription"]["text"]
            scores = fidelity(reference, hypothesis)
            for kind, key in (("character", "characters"), ("word", "words")):
                for op in ("substitutions", "deletions", "insertions"):
                    if row[f"{kind}_{op}"] != scores[key][op]:
                        raise ValueError("saved metric mismatch")
            if row["exact_match"] != (reference == hypothesis):
                raise ValueError("saved exact-match mismatch")
            row["newline_diagnostic_exact"] = reference.replace("\n\n", "\n") == hypothesis
            if row["category"] == "phone_camera_photo":
                phone.append(
                    {
                        k: row[k]
                        for k in (
                            "fixture_id",
                            "cer",
                            "wer",
                            "exact_match",
                            "newline_diagnostic_exact",
                            "character_substitutions",
                            "character_deletions",
                            "character_insertions",
                            "word_substitutions",
                            "word_deletions",
                            "word_insertions",
                        )
                    }
                )
                continue  # Master polygons are not registered to camera geometry.
            diagnostic = diagnose(row, truth)
            pairs = truth["layout"]["precedence"]
            sequence = diagnostic["observed_region_sequence"]
            diagnostic["required_pairs"] = pairs
            diagnostic["passed_pairs"] = [
                [a, b]
                for a, b in pairs
                if sequence.count(a) == sequence.count(b) == 1
                and sequence.index(a) < sequence.index(b)
            ]
            grouped = {b["id"]: [] for b in truth["layout"]["blocks"]}
            for unit in row["evidence"]["units"]:
                region = match_region(unit.get("polygon"), truth["layout"]["blocks"])
                if region is not None:
                    grouped[region].append(unit["text"])
            diagnostic["cell_evidence"] = [
                {"id": c["id"], "expected": c["text"], "observed": " ".join(grouped[c["id"]])}
                for c in truth["layout"]["cells"]
            ]
            layouts.append(diagnostic)
        selected = frozen["selected"][engine]
        dev = []
        for run in (selected["ao_run"], selected["photo_run"]):
            dev.extend(
                json.loads(line)
                for line in (ROOT / "artifacts" / run / "pages.jsonl").read_text().splitlines()
            )
        output["engines"][engine] = dict(
            overall=summarize(rows),
            categories={
                category: summarize([r for r in rows if r["category"] == category])
                for category in sorted({r["category"] for r in rows})
            },
            phone=phone,
            layout=layouts,
            development=aggregate(dev),
            development_categories={
                category: aggregate([r for r in dev if r["category"] == category])
                for category in sorted({r["category"] for r in dev})
            },
            photo_spatial_diagnostics="Unavailable: master polygons are not camera coordinates.",
        )
    return output


if __name__ == "__main__":
    result = analyze()
    write_new(SUMMARY, result)
    print(
        json.dumps(
            {
                k: {"overall": v["overall"], "phone": v["phone"]}
                for k, v in result["engines"].items()
            },
            indent=2,
        )
    )
