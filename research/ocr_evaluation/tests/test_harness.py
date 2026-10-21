import json
import sys
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from engines.base import assemble, run_child
from engines.paddle import normalize, verify_bundle
from engines.tesseract import parse_tsv
from evaluate import claim_holdout, require_development, validate_artifacts, write_jsonl
from generators.degradations import LEVELS, points, transform
from integrity import canonical, digest, freeze, read_manifest, verify_artifact, verify_freeze
from layout import precedence, regions, table_associations
from preprocessing.recipes import apply, decode, pixel_digest
from report import performance
from routing import eligibility
from schemas import Artifact, Manifest, PageResult

ROOT = Path(__file__).resolve().parents[1]


def manifest_data():
    return json.loads((ROOT / "manifests/benchmark.v1.json").read_bytes())


def artifact(data=b"model"):
    return Artifact(
        identifier="eng",
        path="eng.traineddata",
        engine="tesseract",
        engine_version="5.5.0",
        runtime_version="5.5.0",
        model_name="eng",
        revision="immutable-upstream-revision",
        source="https://example.org/model",
        licence="Apache-2.0",
        byte_size=len(data),
        sha256=digest(data),
        language="en",
        role="recognition",
    )


def test_manifest_counts():
    m = read_manifest(ROOT / "manifests/benchmark.v1.json")
    assert len(m.cases) == 80
    assert sum(c.split == "development" for c in m.cases) == 32


@pytest.mark.parametrize("mutation", ["duplicate", "leak", "hash", "provenance", "parent", "count"])
def test_manifest_rejections(mutation):
    data = manifest_data()
    a, b = data["cases"][:2]
    if mutation == "duplicate":
        b["fixture_id"] = a["fixture_id"]
    elif mutation == "leak":
        data["cases"][2]["source_family_id"] = a["source_family_id"]
    elif mutation == "hash":
        a["source_digest"] = "bad"
    elif mutation == "provenance":
        a["provenance"] = ""
    elif mutation == "parent":
        b["parent_id"] = "absent"
    else:
        data["cases"].pop()
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_model_integrity(tmp_path):
    a = artifact()
    with pytest.raises(ValueError, match="missing_model"):
        verify_artifact(tmp_path, a)
    (tmp_path / a.path).write_bytes(b"wrong")
    with pytest.raises(ValueError, match="digest"):
        verify_artifact(tmp_path, a)
    (tmp_path / a.path).write_bytes(b"model")
    assert verify_artifact(tmp_path, a).is_file()
    with pytest.raises(ValueError, match="escapes"):
        verify_artifact(tmp_path, a.model_copy(update={"path": "../outside"}))
    with pytest.raises(ValueError):
        verify_bundle(tmp_path, [])
    empty = tmp_path / "empty-artifacts.json"
    empty.write_text('{"version":"ocr-artifacts-v1","artifacts":[]}')
    with pytest.raises(ValueError, match="unprovisioned"):
        validate_artifacts(empty, tmp_path)


def test_freeze_and_claim(tmp_path):
    (tmp_path / "contract").write_text("v1")
    metadata = dict(
        development_selection_complete=True, artifacts_verified=True, linux_gates_passed=True
    )
    frozen = tmp_path / "freeze.json"
    with pytest.raises(ValueError):
        freeze(tmp_path, ["contract"], {}, frozen)
    freeze(tmp_path, ["contract"], metadata, frozen)
    with pytest.raises(FileExistsError):
        freeze(tmp_path, ["contract"], metadata, frozen)
    manifest = read_manifest(ROOT / "manifests/benchmark.v1.json")
    with pytest.raises(ValueError, match="verified"):
        claim_holdout(tmp_path, manifest, frozen)
    (tmp_path / "contract").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        verify_freeze(tmp_path, frozen)
    with pytest.raises(ValueError):
        require_development("heldout")


@pytest.mark.parametrize("kind,level", [(k, v) for k, levels in LEVELS.items() for v in levels])
def test_degradation_determinism(kind, level):
    image = Image.new("RGB", (60, 80), "white")
    image.putpixel((20, 30), (40, 70, 90))
    first, a = transform(image, kind, level, 73)
    second, b = transform(image, kind, level, 73)
    assert first.tobytes() == second.tobytes()
    assert a == b
    assert a["parameters"] == {kind: level}
    assert a["seed"] == 73
    assert a["parent_pixel_sha256"] == pixel_digest(image)
    assert a["output_pixel_sha256"] == pixel_digest(first)


def test_geometry():
    assert points([(1, 2)], [[2, 0, 3], [0, 4, 5], [0, 0, 1]]) == [[5, 13]]
    image = Image.new("RGB", (60, 80), "white")
    _, record = transform(image, "resolution", 150)
    assert points([(60, 80)], record["forward_matrix"]) == [[30, 40]]
    _, record = transform(image, "orientation", 180)
    assert points([(0, 0)], record["forward_matrix"])[0] == pytest.approx([60, 80])


@pytest.mark.parametrize(
    "recipe,params",
    [
        ("baseline", {}),
        ("grayscale", {}),
        ("contrast", {"factor": 0.7}),
        ("resize", {"scale": 0.5}),
        ("deskew", {"angle": 2}),
        ("adaptive_threshold", {"window": 3, "offset": 5}),
    ],
)
def test_preprocessing(recipe, params):
    image = Image.new("RGB", (20, 30), "white")
    a, record = apply(image, recipe, **params)
    b, other = apply(image, recipe, **params)
    assert a.tobytes() == b.tobytes()
    assert record == other
    assert record["version"] == "ocr-preprocessing-v1"
    with pytest.raises(ValueError):
        apply(image, "baseline", extra=1)


def test_images(tmp_path):
    path = tmp_path / "test.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
    image = decode(path, "image/png")
    assert image.getpixel((0, 0)) == (255, 255, 255)
    assert not image.info
    with pytest.raises(ValueError, match="mime_magic"):
        decode(path, "image/jpeg")
    path.write_bytes(b"\x89PNG\r\n\x1a\ninvalid")
    with pytest.raises(ValueError, match="malformed"):
        decode(path, "image/png")
    # Narrow harmless image tests dimension policy without a decompression bomb.
    Image.new("RGB", (6001, 1)).save(path)
    with pytest.raises(ValueError, match="resource"):
        decode(path, "image/png")


def test_native_adapters():
    raw = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t97.5\tHello\n"
        "5\t1\t1\t1\t2\t1\t0\t10\t10\t10\t-1\tworld\n"
    )
    result = parse_tsv(raw, "5.5.0")
    assert result.units[0].confidence == 97.5
    assert result.units[1].confidence is None
    assert assemble(result) == "Hello\nworld"
    assert result.native_output == raw
    p = normalize(
        {"rec_texts": ["Hi"], "rec_scores": [0.9], "rec_polys": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}
    )
    assert p.units[0].confidence == 0.9
    with pytest.raises(ValueError, match="malformed"):
        normalize({"rec_texts": ["Hi"], "rec_scores": [], "rec_polys": []})
    with pytest.raises(ValueError, match="malformed"):
        parse_tsv("invalid", "5.5.0")


def test_child_failures():
    with pytest.raises(ValueError, match="missing_engine"):
        run_child(["/no/such/ocr-engine"])
    with pytest.raises(ValueError, match="timeout"):
        run_child([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.05)
    with pytest.raises(ValueError, match="abnormal_engine_exit"):
        run_child([sys.executable, "-c", "raise SystemExit(2)"])
    assert run_child([sys.executable, "-c", 'print("ok")']) == b"ok\n"


def test_layout_routing_performance():
    assert precedence(["a", "b"], [("a", "b"), ("b", "c")]) == 0.5
    assert precedence(["a"], []) is None
    assert precedence(["a", "a", "b"], [("a", "b")]) == 0
    assert regions(["a", "b"], ["a", "a"])["duplicate"] == 1
    assert table_associations(
        {"c": dict(row=0, column=0, text="A")}, {"c": dict(row=1, column=0, text="B")}
    ) == dict(missing=0, transcription=1, row=1, column=0)
    assert eligibility("failed", "encrypted_pdf", []) == "ineligible_failure"
    assert eligibility("ocr_required", "image_without_text", []) == "eligible"
    assert eligibility("needs_review", None, ["inspection_uncertain"]) == "manual_review_only"
    assert performance(list(range(1, 101)))["p95"] == 95
    assert performance([1, 2])["p95"] is None


def test_result_jsonl(tmp_path):
    row = PageResult(
        experiment_id="test",
        fixture_id="a",
        source_family_id="a",
        category="tables",
        feature_tags=[],
        split="development",
        page_number=1,
        source_digest=digest(b"a"),
        ground_truth_digest=digest(b"b"),
        engine="tesseract",
        configuration_fingerprint=digest(b"c"),
        outcome="failed",
        failure_stage="engine",
        failure_code="missing_model",
        character_substitutions=None,
        character_deletions=None,
        character_insertions=None,
        reference_character_count=None,
        cer=None,
        word_substitutions=None,
        word_deletions=None,
        word_insertions=None,
        reference_word_count=None,
        wer=None,
        exact_match=None,
        metric_status="unavailable_engine_failure",
        evidence={},
        unavailable_reasons={"peak_memory_bytes": "not instrumented"},
        peak_memory_bytes=None,
        memory_method="unavailable",
        notes=[],
    )
    out = tmp_path / "results.jsonl"
    write_jsonl(out, [row])
    assert PageResult.model_validate_json(out.read_bytes()) == row
    with pytest.raises(FileExistsError):
        write_jsonl(out, [row])
    data = row.model_dump()
    data["unavailable_reasons"] = {}
    with pytest.raises(ValidationError):
        PageResult.model_validate(data)
    assert canonical({"b": 1, "a": 2}) == canonical({"a": 2, "b": 1})


def test_pdfium_synthetic(tmp_path):
    from rasterizers.pdfium import render

    source = tmp_path / "safe.pdf"
    Image.new("RGB", (40, 40), "white").save(source, "PDF", resolution=72)
    first = list(render(source, 150))
    second = list(render(source, 150))
    assert len(first) == 1
    assert first[0][0].size == (84, 84)
    assert first[0][1] == second[0][1]
    source.write_bytes(b"%PDF-invalid")
    with pytest.raises(__import__("pypdfium2").PdfiumError):
        list(render(source))


def test_draft_corpus_is_not_verified(tmp_path):
    from generators.render_development import generate

    result = generate(tmp_path / "drafts", ROOT / "manifests/benchmark.v1.json")
    assert result["synthetic_drafts"] == 30
    assert result["phone_print_masters"] == 0
    assert result["verified_cases"] == 0
    assert len({r["source_digest"] for r in result["records"]}) == 30
    assert all(r["split"] == "development" for r in result["records"])
    with pytest.raises(FileExistsError):
        generate(tmp_path / "drafts", ROOT / "manifests/benchmark.v1.json")


def test_confidence_no_pooling():
    from confidence import pearson, summarize

    rows = [
        dict(engine="tesseract", correct=False, confidence=99),
        dict(engine="tesseract", correct=True, confidence=20),
        dict(engine="tesseract", correct=False, confidence=None, omitted=True),
    ]
    assert summarize("tesseract", rows)["omissions"] == 1
    assert summarize("tesseract", rows)["incorrect_native_scores"] == [99]
    with pytest.raises(ValueError):
        summarize("paddle", rows)
    assert pearson([1, 2, 3], [3, 2, 1]) == -1
    assert pearson([1, 1], [2, 3]) is None
