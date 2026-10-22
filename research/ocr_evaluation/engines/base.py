"""Native sequence assembly: never geometrically reorder."""

import os
import signal
import subprocess
import tempfile

from schemas import OCRResult

VERSION = "ocr-adapter-v1"


def assemble(result: OCRResult) -> str:
    output = ""
    previous = None
    for unit in result.units:
        if previous is not None:
            output += (
                "\n\n"
                if unit.block != previous.block
                else "\n"
                if unit.line != previous.line
                else " "
            )
        output += unit.text
        previous = unit
    return output


def run_child(command: list[str], timeout: float = 30, env: dict | None = None) -> bytes:
    # File-backed bounded read prevents unbounded PIPE accumulation. OS sandbox/resource
    # limits are still required before accepting arbitrary hostile research inputs.
    with tempfile.TemporaryFile() as output:
        try:
            child = subprocess.Popen(
                command, stdout=output, stderr=subprocess.DEVNULL, env=env, start_new_session=True
            )
        except FileNotFoundError as exc:
            raise ValueError("missing_engine") from exc
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise ValueError("timeout") from exc
        if child.returncode:
            raise ValueError("abnormal_engine_exit")
        output.seek(0)
        data = output.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("adapter_output_limit")
        return data
