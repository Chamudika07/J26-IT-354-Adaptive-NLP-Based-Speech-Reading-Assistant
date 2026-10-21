"""Explicit model acquisition from immutable manifest references; never called by evaluation."""

import argparse
import json
import tempfile
import urllib.request
from pathlib import Path

from integrity import verify_artifact
from schemas import Artifact


def provision(manifest: Path, root: Path):
    payload = json.loads(manifest.read_bytes())
    if payload.get("version") != "ocr-artifacts-v1" or not payload.get("artifacts"):
        raise ValueError("unprovisioned manifest")
    root.mkdir(parents=True, exist_ok=True)
    for raw in payload["artifacts"]:
        artifact = Artifact.model_validate(raw)
        destination = (root / artifact.path).resolve()
        if not destination.is_relative_to(root.resolve()):
            raise ValueError("artifact path escapes root")
        if destination.exists():
            verify_artifact(root, artifact)
            continue
        if not artifact.source.startswith("https://"):
            raise ValueError("HTTPS artifact source required")
        with tempfile.TemporaryDirectory(dir=root, prefix="provision-") as scratch:
            with urllib.request.urlopen(artifact.source, timeout=120) as response:
                data = response.read(artifact.byte_size + 1)
            candidate = Path(scratch) / artifact.path
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(data)
            verify_artifact(Path(scratch), artifact)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(data)
    return len(payload["artifacts"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("manifests/artifacts.v1.json"))
    parser.add_argument("--root", type=Path, default=Path("models"))
    args = parser.parse_args()
    print({"verified_artifacts": provision(args.manifest, args.root)})
