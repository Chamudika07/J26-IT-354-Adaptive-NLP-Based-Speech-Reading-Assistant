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
