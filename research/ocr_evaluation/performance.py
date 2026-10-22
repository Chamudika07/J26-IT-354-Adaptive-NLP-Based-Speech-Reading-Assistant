"""Selected development case: two warmups and ten measured fresh-process repetitions."""

import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from integrity import digest
from report import performance
from schemas import Artifact


def worker(config_path, image):
    config = json.loads(config_path.read_bytes())
    artifacts = [Artifact.model_validate(a) for a in config["artifacts"]]
    started = time.perf_counter()
    if config["engine"] == "tesseract":
        from engines.tesseract import recognize

        result = recognize(
            image,
            Path(config["executable"]),
            Path(config["model_root"]),
            artifacts[0],
            config["engine_version"],
        )
    else:
        from engines.paddle import recognize

        result = recognize(
            image,
            Path(config["model_root"]),
            artifacts,
            config["detection_dir"],
            config["recognition_dir"],
        )
    return dict(
        engine_ms=(time.perf_counter() - started) * 1000,
        child_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        * (1 if sys.platform == "darwin" else 1024),
        memory_method="largest child peak RSS; not simultaneous process-tree peak",
        native_sha256=digest(result.native_output.encode()),
        units=len(result.units),
    )


def measure(config, image, output):
    if "heldout" in str(image) or "phone_camera_photo" in str(image):
        raise ValueError("performance subset is non-photo development only")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    with (output / "timings.jsonl").open("x") as stream:
        for i in range(12):
            start = time.perf_counter()
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--config",
                    str(config.resolve()),
                    "--image",
                    str(image.resolve()),
                ],
                capture_output=True,
                check=True,
                timeout=90,
                env={"PATH": "/usr/bin:/bin"},
            )
            row = json.loads(result.stdout)
            row.update(warmup=i < 2, repetition=i, wall_ms=(time.perf_counter() - start) * 1000)
            stream.write(json.dumps(row) + "\n")
            rows.append(row)
    summary = performance([r["wall_ms"] for r in rows if not r["warmup"]])
    summary.update(
        warmups=2,
        measured=10,
        peak_child_rss_bytes=max(r["child_peak_rss_bytes"] for r in rows if not r["warmup"]),
        source_sha256=digest(image.read_bytes()),
        configuration_sha256=digest(config.read_bytes()),
    )
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            worker(args.config, args.image)
            if args.worker
            else measure(args.config, args.image, args.output)
        )
    )
