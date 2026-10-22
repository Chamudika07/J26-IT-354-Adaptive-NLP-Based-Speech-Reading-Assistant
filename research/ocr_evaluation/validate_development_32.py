"""Audit the 30 synthetic A–O sources plus two genuine development photos."""

import argparse
import json
from collections import Counter
from pathlib import Path

from development import prepare_cases
from integrity import canonical
from photo_development import prepare_photos
from preprocessing.recipes import decode, pixel_digest

ROOT = Path(__file__).resolve().parent


def validate(output: Path) -> dict:
    manifest = ROOT / "manifests/benchmark.v1.json"
    cases = prepare_cases(ROOT / "artifacts/development-drafts-v3/index.json", manifest)
    cases += prepare_photos(ROOT / "manifests/phone-development.v1.json", manifest)
    categories = Counter(record["category"] for record, _, _ in cases)
    sources = set()
    families = set()
    for record, truth, path in cases:
        image = decode(path, "image/jpeg" if path.suffix == ".jpg" else "image/png")
        try:
            if pixel_digest(image) != record["input_pixel_digest"]:
                raise ValueError("development source pixel mismatch")
        finally:
            image.close()
        if truth["fixture_id"] != record["fixture_id"] or record["split"] != "development":
            raise ValueError("development identity mismatch")
        sources.add(record["source_digest"])
        families.add(record["source_family_id"])
    if (
        len(cases) != 32
        or len(sources) != 32
        or len(families) != 32
        or len(categories) != 16
        or any(count != 2 for count in categories.values())
    ):
        raise ValueError("development coverage mismatch")
    result = {
        "version": "ocr-development-validation-32-v1",
        "status": "pass",
        "cases": 32,
        "synthetic_ao_cases": 30,
        "genuine_phone_photo_cases": 2,
        "distinct_source_bytes": len(sources),
        "distinct_source_families": len(families),
        "categories": dict(sorted(categories.items())),
        "heldout_cases_opened": 0,
        "limitation": (
            "Phone photos contain only two short lines each; no general photo robustness claim."
        ),
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "validation.json").write_bytes(canonical(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.output)))
