"""Validate and execute only the two registered genuine development phone photos."""

import argparse
import json
from pathlib import Path

from development import run_prepared
from integrity import digest, read_manifest
from preprocessing.recipes import decode, pixel_digest

ROOT = Path(__file__).resolve().parent
EXPECTED = {f"phone_camera_photo-development-{i:02}" for i in (1, 2)}


def prepare_photos(registry: Path, manifest: Path) -> list[tuple[dict, dict, Path]]:
    payload = json.loads(registry.read_bytes())
    if payload["version"] != "ocr-phone-development-v1":
        raise ValueError("unknown photo registry version")
    records = payload["records"]
    if {r["fixture_id"] for r in records} != EXPECTED or len(records) != 2:
        raise ValueError("expected exactly two development photos")
    known = {case.fixture_id: case for case in read_manifest(manifest).cases}
    prepared = []
    for record in sorted(records, key=lambda r: r["fixture_id"]):
        fixture_id = record["fixture_id"]
        case = known[fixture_id]
        if (
            case.split != "development"
            or record["split"] != "development"
            or case.category != "phone_camera_photo"
            or record["category"] != "phone_camera_photo"
            or case.source_family_id != fixture_id
            or record["source_family_id"] != fixture_id
        ):
            raise ValueError("photo development identity mismatch")
        if (
            case.source_digest != record["source_digest"]
            or case.ground_truth_digest != record["ground_truth_digest"]
        ):
            raise ValueError("photo manifest hash mismatch")
        photo = ROOT / "artifacts/phone_photos/development" / f"{fixture_id}.jpg"
        master = ROOT / "artifacts/development-drafts-v1" / f"{fixture_id}.png"
        truth_path = ROOT / "artifacts/development-drafts-v1" / f"{fixture_id}.truth.json"
        if (
            (ROOT / record["source_path"]).resolve() != photo.resolve()
            or (ROOT / record["master_path"]).resolve() != master.resolve()
            or (ROOT / record["ground_truth_path"]).resolve() != truth_path.resolve()
        ):
            raise ValueError("photo registry path mismatch")
        if (
            record["capture_type"] != "genuine_phone_camera_user_attested"
            or record["mime_type"] != "image/jpeg"
            or record["split"] != "development"
        ):
            raise ValueError("photo provenance mismatch")
        if (
            photo.stat().st_size != record["source_byte_size"]
            or digest(photo.read_bytes()) != record["source_digest"]
            or digest(master.read_bytes()) != record["master_digest"]
        ):
            raise ValueError("photo or master digest mismatch")
        truth_bytes = truth_path.read_bytes()
        if digest(truth_bytes) != record["ground_truth_digest"]:
            raise ValueError("photo truth digest mismatch")
        truth = json.loads(truth_bytes)
        if truth["fixture_id"] != fixture_id or truth["page_number"] != 1:
            raise ValueError("photo truth identity mismatch")
        if truth["transcription"]["words"] != truth["transcription"]["text"].split():
            raise ValueError("photo truth token mismatch")
        image = decode(photo, "image/jpeg")
        try:
            if (
                list(image.size) != record["dimensions"]
                or image.width * image.height != record["decoded_pixel_count"]
                or pixel_digest(image) != record["normalized_pixel_digest"]
                or image.info
            ):
                raise ValueError("photo normalized image mismatch")
        finally:
            image.close()
        prepared.append(
            (
                {
                    "fixture_id": fixture_id,
                    "source_family_id": fixture_id,
                    "split": "development",
                    "category": "phone_camera_photo",
                    "source_digest": record["source_digest"],
                    "ground_truth_digest": record["ground_truth_digest"],
                    "input_pixel_digest": record["normalized_pixel_digest"],
                    "status": "development_photo_validated",
                },
                truth,
                photo,
            )
        )
    return prepared


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry", type=Path, default=ROOT / "manifests/phone-development.v1.json"
    )
    parser.add_argument("--manifest", type=Path, default=ROOT / "manifests/benchmark.v1.json")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    prepared = prepare_photos(args.registry, args.manifest)
    if (args.config is None) != (args.output is None):
        raise ValueError("config and output must be provided together")
    if args.config is None:
        print({"validated_development_photos": len(prepared)})
    else:
        run_prepared(prepared, args.config, args.output)
