"""Equal-budget provisional development comparison; no freeze or held-out entry point."""

import argparse
import json
from pathlib import Path

from development import run
from integrity import canonical

CONDITIONS = [("baseline", {}), ("grayscale", {}), ("contrast", {"factor": 1.3})]


def compare(
    index: Path, manifest: Path, artifacts: Path, model_root: Path, executable: Path, output: Path
):
    records = json.loads(artifacts.read_bytes())["artifacts"]
    output.mkdir(parents=True, exist_ok=False)
    for engine, version in [("tesseract", "5.5.3"), ("paddle", "3.2.0")]:
        for recipe, parameters in CONDITIONS:
            name = f"{engine}-{recipe}"
            config = dict(
                experiment_id=output.name + "-" + name,
                engine=engine,
                engine_version=version,
                runtime_version=version,
                model_root=str(model_root.resolve()),
                artifacts=[a for a in records if a["engine"] == engine],
                recipe=recipe,
                parameters=parameters,
            )
            if engine == "tesseract":
                config.update(executable=str(executable.resolve()), psm=3)
            else:
                config.update(
                    detection_dir="PP-OCRv5_mobile_det", recognition_dir="en_PP-OCRv4_mobile_rec"
                )
            config_path = output / (name + ".config.json")
            config_path.write_bytes(canonical(config))
            run(index, manifest, config_path, output / name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("manifests/benchmark.v1.json"))
    parser.add_argument("--artifacts", type=Path, default=Path("manifests/artifacts.v1.json"))
    parser.add_argument("--models", type=Path, default=Path("models"))
    parser.add_argument("--tesseract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compare(args.index, args.manifest, args.artifacts, args.models, args.tesseract, args.output)
