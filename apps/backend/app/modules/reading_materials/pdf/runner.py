"""Killable bounded parser process; no credentials inherited and no parser log forwarding."""

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import BoundedSemaphore
from typing import BinaryIO

from app.modules.reading_materials.pdf.contracts import (
    MAX_BYTES,
    MAX_RESULT,
    OUTCOMES,
    WALL_SECONDS,
    ExtractionResult,
    failed,
)

_slots = BoundedSemaphore(2)


def run(stream: BinaryIO, digest: str, byte_count: int) -> ExtractionResult:
    data = stream.read(MAX_BYTES + 1)
    if len(data) != byte_count or hashlib.sha256(data).hexdigest() != digest:
        return failed("integrity_failed")
    stream.seek(0)
    if not _slots.acquire(blocking=False):
        return failed("resource_limit_exceeded")
    try:
        with tempfile.TemporaryFile() as output:
            child = subprocess.Popen(
                [sys.executable, "-I", str(Path(__file__).with_name("worker.py"))],
                stdin=stream,
                stdout=output,
                stderr=subprocess.DEVNULL,
                env={},
                cwd=tempfile.gettempdir(),
                close_fds=True,
                start_new_session=os.name == "posix",
            )
            try:
                child.wait(timeout=WALL_SECONDS)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                return failed("resource_limit_exceeded")
            if child.returncode != 0:
                return failed(
                    "resource_limit_exceeded" if child.returncode < 0 else "backend_failed"
                )
            output.seek(0)
            raw = output.read(MAX_RESULT + 1)
            if len(raw) > MAX_RESULT:
                return failed("resource_limit_exceeded")
            result = ExtractionResult.model_validate_json(raw)
            if result.outcome_code is not None and result.outcome_code not in OUTCOMES:
                return failed("backend_failed")
            return result
    except Exception:
        return failed("backend_failed")
    finally:
        _slots.release()
