"""Development-only image evaluation; never opens or executes held-out inputs."""

import argparse
import json
import tempfile
import time
from pathlib import Path

from engines.base import assemble
from integrity import canonical, digest, read_manifest, verify_artifact
from metrics import fidelity
from preprocessing.recipes import apply, decode, pixel_digest
from report import summarize
from schemas import Artifact, OCRResult, PageResult


def prepare_cases(index_path: Path, manifest_path: Path) -> list[tuple[dict, dict, Path]]:
    manifest = read_manifest(manifest_path)
    known = {c.fixture_id: c for c in manifest.cases}
    index = json.loads(index_path.read_bytes())
    records = index["records"]
    if len({r["fixture_id"] for r in records}) != len(records):
        raise ValueError("duplicate fixture ID")
    prepared = []
    for record in sorted(records, key=lambda r: r["fixture_id"]):
        case = known[record["fixture_id"]]
        if case.split != "development" or record["split"] != "development":
            raise ValueError("development-only execution")
        if case.category == "phone_camera_photo":
            raise ValueError("phone photographs deferred; print masters are not photos")
        if (
            case.source_family_id != record["source_family_id"]
            or case.category != record["category"]
        ):
            raise ValueError("manifest identity mismatch")
    for record in sorted(records, key=lambda r: r["fixture_id"]):
        case = known[record["fixture_id"]]
        image_path = index_path.parent / (case.fixture_id + ".png")
        truth_path = index_path.parent / (case.fixture_id + ".truth.json")
        if digest(image_path.read_bytes()) != record["source_digest"]:
            raise ValueError("source digest mismatch")
        truth_bytes = truth_path.read_bytes()
        if digest(truth_bytes) != record["ground_truth_digest"]:
            raise ValueError("ground truth digest mismatch")
        truth = json.loads(truth_bytes)
        if truth["fixture_id"] != case.fixture_id or truth["page_number"] != 1:
            raise ValueError("ground truth identity mismatch")
        if truth["transcription"]["words"] != truth["transcription"]["text"].split():
            raise ValueError("ground truth token mismatch")
        prepared.append((record, truth, image_path))
    if not prepared:
        raise ValueError("empty development selection")
    return prepared


def score_page(
    record: dict, truth: dict, image_path: Path, config: dict, recognize, output: Path
) -> PageResult:
    """Callback is a real adapter in CLI; tests use labelled fixtures in temporary directories."""
    started = time.perf_counter()
    stage = "decode"
    native = None
    assembled = None
    image = None
    preprocessing = None
    timing = {}
    failure = None
    mime = {".png": "image/png", ".jpg": "image/jpeg"}.get(image_path.suffix.lower())
    if mime is None:
        raise ValueError("unsupported development source extension")
    try:
        image = decode(image_path, mime)
        stage = "preprocessing"
        before = time.perf_counter()
        processed, preprocessing = apply(
            image, config.get("recipe", "baseline"), **config.get("parameters", {})
        )
        timing["preprocessing"] = (time.perf_counter() - before) * 1000
        with tempfile.TemporaryDirectory(prefix="ocr-development-") as scratch:
            derived = Path(scratch) / "input.png"
            processed.save(derived)
            stage = "engine"
            before = time.perf_counter()
            native = OCRResult.model_validate(recognize(derived))
            if (
                native.engine != config["engine"]
                or native.engine_version != config["engine_version"]
            ):
                raise ValueError("engine_version_mismatch")
            timing["engine_process_including_load"] = (time.perf_counter() - before) * 1000
        stage = "assembly"
        assembled = assemble(native)
    except (ValueError, OSError, RuntimeError) as exc:
        # Fixed class/code, not arbitrary error text which could contain source content.
        failure = type(exc).__name__
    timing["page_wall_before_serialization"] = (time.perf_counter() - started) * 1000
    reference = truth["transcription"]["text"]
    scores = fidelity(reference, assembled) if assembled is not None else None
    metrics = {}
    for kind, key, rate in [("character", "characters", "cer"), ("word", "words", "wer")]:
        score = scores[key] if scores is not None else None
        for edit in ["substitutions", "deletions", "insertions"]:
            metrics[f"{kind}_{edit}"] = score[edit] if score else None
        metrics[f"reference_{kind}_count"] = score["reference_units"] if score else None
        metrics[rate] = score["rate"] if score else None
    native_bytes = native.native_output.encode() if failure is None and native else None
    assembled_bytes = assembled.encode() if failure is None and assembled is not None else None
    if native_bytes is not None:
        (output / (record["fixture_id"] + ".native.txt")).write_bytes(native_bytes)
        (output / (record["fixture_id"] + ".assembled.txt")).write_bytes(assembled_bytes)
    reasons = {
        "peak_memory_bytes": "process-tree RSS not instrumented",
        "line_order_result": "independent region matching not performed",
        "block_order_score": "independent region matching not performed",
        "table_failure_counts": "independent cell matching not performed",
        "rasterizer": "direct PNG input",
        "rasterizer_version": "direct PNG input",
        "render_dpi": "direct PNG input",
        "render_pixel_digest": "direct PNG input",
        "confidence_summary": "aligned confidence analysis not performed",
    }
    row = PageResult(
        experiment_id=config["experiment_id"],
        fixture_id=record["fixture_id"],
        source_family_id=record["source_family_id"],
        category=record["category"],
        feature_tags=[],
        split="development",
        page_number=1,
        source_digest=record["source_digest"],
        ground_truth_digest=record["ground_truth_digest"],
        engine=config["engine"],
        configuration_fingerprint=digest(canonical(config)),
        outcome="failed" if failure else "success",
        failure_stage=stage if failure else None,
        failure_code=failure,
        exact_match=assembled == reference if failure is None else None,
        metric_status=(
            "unavailable_engine_failure" if failure else scores["characters"]["metric_status"]
        ),
        input_kind="JPEG" if mime == "image/jpeg" else "PNG",
        input_dimensions=image.size if image else None,
        input_pixel_digest=pixel_digest(image) if image else None,
        preprocessing_recipe=config.get("recipe", "baseline"),
        preprocessing_version=preprocessing["version"] if preprocessing else None,
        preprocessing_parameters=config.get("parameters", {}),
        preprocessed_pixel_digest=preprocessing["output_pixel_digest"] if preprocessing else None,
        engine_version=config["engine_version"],
        runtime_version=config["runtime_version"],
        model_name=config["model_name"],
        model_version=config["model_version"],
        model_digest=config["model_digest"],
        native_output_digest=digest(native_bytes) if native_bytes is not None else None,
        assembled_text_digest=digest(assembled_bytes) if assembled_bytes is not None else None,
        confidence_scale=native.confidence_scale if native and not failure else None,
        latency_ms=timing,
        peak_memory_bytes=None,
        memory_method="unavailable",
        review_label=(
            "user_attested_development_phone_photo"
            if record["category"] == "phone_camera_photo"
            else "draft_development_only"
        ),
        unavailable_reasons=reasons,
        evidence={
            "authoring_status": record["status"],
            "units": [u.model_dump(mode="json") for u in native.units]
            if native and not failure
            else [],
        },
        notes=[
            "Genuine phone photo of short two-line development master; limited representativeness."
            if record["category"] == "phone_camera_photo"
            else "Unreviewed synthetic drafts; not a final comparison or engine-selection result."
        ],
        **metrics,
    )
    # Every null measurement has an explicit reason, including failures and zero denominators.
    for name, value in row.model_dump().items():
        if value is None and name not in {"failure_stage", "failure_code"}:
            row.unavailable_reasons.setdefault(
                name, "failed before measurement" if failure else "not measured or not applicable"
            )
    if not failure and not reference:
        row.unavailable_reasons["cer"] = "undefined_zero_reference"
    if not failure and not reference.split():
        row.unavailable_reasons["wer"] = "undefined_zero_reference"
    return row


def run(index_path: Path, manifest_path: Path, config_path: Path, output: Path) -> None:
    prepared = prepare_cases(index_path, manifest_path)
    run_prepared(prepared, config_path, output)


def run_prepared(prepared: list[tuple[dict, dict, Path]], config_path: Path, output: Path) -> None:
    """Run a prevalidated development-only selection through the same adapter/scorer."""
    if not prepared or any(record["split"] != "development" for record, _, _ in prepared):
        raise ValueError("development-only execution")
    config = json.loads(config_path.read_bytes())
    model_root = Path(config["model_root"]).resolve()
    artifacts = [Artifact.model_validate(a) for a in config["artifacts"]]
    if not artifacts:
        raise ValueError("missing_model")
    for artifact in artifacts:
        verify_artifact(model_root, artifact)
        if artifact.engine != config["engine"]:
            raise ValueError("engine/model mismatch")
    config["model_digest"] = digest(canonical([a.model_dump() for a in artifacts]))
    config["model_name"] = ",".join(sorted({a.model_name for a in artifacts}))
    config["model_version"] = ",".join(sorted({a.revision for a in artifacts}))
    if config["engine"] == "tesseract":
        from engines.tesseract import recognize

        models = [a for a in artifacts if a.role == "recognition"]
        if len(models) != 1:
            raise ValueError("exactly one English traineddata required")

        def adapter(path):
            return recognize(
                path,
                Path(config["executable"]),
                model_root,
                models[0],
                config["engine_version"],
                psm=config.get("psm", 3),
            )
    elif config["engine"] == "paddle":
        from engines.paddle import recognize

        def adapter(path):
            return recognize(
                path, model_root, artifacts, config["detection_dir"], config["recognition_dir"]
            )
    else:
        raise ValueError("unsupported engine")
    output.mkdir(parents=True, exist_ok=False)
    (output / "config.json").write_bytes(canonical(config))
    rows = []
    with (output / "pages.jsonl").open("x") as stream:
        for record, truth, path in prepared:
            row = score_page(record, truth, path, config, adapter, output)
            stream.write(row.model_dump_json() + "\n")
            stream.flush()
            rows.append(row)
    (output / "summary.json").write_bytes(canonical(summarize(rows)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/benchmark.v1.json"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.index, args.manifest, args.config, args.output)
