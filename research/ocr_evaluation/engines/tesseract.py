"""Explicit English TSV adapter; native confidence is not a probability."""

import csv
import io
from pathlib import Path

from engines.base import run_child
from integrity import verify_artifact
from schemas import Artifact, OCRResult, Unit


def parse_tsv(raw: str, version: str) -> OCRResult:
    units = []
    try:
        for row in csv.DictReader(io.StringIO(raw), delimiter="\t", quoting=csv.QUOTE_NONE):
            if int(row["level"]) != 5:
                continue
            confidence = float(row["conf"])
            x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
            units.append(
                Unit(
                    text=row["text"],
                    block=row["block_num"],
                    line=f"{row['par_num']}:{row['line_num']}",
                    confidence=None if confidence == -1 else confidence,
                    polygon=[(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                )
            )
        if not raw.startswith("level\t"):
            raise ValueError("missing TSV header")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("malformed_adapter_result") from exc
    return OCRResult(
        engine="tesseract",
        engine_version=version,
        confidence_scale="native TSV 0..100; -1 unavailable",
        units=units,
        native_output=raw,
    )


def recognize(
    image: Path,
    executable: Path,
    model_root: Path,
    artifact: Artifact,
    expected_version: str,
    psm: int = 3,
    timeout: float = 30,
) -> OCRResult:
    if not expected_version.startswith("5."):
        raise ValueError("Tesseract 5.x required")
    model = verify_artifact(model_root, artifact)
    if model.name != "eng.traineddata" or artifact.engine != "tesseract":
        raise ValueError("explicit English traineddata required")
    env = {"PATH": "/usr/bin:/bin", "OMP_THREAD_LIMIT": "1", "LC_ALL": "C"}
    version = run_child([str(executable), "--version"], env=env).decode().splitlines()[0]
    if version != "tesseract " + expected_version:
        raise ValueError("engine_version_mismatch")
    raw = run_child(
        [
            str(executable),
            str(image),
            "stdout",
            "--tessdata-dir",
            str(model.parent),
            "-l",
            "eng",
            "--psm",
            str(psm),
            "-c",
            "tessedit_create_tsv=1",
        ],
        timeout,
        env,
    )
    return parse_tsv(raw.decode("utf-8"), expected_version)
