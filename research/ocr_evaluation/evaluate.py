"""Validation CLI. Final execution stays closed until the research gates are qualified."""

import argparse
import json
from pathlib import Path

from integrity import read_manifest, verify_artifact, verify_freeze
from photos import require_phone_photos
from schemas import Artifact, Manifest, PageResult

ROOT = Path(__file__).resolve().parent


def validate_artifacts(path: Path, root: Path) -> None:
    data = json.loads(path.read_bytes())
    if data.get("version") != "ocr-artifacts-v1" or not data.get("artifacts"):
        raise ValueError("unprovisioned artifact manifest")
    for row in data["artifacts"]:
        verify_artifact(root, Artifact.model_validate(row))


def claim_holdout(root: Path, manifest: Manifest, freeze_path: Path) -> Path:
    verify_freeze(root, freeze_path)
    if any(c.status != "verified" for c in manifest.cases):
        raise ValueError("all base cases must be verified before heldout")
    require_phone_photos(root)
    # A single fixed claim per benchmark, independent of chosen result directory.
    claim = root / "artifacts" / "heldout-primary-v1.claim"
    claim.parent.mkdir(parents=True, exist_ok=True)
    with claim.open("x") as stream:
        stream.write("Claimed. Interrupted/failed runs require explicit protocol amendment.\n")
    return claim


def write_jsonl(path: Path, rows: list[PageResult]) -> None:
    with path.open("x") as stream:
        for row in sorted(rows, key=lambda r: (r.fixture_id, r.page_number, r.engine)):
            stream.write(row.model_dump_json() + "\n")


def require_development(split: str) -> None:
    if split != "development":
        raise ValueError("tuning is development-only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true", required=True)
    args = parser.parse_args()
    manifest = read_manifest(ROOT / "manifests/benchmark.v1.json")
    print(
        json.dumps(
            {
                "planned_bases": sum(c.parent_id is None for c in manifest.cases),
                "development": sum(c.split == "development" for c in manifest.cases),
                "heldout": sum(c.split == "heldout" for c in manifest.cases),
                "verified": sum(c.status == "verified" for c in manifest.cases),
            }
        )
    )
