"""One-time frozen evaluation. Only --execute invokes OCR; verification never does."""

import argparse
import json
import os
import platform
import signal
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from development import score_page
from heldout_preparation import ROOT, validate
from integrity import canonical, digest, verify_artifact
from schemas import Artifact, PageResult
from verify_development_freeze import verify as verify_development

RUN = ROOT / "artifacts/heldout-final-v1"
INDEX = ROOT / "manifests/heldout-execution.v1.json"
FREEZE = ROOT / "manifests/development-configuration-freeze.v1.json"
PREPARATION = ROOT / "manifests/heldout-preparation.v1.json"


def now():
    return datetime.now(UTC).isoformat()


def write_new(path, payload):
    with path.open("xb") as stream:
        stream.write(canonical(payload))
        stream.flush()
        os.fsync(stream.fileno())


def guard(run=RUN, index=INDEX):
    if run.exists() or index.exists():
        raise ValueError("held-out execution already reserved; rerun forbidden")
    for parent in (ROOT / "artifacts", ROOT / "results", ROOT / "manifests"):
        for path in parent.rglob("*"):
            if "heldout" in path.name.lower() and any(
                word in path.name.lower() for word in ("execution", "result", "final", "run-index")
            ):
                raise ValueError("prior held-out result/index/directory exists")


def corpus():
    rows = json.loads(PREPARATION.read_bytes())["records"]
    cases = []
    for source in rows:
        row = dict(source)
        photo = row["category"] == "phone_camera_photo"
        path = ROOT / row["expected_photo_path" if photo else "image"]
        row["source_digest"] = row["photo_source_digest"] if photo else row["source_digest"]
        truth = json.loads((ROOT / row["truth"]).read_bytes())
        cases.append((row, truth, path))
    return cases


def configurations():
    frozen = json.loads(FREEZE.read_bytes())
    configs = {}
    for engine, selected in frozen["selected"].items():
        path = ROOT / "artifacts" / selected["ao_run"] / "config.json"
        config = json.loads(path.read_bytes())
        if digest(path.read_bytes()) != selected["ao_config_sha256"]:
            raise ValueError("frozen config mismatch")
        for item in config["artifacts"]:
            verify_artifact(Path(config["model_root"]), Artifact.model_validate(item))
        configs[engine] = config  # Byte-equivalent frozen configuration, including experiment ID.
    return configs


class Capture:
    """Identical commands/environment/timeouts; retain stdout and stderr even on failure."""

    def __init__(self, directory):
        self.directory = directory
        self.calls = []

    def __call__(self, command, timeout=30, env=None):
        number = len(self.calls)
        metadata = dict(command=command, timeout=timeout, started_at=now())
        self.calls.append(metadata)
        stdout = self.directory / f"process-{number}.stdout"
        stderr = self.directory / f"process-{number}.stderr"
        try:
            with stdout.open("xb") as out, stderr.open("xb") as err:
                child = subprocess.Popen(
                    command, stdout=out, stderr=err, env=env, start_new_session=True
                )
                metadata["pid"] = child.pid
                try:
                    child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                    raise ValueError("timeout") from None
                metadata["returncode"] = child.returncode
            if child.returncode:
                raise ValueError("abnormal_engine_exit")
            data = stdout.read_bytes()
            if len(data) > 4 * 1024 * 1024:
                raise ValueError("adapter_output_limit")
            return data
        except Exception:
            metadata["exception"] = traceback.format_exc()
            raise
        finally:
            metadata["finished_at"] = now()
            write_new(self.directory / f"process-{number}.json", metadata)


def execute():
    guard()
    preflight = validate()
    if preflight["phone_photos_registered"] != 3 or preflight["heldout_executions"] != 0:
        raise ValueError("incomplete pre-run gate")
    verify_development(FREEZE)
    configs = configurations()
    if version("paddleocr") != "3.2.0" or version("paddlepaddle") != "3.2.0":
        raise ValueError("Paddle package mismatch")
    # Version query only: no image or OCR is passed during this check.
    engine_version = subprocess.check_output(
        [configs["tesseract"]["executable"], "--version"], text=True
    ).splitlines()[0]
    if engine_version != "tesseract 5.5.3":
        raise ValueError("Tesseract version mismatch")
    cases = corpus()
    RUN.mkdir(exist_ok=False)
    inputs = {str(PREPARATION.relative_to(ROOT)): digest(PREPARATION.read_bytes())}
    inputs[str(FREEZE.relative_to(ROOT))] = digest(FREEZE.read_bytes())
    for record, _, path in cases:
        inputs[str(path.relative_to(ROOT))] = digest(path.read_bytes())
        inputs[record["truth"]] = digest((ROOT / record["truth"]).read_bytes())
    start = dict(
        version="ocr-heldout-execution-v1",
        started_at=now(),
        preflight=preflight,
        planned_evaluations=96,
        input_sha256=inputs,
        runner_sha256=digest(Path(__file__).read_bytes()),
        environment=dict(
            python=sys.version,
            platform=platform.platform(),
            packages={p: version(p) for p in ("paddleocr", "paddlepaddle", "pillow", "numpy")},
        ),
        frozen_configuration_sha256={k: digest(canonical(v)) for k, v in configs.items()},
        corpus_version="ocr-heldout-preparation-v1",
        tuning=False,
    )
    write_new(RUN / "reservation.json", start)
    completed = []
    from engines import base, paddle, tesseract

    original_base, original_tess = base.run_child, tesseract.run_child
    try:
        for engine, config in configs.items():
            directory = RUN / engine
            directory.mkdir()
            write_new(directory / "config.json", config)
            for record, truth, path in cases:
                case_dir = directory / record["fixture_id"]
                case_dir.mkdir(exist_ok=False)
                write_new(case_dir / "started.json", {"started_at": now()})
                capture = Capture(case_dir)
                base.run_child = tesseract.run_child = capture
                artifacts = [Artifact.model_validate(a) for a in config["artifacts"]]

                def adapter(
                    image, config=config, artifacts=artifacts, engine=engine, case_dir=case_dir
                ):
                    try:
                        if engine == "tesseract":
                            return tesseract.recognize(
                                image,
                                Path(config["executable"]),
                                Path(config["model_root"]),
                                artifacts[0],
                                config["engine_version"],
                                psm=config["psm"],
                            )
                        return paddle.recognize(
                            image,
                            Path(config["model_root"]),
                            artifacts,
                            config["detection_dir"],
                            config["recognition_dir"],
                        )
                    except Exception:
                        write_new(case_dir / "failure.json", {"traceback": traceback.format_exc()})
                        raise

                row = score_page(record, truth, path, config, adapter, case_dir)
                row.split = "heldout"
                row.review_label = "final_heldout_once"
                row.notes = ["Frozen final held-out evaluation; no tuning or retry."]
                write_new(case_dir / "result.json", row.model_dump(mode="json"))
                with (directory / "pages.jsonl").open("a") as stream:
                    stream.write(row.model_dump_json() + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                completed.append((engine, record["fixture_id"], row.outcome))
                print(engine, record["fixture_id"], row.outcome, flush=True)
                if row.outcome != "success":
                    raise RuntimeError("execution stopped on failure; no automatic recovery")
    finally:
        base.run_child, tesseract.run_child = original_base, original_tess
    finish = dict(
        start,
        finished_at=now(),
        status="completed_no_rerun",
        executed_evaluations=len(completed),
        executed_by_engine={k: 48 for k in configs},
        failures=[],
        exclusions=[],
        files={
            str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in RUN.rglob("*") if p.is_file()
        },
    )
    write_new(INDEX, finish)
    return verify()


def verify():
    """Validate saved evidence only; never calls an OCR adapter."""
    manifest = json.loads(INDEX.read_bytes())
    if manifest["status"] != "completed_no_rerun" or manifest["executed_evaluations"] != 96:
        raise ValueError("evaluation not complete")
    if digest(Path(__file__).read_bytes()) != manifest["runner_sha256"]:
        raise ValueError("runner changed after execution")
    actual = {str(p.relative_to(ROOT)) for p in RUN.rglob("*") if p.is_file()}
    if actual != set(manifest["files"]):
        raise ValueError("execution artifact inventory mismatch")
    for name, expected in (manifest["input_sha256"] | manifest["files"]).items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path.read_bytes()) != expected:
            raise ValueError("execution/input hash mismatch")
    expected_cases = {r["fixture_id"]: r for r, _, _ in corpus()}
    configs = configurations()
    for engine, config in configs.items():
        directory = RUN / engine
        rows = [
            PageResult.model_validate_json(line)
            for line in (directory / "pages.jsonl").read_bytes().splitlines()
        ]
        if len(rows) != 48 or {r.fixture_id for r in rows} != set(expected_cases):
            raise ValueError("execution case count/identity mismatch")
        for row in rows:
            case = expected_cases[row.fixture_id]
            if (
                row.engine != engine
                or row.split != "heldout"
                or row.outcome != "success"
                or row.source_digest != case["source_digest"]
                or row.ground_truth_digest != case["ground_truth_digest"]
                or row.configuration_fingerprint != digest(canonical(config))
            ):
                raise ValueError("execution row mismatch")
            case_dir = directory / row.fixture_id
            calls = list(case_dir.glob("process-*.json"))
            if len(calls) != (2 if engine == "tesseract" else 1):
                raise ValueError("process invocation count mismatch")
            for suffix, expected in (
                ("native", row.native_output_digest),
                ("assembled", row.assembled_text_digest),
            ):
                if digest((case_dir / f"{row.fixture_id}.{suffix}.txt").read_bytes()) != expected:
                    raise ValueError("raw output hash mismatch")
    verify_development(FREEZE)
    return dict(status="verified", tesseract=48, paddle=48, evaluations=96, rerun_forbidden=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(execute() if args.execute else verify()))
