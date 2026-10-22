"""Artifact verification and content-addressed freeze helpers."""

import hashlib
import json
from pathlib import Path

from schemas import Artifact, Manifest


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def verify_artifact(root: Path, artifact: Artifact) -> Path:
    path = (root / artifact.path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("artifact path escapes root")
    if not path.is_file():
        raise ValueError("missing_model")
    data = path.read_bytes()
    if len(data) != artifact.byte_size or digest(data) != artifact.sha256:
        raise ValueError("model_digest_mismatch")
    return path


def read_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_bytes())


def freeze(root: Path, paths: list[str], metadata: dict, output: Path) -> None:
    if not metadata.get("development_selection_complete"):
        raise ValueError("development selection is required")
    if not metadata.get("artifacts_verified") or not metadata.get("linux_gates_passed"):
        raise ValueError("artifact and Linux gates required")
    files = {}
    for name in paths:
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("freeze path escapes root")
        files[name] = digest(path.read_bytes())
    payload = {"version": "ocr-freeze-v1", "files": files, "metadata": metadata}
    with output.open("xb") as stream:
        stream.write(canonical(payload))


def verify_freeze(root: Path, path: Path) -> dict:
    payload = json.loads(path.read_bytes())
    if payload.get("version") != "ocr-freeze-v1" or not payload.get("files"):
        raise ValueError("invalid freeze")
    for name, expected in payload["files"].items():
        p = (root / name).resolve()
        if not p.is_relative_to(root.resolve()) or digest(p.read_bytes()) != expected:
            raise ValueError("frozen file changed")
    return payload
