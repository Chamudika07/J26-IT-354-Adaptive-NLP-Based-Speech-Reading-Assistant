"""Verify immutable final evidence and recompute frozen metrics, without OCR execution."""

import json

from analyze_heldout import SUMMARY, analyze
from heldout_execution import ROOT, RUN, verify
from integrity import digest

RECORD = ROOT / "manifests/heldout-final-record.v1.json"


def verify_results():
    report = verify()
    final = json.loads(RECORD.read_bytes())
    for name, expected in final["file_sha256"].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path.read_bytes()) != expected:
            raise ValueError("final evidence hash mismatch")
    if json.loads(SUMMARY.read_bytes()) != analyze():
        raise ValueError("recomputed analysis differs")
    count = 0
    for folder in (ROOT / "artifacts", ROOT / "results"):
        for path in folder.rglob("*.jsonl"):
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if row.get("split") == "heldout" or "-heldout-" in row.get("fixture_id", ""):
                    if path not in {RUN / e / "pages.jsonl" for e in ("tesseract", "paddle")}:
                        raise ValueError("additional held-out result stream detected")
                    count += 1
    if count != 96:
        raise ValueError("global held-out execution count mismatch")
    return dict(report, metrics="recomputed_and_verified", recommendation=final["recommendation"])


if __name__ == "__main__":
    print(json.dumps(verify_results()))
