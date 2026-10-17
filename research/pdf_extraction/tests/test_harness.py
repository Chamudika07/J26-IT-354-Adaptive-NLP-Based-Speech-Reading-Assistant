import csv
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import evaluate
from adapters import production_extractor as adapter
from generators.corpus import author, generate, render
from report import aggregate, report
from schemas import Manifest, Result, digest, read_text, resolve, validate_artifacts


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("development")
    manifest = generate(root, "development", adapter.commit())
    (root / "manifest.json").write_text(manifest.model_dump_json())
    return root, manifest


def test_manifest_and_independent_source(corpus):
    root, manifest = corpus
    validate_artifacts(manifest, root)
    assert len(manifest.fixture_entries) == 22
    assert {f.split for f in manifest.fixture_entries} == {"development"}
    for f in manifest.fixture_entries:
        source = json.loads(resolve(root, f.authoring_source.reference).read_text())
        assert f.expected_policy_outcome == source["expected_policy_outcome"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_sha256", "bad"),
        ("split", "train"),
        ("primary_category", "other"),
        ("creator_or_source_reference", ""),
        ("license_or_permission_reference", ""),
        ("provenance_type", "unknown"),
        ("source_byte_count", -1),
    ],
)
def test_bad_manifest_fields(corpus, field, value):
    data = corpus[1].model_dump()
    data["fixture_entries"][0][field] = value
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


def test_duplicate_and_leaked_families(corpus):
    data = corpus[1].model_dump()
    extra = deepcopy(data["fixture_entries"][0])
    data["fixture_entries"].append(extra)
    with pytest.raises(ValidationError, match="duplicate"):
        Manifest.model_validate(data)
    extra["fixture_id"] = "new-id"
    extra["source_sha256"] = "f" * 64
    extra["split"] = "heldout"
    with pytest.raises(ValidationError, match="crosses split"):
        Manifest.model_validate(data)


@pytest.mark.parametrize("mode", ["missing", "hash", "visible", "offset", "assembly"])
def test_artifact_corruption(corpus, tmp_path, mode):
    import shutil

    root, original = corpus
    shutil.copytree(root, tmp_path / "copy")
    root = tmp_path / "copy"
    manifest = original.model_copy(deep=True)
    f = manifest.fixture_entries[0]
    if mode == "missing":
        resolve(root, f.page_ground_truth[0].reference).unlink()
    elif mode == "hash":
        resolve(root, f.page_ground_truth[0].reference).write_text("changed")
    elif mode == "assembly":
        path = resolve(root, f.assembled_ground_truth.reference)
        path.write_text("changed")
        f.assembled_ground_truth.sha256 = digest(path)
    else:
        path = resolve(root, f.structural_annotation.reference)
        structure = json.loads(path.read_text())
        if mode == "visible":
            resolve(root, structure["visible_ground_truth"]["reference"]).write_text("changed")
        else:
            structure["offsets"] = [[0, 1]]
            path.write_text(json.dumps(structure))
            f.structural_annotation.sha256 = digest(path)
    with pytest.raises((ValueError, OSError)):
        validate_artifacts(manifest, root)


def test_byte_exact_newlines_and_path_guard(tmp_path):
    path = tmp_path / "text"
    path.write_bytes(b"a\r\nb\r")
    assert read_text(path) == "a\r\nb\r"
    with pytest.raises(ValueError):
        resolve(tmp_path, "../escape")


def test_generator_deterministic(tmp_path):
    source = author("simple_single_column", "development", 0, 123)
    render(source, tmp_path / "a.pdf")
    render(source, tmp_path / "b.pdf")
    assert digest(tmp_path / "a.pdf") == digest(tmp_path / "b.pdf")


def test_duplicate_generation_refused(corpus):
    with pytest.raises(ValueError, match="already generated"):
        generate(corpus[0], "development", adapter.commit(), corpus[1])


def test_order():
    fixtures = [SimpleNamespace(fixture_id=str(i)) for i in range(20)]
    assert evaluate.ordered(fixtures, 12) == evaluate.ordered(fixtures[::-1], 12)
    assert evaluate.ordered(fixtures, 12) != evaluate.ordered(fixtures, 13)


@pytest.fixture
def result(corpus):
    root, manifest = corpus
    f = manifest.fixture_entries[0]
    raw = adapter.extract(resolve(root, f.source_artifact_reference))
    assert raw["status"] == "extracted"
    return evaluate.measure(f, root, raw, "test", manifest.production_commit, [1.0, 2.0, 3.0])


def test_adapter_result_and_versions(result):
    assert result.extraction_fingerprint == adapter.contracts.fingerprint()
    assert result.detail["raw"]["versions"] == adapter.contracts.provenance()
    assert result.exact_match is True
    assert result.peak_memory_bytes is None
    assert result.page_order_correct is True
    assert result.raw_page_cer == 0
    assert result.latency_median_ms == 2


@pytest.mark.parametrize(
    "field", ["character_insertions", "word_deletions", "raw_wer", "latency_median_ms"]
)
def test_result_rejects_invalid_numbers(result, field):
    data = result.model_dump()
    data[field] = -1
    with pytest.raises(ValidationError):
        Result.model_validate(data)


def test_failure_nulls_and_missing_outputs(corpus):
    root, manifest = corpus
    raw = {
        **adapter.contracts.failed("backend_failed").model_dump(),
        "fingerprint": adapter.contracts.fingerprint(),
        "versions": adapter.contracts.provenance(),
    }
    result = evaluate.measure(
        manifest.fixture_entries[0], root, raw, "test", manifest.production_commit, [2.0]
    )
    assert result.raw_assembled_cer == 1
    assert result.raw_wer == 1
    assert result.observed_page_count is None
    assert result.lexical_page_coverage is None
    assert result.review_label == "extraction_failure"
    assert Result.model_validate_json(result.model_dump_json()) == result


def test_offsets_validation(corpus, result):
    raw = deepcopy(result.detail["raw"])
    raw["pages"][0]["text_end"] = 1
    with pytest.raises(ValueError, match="offsets"):
        evaluate.measure(
            corpus[1].fixture_entries[0], corpus[0], raw, "test", adapter.commit(), [1.0]
        )


def test_jsonl_csv_and_aggregation(tmp_path, result):
    (tmp_path / "results.jsonl").write_text(result.model_dump_json() + "\n")
    report(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["operational_fidelity"]["characters"]["rate"] == 0
    assert summary["routing_counts"]["extracted"]["extracted"] == 1
    assert summary["routing_row_percent"]["failed"]["failed"] is None
    with (tmp_path / "summary.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["peak_memory_bytes"] == ""
    assert aggregate([])["policy_agreement"] is None
    assert aggregate([])["operational_fidelity"]["words"]["rate"] is None
    (tmp_path / "results.jsonl").write_text((result.model_dump_json() + "\n") * 2)
    with pytest.raises(ValueError, match="duplicate"):
        report(tmp_path)


def test_cli_errors_and_freeze_gate(corpus, tmp_path):
    assert evaluate.main(["validate", "--root", str(tmp_path / "absent")]) == 2
    assert evaluate.main(["generate", "--root", str(adapter.ROOT / "apps/backend")]) == 2
    assert evaluate.main(["freeze", "--root", str(corpus[0])]) == 2
    assert evaluate.main(["generate", "--split", "heldout", "--root", str(corpus[0])]) == 2


def test_resume_provenance_and_existing_output(corpus, tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(ValueError, match="output exists"):
        evaluate.run(corpus[1], corpus[0], output, "development")
    (output / "environment.json").write_text("{}")
    with pytest.raises(ValueError, match="provenance"):
        evaluate.run(corpus[1], corpus[0], output, "development", resume=True)


def test_adapter_calls_approved_runner(corpus, monkeypatch):
    calls = []

    def runner(stream, hash_value, size):
        calls.append((stream.read(), hash_value, size))
        return adapter.contracts.failed("backend_failed")

    monkeypatch.setattr(adapter.runner, "run", runner)
    f = corpus[1].fixture_entries[0]
    result = adapter.extract(resolve(corpus[0], f.source_artifact_reference))
    assert result["outcome_code"] == "backend_failed"
    assert calls[0][1:] == (f.source_sha256, f.source_byte_count)
    assert result["elapsed_ms"] >= 0


def test_successful_resume_skips_completed(corpus, tmp_path, monkeypatch, result):
    from generators.corpus import write_json

    root, manifest = corpus
    output = tmp_path / "resume"
    output.mkdir()
    metadata = {
        "environment": adapter.environment(),
        "metric_version": evaluate.VERSION,
        "manifest_sha256": digest(root / "manifest.json"),
        "benchmark_version": manifest.benchmark_version,
        "protocol_version": manifest.protocol_version,
        "order": [
            f.fixture_id for f in evaluate.ordered(manifest.fixture_entries, manifest.split_seed)
        ],
        "seed": manifest.split_seed,
        "warmups": 2,
        "repetitions": 10,
        "freeze": evaluate.freeze_contract(),
    }
    write_json(output / "environment.json", metadata)
    with (output / "results.jsonl").open("w") as stream:
        for f in manifest.fixture_entries:
            clone = result.model_copy(
                update={"fixture_id": f.fixture_id, "category": f.primary_category}
            )
            stream.write(clone.model_dump_json() + "\n")

    def forbidden(*args):
        raise AssertionError("completed fixtures must not be rerun")

    monkeypatch.setattr(adapter, "extract", forbidden)
    evaluate.run(manifest, root, output, "development", resume=True)
    assert len((output / "results.jsonl").read_text().splitlines()) == 22


def test_font_and_geometry_rejection(tmp_path):
    source = author("simple_single_column", "development", 0, 1)
    source["pages"][0]["blocks"][0]["text"] = "not supported 😀"
    with pytest.raises(ValueError, match="font"):
        render(source, tmp_path / "bad.pdf")
    source["pages"][0]["blocks"][0]["text"] = "a" * 1000
    with pytest.raises(ValueError, match="beyond page"):
        render(source, tmp_path / "bad.pdf")
