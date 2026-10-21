import json
from collections import Counter
from pathlib import Path

import pytest
from PIL import Image

import photo_development
from development import prepare_cases, score_page
from generators.render_development import generate
from generators.render_phone_masters import generate as generate_phone_masters
from integrity import digest
from photos import expected_photos, require_phone_photos
from preprocessing.recipes import decode, pixel_digest
from schemas import CATEGORIES, OCRResult, Unit

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def drafts(tmp_path_factory):
    output = tmp_path_factory.mktemp("development") / "drafts"
    generate(output, ROOT / "manifests/benchmark.v1.json")
    return output


@pytest.mark.parametrize("category", CATEGORIES[:-1])
def test_each_category(drafts, category):
    index = json.loads((drafts / "index.json").read_bytes())
    records = [r for r in index["records"] if r["category"] == category]
    assert len(records) == 2
    for row in records:
        assert row["split"] == "development"
        gt = json.loads((drafts / (row["fixture_id"] + ".truth.json")).read_bytes())
        ids = [b["id"] for b in gt["layout"]["blocks"]]
        assert len(ids) == len(set(ids))
        assert gt["transcription"]["words"] == gt["transcription"]["text"].split()
        assert all(a in ids and b in ids for a, b in gt["layout"]["precedence"])
        if category == "tables":
            assert len(gt["layout"]["cells"]) == 9
            assert all(len(c["polygon"]) == 4 for c in gt["layout"]["cells"])
            assert Counter(c["row"] for c in gt["layout"]["cells"]) == {0: 3, 1: 3, 2: 3}
        if category == "two_column":
            roles = {b["role"] for b in gt["layout"]["blocks"]}
            assert {
                "left_column",
                "right_column",
                "caption",
                "footnote",
                "spanning_heading",
            } <= roles
        if category == "mixed_fonts_sizes":
            assert len({b["font"] for b in gt["layout"]["blocks"]}) == 2


def test_phone_deferred(drafts, tmp_path):
    assert not list(drafts.glob("phone_camera_photo*"))
    paths = expected_photos(tmp_path)
    assert len(paths) == 5
    assert sum(p.parent.name == "development" for p in paths) == 2
    with pytest.raises(ValueError, match="photographs missing"):
        require_phone_photos(tmp_path)


def test_phone_print_masters_are_authored_sources_not_photographs(tmp_path):
    output = tmp_path / "print_masters"
    index = generate_phone_masters(output)
    assert len(index["records"]) == 2
    for record in index["records"]:
        assert record["split"] == "development"
        assert record["source_family_id"] == record["fixture_id"]
        assert 80 <= record["word_count"] <= 120
        assert digest((output / record["image"]).read_bytes()) == record["source_digest"]
        truth_bytes = (output / record["truth"]).read_bytes()
        assert digest(truth_bytes) == record["ground_truth_digest"]
        truth = json.loads(truth_bytes)
        assert truth["layout"]["category"] == "phone_camera_photo"
        assert truth["layout"]["cells"] == []
        assert all(block["role"] != "left_column" for block in truth["layout"]["blocks"])
        assert len(truth["layout"]["blocks"]) == 4
        assert truth["transcription"]["words"] == truth["transcription"]["text"].split()
    assert not list(output.glob("*.jpg"))


def test_photo_registration_checks_hashes_and_jpeg_scoring(tmp_path, monkeypatch):
    monkeypatch.setattr(photo_development, "ROOT", tmp_path)
    benchmark = json.loads((ROOT / "manifests/benchmark.v1.json").read_text())
    rows = []
    for number in (1, 2):
        fid = f"phone_camera_photo-development-{number:02}"
        photo = tmp_path / "artifacts/phone_photos/development" / f"{fid}.jpg"
        master = tmp_path / "artifacts/development-drafts-v1" / f"{fid}.png"
        truth_path = master.with_suffix(".truth.json")
        photo.parent.mkdir(parents=True, exist_ok=True)
        master.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (100, 120), "white")
        image.save(photo)
        image.save(master)
        truth = {
            "fixture_id": fid,
            "page_number": 1,
            "transcription": {"text": "Test page", "words": ["Test", "page"]},
        }
        truth_path.write_text(json.dumps(truth))
        normalized = decode(photo, "image/jpeg")
        row = {
            "fixture_id": fid,
            "source_family_id": fid,
            "split": "development",
            "category": "phone_camera_photo",
            "capture_type": "genuine_phone_camera_user_attested",
            "source_path": str(photo),
            "source_digest": digest(photo.read_bytes()),
            "source_byte_size": photo.stat().st_size,
            "mime_type": "image/jpeg",
            "dimensions": list(normalized.size),
            "decoded_pixel_count": normalized.width * normalized.height,
            "normalized_pixel_digest": pixel_digest(normalized),
            "master_path": str(master),
            "master_digest": digest(master.read_bytes()),
            "ground_truth_path": str(truth_path),
            "ground_truth_digest": digest(truth_path.read_bytes()),
        }
        rows.append(row)
        case = next(x for x in benchmark["cases"] if x["fixture_id"] == fid)
        case["source_digest"] = row["source_digest"]
        case["ground_truth_digest"] = row["ground_truth_digest"]
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"version": "ocr-phone-development-v1", "records": rows}))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(benchmark))
    prepared = photo_development.prepare_photos(registry, manifest)
    assert len(prepared) == 2
    record, truth, path = prepared[0]
    config = {
        "experiment_id": "UNIT-TEST-PHOTO",
        "engine": "paddle",
        "engine_version": "3.2.0",
        "runtime_version": "3.2.0",
        "model_name": "unit-test",
        "model_version": "unit-test",
        "model_digest": digest(b"unit-test"),
    }

    def stub(_image):
        return OCRResult(
            engine="paddle",
            engine_version="3.2.0",
            confidence_scale="test-only",
            units=[Unit(text=truth["transcription"]["text"], block="b", line="l", confidence=None)],
            native_output="unit test stub",
        )

    scored = score_page(record, truth, path, config, stub, tmp_path)
    assert scored.input_kind == "JPEG" and scored.exact_match
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest mismatch"):
        photo_development.prepare_photos(registry, manifest)


def test_prepare_all_categories(drafts):
    prepared = prepare_cases(drafts / "index.json", ROOT / "manifests/benchmark.v1.json")
    assert len(prepared) == 30
    ids = [r[0]["fixture_id"] for r in prepared]
    assert ids == sorted(ids)


def test_no_holdout_or_tampered_inputs(drafts, tmp_path):
    index = json.loads((drafts / "index.json").read_bytes())
    index["records"][0]["split"] = "heldout"
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index))
    with pytest.raises(ValueError, match="development-only"):
        prepare_cases(path, ROOT / "manifests/benchmark.v1.json")
    index["records"][0]["split"] = "development"
    index["records"][0]["fixture_id"] = "phone_camera_photo-development-01"
    path.write_text(json.dumps(index))
    with pytest.raises(ValueError, match="phone photographs deferred"):
        prepare_cases(path, ROOT / "manifests/benchmark.v1.json")


def test_development_scoring_with_unit_stub(drafts, tmp_path):
    # Unit stub only: never represented as a measured engine result.
    record, truth, path = prepare_cases(
        drafts / "index.json", ROOT / "manifests/benchmark.v1.json"
    )[0]
    config = dict(
        experiment_id="UNIT-TEST-NOT-BENCHMARK",
        engine="tesseract",
        engine_version="5.test",
        runtime_version="test-stub",
        model_name="test-stub",
        model_version="test",
        model_digest=digest(b"unit-test-only"),
    )

    def stub(image):
        return OCRResult(
            engine="tesseract",
            engine_version="5.test",
            confidence_scale="test-only",
            units=[Unit(text=truth["transcription"]["text"], block="b", line="l", confidence=None)],
            native_output="unit test stub",
        )

    row = score_page(record, truth, path, config, stub, tmp_path)
    assert row.cer == row.wer == 0
    assert row.exact_match
    assert (tmp_path / (record["fixture_id"] + ".native.txt")).read_text() == "unit test stub"
    assert row.confidence_scale == "test-only"

    def broken(image):
        raise ValueError("do not log content")

    failures = tmp_path / "failures"
    failures.mkdir()
    row = score_page(record, truth, path, config, broken, failures)
    assert row.outcome == "failed"
    assert row.failure_stage == "engine"
    assert row.cer is None
    assert "do not log content" not in row.model_dump_json()
    assert not list(failures.iterdir())


def test_holdout_claim_requires_photos_even_if_manifest_marked_verified(tmp_path):
    from evaluate import claim_holdout
    from integrity import freeze, read_manifest

    manifest = read_manifest(ROOT / "manifests/benchmark.v1.json")
    for case in manifest.cases:
        case.status = "verified"
        case.source_digest = digest(b"test source")
        case.ground_truth_digest = digest(b"test truth")
    (tmp_path / "contract").write_text("test freeze")
    frozen = tmp_path / "freeze.json"
    freeze(
        tmp_path,
        ["contract"],
        dict(development_selection_complete=True, artifacts_verified=True, linux_gates_passed=True),
        frozen,
    )
    with pytest.raises(ValueError, match="photographs missing"):
        claim_holdout(tmp_path, manifest, frozen)
    assert not (tmp_path / "artifacts/heldout-primary-v1.claim").exists()


def test_source_tampering_is_rejected(drafts, tmp_path):
    index = json.loads((drafts / "index.json").read_bytes())
    index["records"] = index["records"][:1]
    record = index["records"][0]
    (tmp_path / "index.json").write_text(json.dumps(index))
    (tmp_path / (record["fixture_id"] + ".png")).write_bytes(b"changed source")
    with pytest.raises(ValueError, match="source digest mismatch"):
        prepare_cases(tmp_path / "index.json", ROOT / "manifests/benchmark.v1.json")


def test_accented_authoring_font_has_required_glyphs():
    import reportlab
    from PIL import ImageFont

    font = ImageFont.truetype(str(Path(reportlab.__file__).parent / "fonts/Vera.ttf"), 26)
    missing = bytes(font.getmask("\uffff"))
    assert all(bytes(font.getmask(c)) != missing for c in "éèëû")


def test_tesseract_tsv_does_not_require_system_config(tmp_path, monkeypatch):
    from engines import tesseract
    from schemas import Artifact

    data = b"unit test model"
    (tmp_path / "eng.traineddata").write_bytes(data)
    artifact = Artifact(
        identifier="test",
        path="eng.traineddata",
        engine="tesseract",
        engine_version="5.5.3",
        runtime_version="5.5.3",
        model_name="test",
        revision="test",
        source="unit test",
        licence="test",
        byte_size=len(data),
        sha256=digest(data),
        language="en",
        role="recognition",
    )
    commands = []

    def stub(command, *args, **kwargs):
        commands.append(command)
        if "--version" in command:
            return b"tesseract 5.5.3\n"
        return (
            b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
            b"left\ttop\twidth\theight\tconf\ttext\n"
        )

    monkeypatch.setattr(tesseract, "run_child", stub)
    tesseract.recognize(tmp_path / "input.png", Path("/unit-test"), tmp_path, artifact, "5.5.3")
    assert commands[-1][-2:] == ["-c", "tessedit_create_tsv=1"]


def test_region_matching_uses_geometry_only():
    from analyze_development import match_region

    blocks = [
        dict(id="left", text="identical", polygon=[[10, 10], [40, 10], [40, 20], [10, 20]]),
        dict(id="right", text="identical", polygon=[[100, 10], [140, 10], [140, 20], [100, 20]]),
    ]
    assert match_region([[101, 11], [130, 11], [130, 19], [101, 19]], blocks) == "right"
    assert match_region([[500, 500], [510, 500], [510, 510], [500, 510]], blocks) is None
    assert match_region(None, blocks) is None


@pytest.mark.parametrize("dpi", [100, 150, 200, 300])
def test_rasterizer_supported_dpis(tmp_path, dpi):
    import math

    from PIL import Image

    from rasterizers.pdfium import render

    source = tmp_path / "synthetic.pdf"
    Image.new("RGB", (72, 72), "white").save(source, "PDF", resolution=72)
    image, meta = next(render(source, dpi))
    assert image.size == (math.ceil(dpi), math.ceil(dpi))
    assert meta["dpi"] == dpi
    assert meta["page_size_points"] == [72.0, 72.0]


def test_provision_verifies_download_before_publishing(tmp_path, monkeypatch):
    import io
    import urllib.request

    from provision import provision

    payload = dict(
        version="ocr-artifacts-v1",
        artifacts=[
            dict(
                identifier="test",
                path="eng.traineddata",
                engine="tesseract",
                engine_version="5.5.3",
                runtime_version="5.5.3",
                model_name="test",
                revision="test",
                source="https://example.invalid/model",
                licence="test",
                byte_size=5,
                sha256=digest(b"model"),
                language="en",
                role="recognition",
            )
        ],
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload))
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"wrong"))
    root = tmp_path / "models"
    with pytest.raises(ValueError, match="digest"):
        provision(manifest, root)
    assert not (root / "eng.traineddata").exists()
    assert not list(root.iterdir())
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"model"))
    assert provision(manifest, root) == 1
    assert (root / "eng.traineddata").read_bytes() == b"model"


def test_performance_uses_two_warmups_and_ten_fresh_processes(tmp_path, monkeypatch):
    import subprocess
    from types import SimpleNamespace

    from performance import measure

    config = tmp_path / "config.json"
    config.write_text("{}")
    image = tmp_path / "development.png"
    image.write_bytes(b"unit test only")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            stdout=json.dumps(
                dict(
                    engine_ms=1,
                    child_peak_rss_bytes=12,
                    memory_method="unit test stub",
                    native_sha256=digest(b"test"),
                    units=1,
                )
            ).encode()
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = measure(config, image, tmp_path / "output")
    assert len(calls) == 12
    assert result["warmups"] == 2 and result["measured"] == 10
    assert result["p95"] is None
