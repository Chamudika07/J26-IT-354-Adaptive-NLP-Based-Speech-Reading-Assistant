"""Preparation and fail-closed validation only. No OCR adapters are imported or invoked."""

import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image

from generators.render_heldout import generate as generate_ao
from generators.render_heldout_phone_masters import generate as generate_phone
from integrity import canonical, digest, read_manifest
from preprocessing.recipes import pixel_digest
from schemas import CATEGORIES

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifests/heldout-preparation.v1.json"
VERSION = "ocr-heldout-preparation-v1"
GENERATOR_FILES = (
    "heldout_preparation.py",
    "generators/render_heldout.py",
    "generators/render_heldout_phone_masters.py",
    "generators/degradations.py",
    "preprocessing/recipes.py",
    "uv.lock",
)


def prepare(root: Path = ROOT) -> dict:
    """Create new artifacts exclusively; refuse to overwrite an existing preparation."""
    destination = root / "manifests/heldout-preparation.v1.json"
    output = root / "artifacts/heldout-preparation-v1"
    if destination.exists() or output.exists():
        raise ValueError("held-out preparation already exists")
    benchmark = root / "manifests/benchmark.v1.json"
    ao = generate_ao(output / "ao", benchmark)
    phone = generate_phone(output / "phone-print-masters")
    records = []
    for group, index in (("ao", ao), ("phone-print-masters", phone)):
        for source in index["records"]:
            row = dict(source)
            fixture = row["fixture_id"]
            row.update(
                category=fixture.rsplit("-heldout-", 1)[0],
                preparation_status="prepared",
                execution_status="not_executed",
                ocr_executions=0,
                generator_version=index["version"],
                image=f"artifacts/heldout-preparation-v1/{group}/{fixture}.png",
                truth=f"artifacts/heldout-preparation-v1/{group}/{fixture}.truth.json",
            )
            if group == "phone-print-masters":
                row.update(
                    capture_status="pending",
                    expected_photo_filename=f"{fixture}.jpg",
                    expected_photo_path=f"artifacts/phone_photos/heldout/{fixture}.jpg",
                    photo_source_digest=None,
                )
            records.append(row)
    result = dict(
        version=VERSION,
        status="prepared_not_executed",
        heldout_executions=0,
        records=records,
        configuration={
            "ao_canvas": [1600, 2000],
            "phone_canvas": [1600, 2263],
            "phone_print": "Fit to A4 portrait; original raster master, not a photograph",
            "degradation_seed": 22081766,
            "random_authoring": False,
            "rendering_semantics": "development-v3; independent held-out text",
        },
        file_sha256={name: digest((root / name).read_bytes()) for name in GENERATOR_FILES},
    )
    destination.write_bytes(canonical(result))
    return result


def safe_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("path escapes research root")
    return path


def validate_phone_registry(root: Path, rows: list[dict], dev_sources: set) -> dict:
    """Validate capture lifecycle without changing or recognizing image contents."""
    expected_ids = {f"phone_camera_photo-heldout-{i:02}" for i in (1, 2, 3)}
    if len(rows) != 3 or {r["fixture_id"] for r in rows} != expected_ids:
        raise ValueError("phone fixture identity/count mismatch")
    registered, hashes = set(), set()
    pending = 0
    for row in rows:
        fixture = row["fixture_id"]
        filename = f"{fixture}.jpg"
        relative = f"artifacts/phone_photos/heldout/{filename}"
        if (
            row["category"] != "phone_camera_photo"
            or row["split"] != "heldout"
            or row["expected_photo_filename"] != filename
            or row["expected_photo_path"] != relative
        ):
            raise ValueError("phone filename/category/split mismatch")
        path = safe_path(root, relative)
        truth_bytes = safe_path(root, row["truth"]).read_bytes()
        truth = json.loads(truth_bytes)
        if (
            digest(truth_bytes) != row["ground_truth_digest"]
            or truth["fixture_id"] != fixture
            or truth["layout"]["category"] != "phone_camera_photo"
        ):
            raise ValueError("phone ground truth mismatch")
        if row["capture_status"] == "pending":
            if path.exists() or row["photo_source_digest"] is not None:
                raise ValueError("invalid pending phone master")
            if any(key.startswith("photo_") and value is not None for key, value in row.items()):
                raise ValueError("pending photo has capture metadata")
            pending += 1
            continue
        if row["capture_status"] != "available" or not path.is_file():
            raise ValueError("available phone photo missing or invalid capture status")
        data = path.read_bytes()
        sha = digest(data)
        if sha != row["photo_source_digest"] or sha in hashes | dev_sources:
            raise ValueError("phone hash mismatch, duplicate, or development reuse")
        if (
            row["capture_type"] != "genuine_phone_camera_user_attested"
            or row["photo_mime_type"] != "image/jpeg"
            or row["photo_signature"] != "JPEG"
            or row["photo_byte_count"] != len(data)
            or not data.startswith(b"\xff\xd8\xff")
        ):
            raise ValueError("phone capture metadata/signature mismatch")
        with Image.open(path) as image:
            if image.format != "JPEG" or image.size != (row["photo_width"], row["photo_height"]):
                raise ValueError("phone format/dimensions mismatch")
            image.verify()
        with Image.open(path) as image:
            image.load()  # Verify the complete raster can decode, not just the header.
        hashes.add(sha)
        registered.add(filename)
    folder = root / "artifacts/phone_photos/heldout"
    actual = {p.name for p in folder.iterdir()} if folder.exists() else set()
    if actual != registered:
        raise ValueError("unregistered extra phone artifact")
    return {"phone_photos_pending": pending, "phone_photos_registered": len(registered)}


def validate(root: Path = ROOT, manifest_path: Path | None = None) -> dict:
    payload = json.loads(
        (manifest_path or root / "manifests/heldout-preparation.v1.json").read_bytes()
    )
    if (
        payload["version"] != VERSION
        or payload["status"] != "prepared_not_executed"
        or payload["heldout_executions"] != 0
    ):
        raise ValueError("invalid preparation state")
    if set(payload["file_sha256"]) != set(GENERATOR_FILES):
        raise ValueError("missing generator provenance")
    for name, expected in payload["file_sha256"].items():
        if digest(safe_path(root, name).read_bytes()) != expected:
            raise ValueError("generator provenance mismatch")
    benchmark = read_manifest(root / "manifests/benchmark.v1.json")
    heldout = {c.fixture_id: c for c in benchmark.cases if c.split == "heldout"}
    development = [c for c in benchmark.cases if c.split == "development"]
    rows = payload["records"]
    if len(rows) != 48 or {r["fixture_id"] for r in rows} != set(heldout):
        raise ValueError("held-out identity/count mismatch")
    if Counter(r["category"] for r in rows) != Counter(dict.fromkeys(CATEGORIES, 3)):
        raise ValueError("category count mismatch")
    families, hashes, texts, sources, pixels = (set() for _ in range(5))
    dev_hashes = {c.ground_truth_digest for c in development}
    dev_sources = {c.source_digest for c in development}
    dev_families = {c.source_family_id for c in development}
    # Include original development print masters as well as captured-photo ground truth.
    dev_texts, dev_blocks, dev_pixels = set(), set(), set()
    for directory in (
        "development-drafts-v1",
        "development-drafts-v3",
        "phone_print_masters/development-v2",
    ):
        folder = root / "artifacts" / directory
        if not folder.exists():
            raise ValueError("development sources required for independence validation")
        truth_paths = list(folder.glob("*.truth.json"))
        if len(truth_paths) < (2 if "phone_print" in directory else 30):
            raise ValueError("incomplete development sources")
        for path in truth_paths:
            truth = json.loads(path.read_bytes())
            dev_hashes.add(digest(path.read_bytes()))
            dev_texts.add(" ".join(truth["transcription"]["text"].split()))
            dev_blocks.update(
                b["text"] for b in truth["layout"]["blocks"] if len(b["text"].split()) > 3
            )
        for path in folder.glob("*.png"):
            dev_sources.add(digest(path.read_bytes()))
            with Image.open(path) as image:
                dev_pixels.add(pixel_digest(image.convert("RGB")))
    for row in rows:
        fixture = heldout[row["fixture_id"]]
        if (
            row["split"] != "heldout"
            or row["category"] != fixture.category
            or row["source_family_id"] != fixture.source_family_id
            or row["source_family_id"] in families | dev_families
            or row["preparation_status"] != "prepared"
            or row["execution_status"] != "not_executed"
            or row["ocr_executions"] != 0
        ):
            raise ValueError("identity, family, or execution mismatch")
        families.add(row["source_family_id"])
        truth_bytes = safe_path(root, row["truth"]).read_bytes()
        truth = json.loads(truth_bytes)
        gh = digest(truth_bytes)
        text = " ".join(truth["transcription"]["text"].split())
        if gh != row["ground_truth_digest"] or gh in hashes | dev_hashes:
            raise ValueError("ground truth digest mismatch or duplicate")
        if text in texts | dev_texts:
            raise ValueError("duplicate transcription")
        hashes.add(gh)
        texts.add(text)
        if (
            truth["version"] != "ocr-ground-truth-v1"
            or truth["fixture_id"] != fixture.fixture_id
            or truth["page_number"] != 1
            or truth["layout"]["category"] != fixture.category
            or truth["transcription"]["words"] != truth["transcription"]["text"].split()
        ):
            raise ValueError("invalid ground truth")
        blocks = truth["layout"]["blocks"]
        if (
            not blocks
            or len({b["id"] for b in blocks}) != len(blocks)
            or truth["transcription"]["text"] != "\n\n".join(b["text"] for b in blocks)
            or truth["transcription"]["lines"] != [line for b in blocks for line in b["lines"]]
            or truth["layout"]["precedence"]
            != [[a["id"], b["id"]] for a, b in zip(blocks, blocks[1:], strict=False)]
        ):
            raise ValueError("invalid layout/transcription alignment")
        if any(b["text"] in dev_blocks for b in blocks):
            raise ValueError("copied development block")
        image_path = safe_path(root, row["image"])
        sh = digest(image_path.read_bytes())
        if sh != row["source_digest"] or sh in sources | dev_sources:
            raise ValueError("source digest mismatch or reuse")
        sources.add(sh)
        with Image.open(image_path) as image:
            pd = pixel_digest(image.convert("RGB"))
            if pd in pixels | dev_pixels or pd != row.get("input_pixel_digest", pd):
                raise ValueError("pixel reuse or mismatch")
            pixels.add(pd)
            for block in blocks + truth["layout"]["cells"]:
                if len(block["polygon"]) != 4 or any(
                    not (0 <= x <= image.width and 0 <= y <= image.height)
                    for x, y in block["polygon"]
                ):
                    raise ValueError("invalid ground truth geometry")
        if fixture.category == "tables" and len(truth["layout"]["cells"]) != 9:
            raise ValueError("invalid table cells")
        if fixture.category == "phone_camera_photo":
            if not 80 <= len(truth["transcription"]["words"]) <= 120:
                raise ValueError("invalid phone master word count")
    phone_counts = validate_phone_registry(
        root, [r for r in rows if r["category"] == "phone_camera_photo"], dev_sources | sources
    )
    # Audit persisted result evidence, rather than relying only on a declared counter.
    for folder in (root / "artifacts", root / "results"):
        for path in folder.rglob("*.jsonl"):
            for line in path.read_text().splitlines():
                result = json.loads(line)
                if result.get("split") == "heldout" or result.get("fixture_id") in heldout:
                    raise ValueError("held-out result exists")
    return dict(
        status="pass",
        ao_cases=45,
        phone_masters=3,
        **phone_counts,
        total_slots=48,
        heldout_executions=0,
        independence="pass",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument(
        "--pre-run", action="store_true", help="Require all three registered photos"
    )
    args = parser.parse_args()
    if args.prepare:
        prepare()
    report = validate()
    if args.pre_run:
        from verify_development_freeze import verify

        if report["phone_photos_registered"] != 3 or report["phone_photos_pending"] != 0:
            raise ValueError("pre-run requires three registered photos")
        report["development_freeze"] = verify(
            ROOT / "manifests/development-configuration-freeze.v1.json"
        )["status"]
    print(json.dumps(report))
