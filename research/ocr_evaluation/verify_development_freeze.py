"""Verify the development-only freeze without opening held-out data."""

import hashlib
import json
from pathlib import Path

from development import prepare_cases
from photo_development import prepare_photos

ROOT = Path(__file__).resolve().parent


def verify(path: Path) -> dict:
    frozen = json.loads(path.read_bytes())
    if (
        frozen["version"] != "ocr-development-configuration-freeze-v1"
        or frozen["status"] != "development_configuration_frozen"
        or frozen["heldout_executions"] != 0
        or frozen["production_engine_selected"] is not False
    ):
        raise ValueError("invalid development freeze")
    for relative, expected in frozen["file_sha256"].items():
        target = (ROOT / relative).resolve()
        if (
            not target.is_relative_to(ROOT)
            or hashlib.sha256(target.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("development freeze file hash mismatch")
    for selected in frozen["selected"].values():
        for artifact in selected["model_artifacts"]:
            target = (ROOT / "models" / artifact["path"]).resolve()
            if not target.is_relative_to(ROOT / "models"):
                raise ValueError("model path escapes research directory")
            if hashlib.sha256(target.read_bytes()).hexdigest() != artifact["sha256"]:
                raise ValueError("development model hash mismatch")
        for run, config_key, fingerprint_key, count in (
            (selected["ao_run"], "ao_config_sha256", "ao_configuration_fingerprint", 30),
            (selected["photo_run"], "photo_config_sha256", "photo_configuration_fingerprint", 2),
        ):
            directory = ROOT / "artifacts" / run
            if (
                hashlib.sha256((directory / "config.json").read_bytes()).hexdigest()
                != selected[config_key]
            ):
                raise ValueError("development configuration hash mismatch")
            rows = [
                json.loads(line) for line in (directory / "pages.jsonl").read_text().splitlines()
            ]
            if (
                len(rows) != count
                or any(row["outcome"] != "success" or row["split"] != "development" for row in rows)
                or {row["configuration_fingerprint"] for row in rows} != {selected[fingerprint_key]}
            ):
                raise ValueError("development run mismatch")
    manifest = ROOT / "manifests/benchmark.v1.json"
    cases = prepare_cases(ROOT / "artifacts/development-drafts-v3/index.json", manifest)
    cases += prepare_photos(ROOT / "manifests/phone-development.v1.json", manifest)
    if len(cases) != 32 or len({case[0]["fixture_id"] for case in cases}) != 32:
        raise ValueError("development corpus mismatch")
    expected = {record["fixture_id"]: record for record, _, _ in cases}
    if frozen["corpus"]["photo_source_sha256"] != {
        fixture_id: record["source_digest"]
        for fixture_id, record in expected.items()
        if record["category"] == "phone_camera_photo"
    }:
        raise ValueError("frozen photo source hash mismatch")
    for selected in frozen["selected"].values():
        for run in (selected["ao_run"], selected["photo_run"]):
            for line in (ROOT / "artifacts" / run / "pages.jsonl").read_text().splitlines():
                row = json.loads(line)
                source = expected.get(row["fixture_id"])
                if source is None or any(
                    row[key] != source[key] for key in ("source_digest", "ground_truth_digest")
                ):
                    raise ValueError("development result source mismatch")
    return {"status": "verified", "development_cases": 32, "heldout_executions": 0}


if __name__ == "__main__":
    print(json.dumps(verify(ROOT / "manifests/development-configuration-freeze.v1.json")))
