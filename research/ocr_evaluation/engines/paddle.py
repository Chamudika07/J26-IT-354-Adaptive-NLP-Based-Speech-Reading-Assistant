"""Paddle 3.2 adapter contract. Local models only; execution requires verified bundle."""

import json
from pathlib import Path

from integrity import verify_artifact
from schemas import Artifact, OCRResult, Unit

ENGINE_VERSION = "3.2.0"
RUNTIME_VERSION = "3.2.0"


def verify_bundle(root: Path, artifacts: list[Artifact]) -> dict[str, Path]:
    if not artifacts or any(a.engine != "paddle" for a in artifacts):
        raise ValueError("missing_model")
    if not {"recognition", "detection", "dictionary"} <= {a.role for a in artifacts}:
        raise ValueError("incomplete model bundle")
    if len({a.path for a in artifacts}) != len(artifacts):
        raise ValueError("duplicate artifact")
    for a in artifacts:
        if a.engine_version != ENGINE_VERSION or a.runtime_version != RUNTIME_VERSION:
            raise ValueError("engine_version_mismatch")
    return {a.path: verify_artifact(root, a) for a in artifacts}


def normalize(payload: dict) -> OCRResult:
    try:
        texts = payload["rec_texts"]
        scores = payload["rec_scores"]
        polygons = payload["rec_polys"]
        if not len(texts) == len(scores) == len(polygons):
            raise ValueError("unequal arrays")
        units = [
            Unit(text=t, confidence=s, polygon=p, block="native", line=str(i))
            for i, (t, s, p) in enumerate(zip(texts, scores, polygons, strict=True))
        ]
        return OCRResult(
            engine="paddle",
            engine_version=ENGINE_VERSION,
            confidence_scale="native recognition score 0..1; uncalibrated",
            units=units,
            native_output=json.dumps(payload, allow_nan=False),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("malformed_adapter_result") from exc


def recognize(
    image: Path,
    model_root: Path,
    artifacts: list[Artifact],
    detection_dir: str,
    recognition_dir: str,
    timeout: float = 60,
) -> OCRResult:
    import sys
    import tempfile

    from engines.base import run_child

    paths = verify_bundle(model_root, artifacts)
    if detection_dir != "PP-OCRv5_mobile_det" or recognition_dir not in {
        "en_PP-OCRv4_mobile_rec",
        "en_PP-OCRv5_mobile_rec",
    }:
        raise ValueError("unsupported_model_pair")
    model_names = {a.model_name for a in artifacts}
    if model_names != {detection_dir, recognition_dir}:
        raise ValueError("model_bundle_directory_mismatch")
    expected = set(paths.values())
    directories = []
    for name in (detection_dir, recognition_dir):
        directory = (model_root / name).resolve()
        if not directory.is_relative_to(model_root.resolve()) or not directory.is_dir():
            raise ValueError("missing_model")
        actual = {p.resolve() for p in directory.rglob("*") if p.is_file()}
        if not actual or not actual <= expected:
            raise ValueError("unmanifested model file")
        directories.append(str(directory))
    with tempfile.TemporaryDirectory(prefix="ocr-paddle-") as scratch:
        config = Path(scratch) / "config.json"
        config.write_text(
            json.dumps(
                {
                    "image": str(image.resolve()),
                    "detection_dir": directories[0],
                    "recognition_dir": directories[1],
                    "recognition_model_name": recognition_dir,
                }
            )
        )
        raw = run_child(
            [sys.executable, str(Path(__file__).with_name("paddle_worker.py")), str(config)],
            timeout,
            {
                "PATH": "/usr/bin:/bin",
                "PADDLE_PDX_CACHE_HOME": scratch,
                "OMP_NUM_THREADS": "1",
                "HF_HUB_OFFLINE": "1",
            },
        )
    try:
        return normalize(json.loads(raw))
    except (ValueError, TypeError) as exc:
        raise ValueError("malformed_adapter_result") from exc
