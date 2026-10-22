"""Preparation checks use no OCR process or model."""

import json

import pytest

from heldout_preparation import MANIFEST, ROOT, prepare, safe_path, validate
from integrity import canonical


@pytest.fixture
def payload():
    if not MANIFEST.exists() or not (ROOT / "artifacts/heldout-preparation-v1").exists():
        pytest.skip("local held-out preparation artifacts required")
    return json.loads(MANIFEST.read_bytes())


def test_prepared_corpus(payload):
    if (ROOT / "manifests/heldout-execution.v1.json").exists():
        with pytest.raises(ValueError, match="held-out result exists"):
            validate()
    else:
        assert validate()["heldout_executions"] == 0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("split", "development", "identity"),
        ("source_family_id", "clean_digital_scan-development-01", "identity"),
        ("execution_status", "executed", "execution"),
        ("ocr_executions", 1, "execution"),
        ("ground_truth_digest", "0" * 64, "ground truth digest"),
        ("source_digest", "0" * 64, "source digest"),
        ("input_pixel_digest", "0" * 64, "pixel"),
        ("image", "../escape.png", "escapes"),
    ],
)
def test_rejects_invalid_case(payload, tmp_path, field, value, message):
    payload["records"][0][field] = value
    path = tmp_path / "manifest.json"
    path.write_bytes(canonical(payload))
    with pytest.raises(ValueError, match=message):
        validate(manifest_path=path)


@pytest.mark.parametrize("change", ["count", "duplicate", "execution", "provenance", "photo"])
def test_rejects_invalid_preparation(payload, tmp_path, change):
    if change == "count":
        payload["records"].pop()
    elif change == "duplicate":
        payload["records"][1] = payload["records"][0]
    elif change == "execution":
        payload["heldout_executions"] = 1
    elif change == "provenance":
        payload["file_sha256"] = {}
    else:
        payload["records"][-1]["capture_status"] = "captured"
    path = tmp_path / "manifest.json"
    path.write_bytes(canonical(payload))
    with pytest.raises(ValueError):
        validate(manifest_path=path)


def test_refuses_overwrite(tmp_path):
    (tmp_path / "artifacts/heldout-preparation-v1").mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        prepare(tmp_path)


def test_rejects_path_escape(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        safe_path(tmp_path, "../outside")


@pytest.fixture
def phone_registry(tmp_path):
    from PIL import Image

    from integrity import digest

    folder = tmp_path / "artifacts/phone_photos/heldout"
    folder.mkdir(parents=True)
    rows = []
    for i in (1, 2, 3):
        fixture = f"phone_camera_photo-heldout-{i:02}"
        photo = folder / f"{fixture}.jpg"
        Image.new("RGB", (20 + i, 30), (i * 50, 0, 0)).save(photo)
        truth = tmp_path / f"{fixture}.truth.json"
        truth.write_bytes(
            canonical({"fixture_id": fixture, "layout": {"category": "phone_camera_photo"}})
        )
        rows.append(
            dict(
                fixture_id=fixture,
                split="heldout",
                category="phone_camera_photo",
                expected_photo_filename=photo.name,
                expected_photo_path=str(photo.relative_to(tmp_path)),
                capture_status="available",
                capture_type="genuine_phone_camera_user_attested",
                photo_source_digest=digest(photo.read_bytes()),
                photo_byte_count=photo.stat().st_size,
                photo_width=20 + i,
                photo_height=30,
                photo_mime_type="image/jpeg",
                photo_signature="JPEG",
                truth=truth.name,
                ground_truth_digest=digest(truth.read_bytes()),
            )
        )
    return tmp_path, rows


def test_available_phone_registry(phone_registry):
    from heldout_preparation import validate_phone_registry

    root, rows = phone_registry
    assert validate_phone_registry(root, rows, set()) == {
        "phone_photos_pending": 0,
        "phone_photos_registered": 3,
    }


def test_pending_phone_registry(phone_registry):
    from heldout_preparation import validate_phone_registry

    root, rows = phone_registry
    for row in rows:
        (root / row["expected_photo_path"]).unlink()
        for key in list(row):
            if key.startswith("photo_"):
                del row[key]
        row.update(capture_status="pending", photo_source_digest=None)
    assert validate_phone_registry(root, rows, set())["phone_photos_pending"] == 3


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "extra",
        "hash",
        "filename",
        "truth",
        "duplicate_hash",
        "duplicate_id",
        "signature",
        "dimensions",
        "bytes",
        "split",
        "category",
        "pending_present",
        "status",
        "mime",
        "development_reuse",
        "capture_type",
        "format",
    ],
)
def test_phone_registry_rejects_invalid_capture(phone_registry, change):
    from PIL import Image

    from heldout_preparation import validate_phone_registry
    from integrity import digest

    root, rows = phone_registry
    row = rows[0]
    photo = root / row["expected_photo_path"]
    dev_sources = set()
    if change == "missing":
        photo.unlink()
    elif change == "extra":
        (photo.parent / "unregistered.jpg").write_bytes(photo.read_bytes())
    elif change == "hash":
        row["photo_source_digest"] = "0" * 64
    elif change == "filename":
        row["expected_photo_filename"] = rows[1]["expected_photo_filename"]
    elif change == "truth":
        row["ground_truth_digest"] = "0" * 64
    elif change == "duplicate_hash":
        (root / rows[1]["expected_photo_path"]).write_bytes(photo.read_bytes())
        for key in ("photo_source_digest", "photo_byte_count", "photo_width", "photo_height"):
            rows[1][key] = row[key]
    elif change == "duplicate_id":
        rows[1] = row.copy()
    elif change in {"signature", "format"}:
        if change == "format":
            Image.new("RGB", (21, 30)).save(photo, format="PNG")
        else:
            photo.write_bytes(b"invalid jpeg")
        row["photo_source_digest"] = digest(photo.read_bytes())
        row["photo_byte_count"] = photo.stat().st_size
    elif change == "dimensions":
        row["photo_width"] += 1
    elif change == "bytes":
        row["photo_byte_count"] += 1
    elif change == "split":
        row["split"] = "development"
    elif change == "category":
        row["category"] = "tables"
    elif change == "pending_present":
        row.update(capture_status="pending", photo_source_digest=None)
    elif change == "status":
        row["capture_status"] = "captured"
    elif change == "mime":
        row["photo_mime_type"] = "image/png"
    elif change == "development_reuse":
        dev_sources.add(row["photo_source_digest"])
    elif change == "capture_type":
        row["capture_type"] = "synthetic"
    with pytest.raises(ValueError):
        validate_phone_registry(root, rows, dev_sources)
