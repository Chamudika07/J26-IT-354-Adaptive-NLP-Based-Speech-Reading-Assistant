"""Standalone child entry point; no app settings, environment, or DB connections."""

import logging
import os
import sys
from pathlib import Path

# -I excludes cwd and PYTHONPATH; import only this installed backend source tree.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
os.environ.clear()
logging.disable(logging.CRITICAL)


def deny_network(event: str, args: object) -> None:
    if event.startswith("socket."):
        raise PermissionError("Network disabled")


sys.addaudithook(deny_network)
from app.modules.reading_materials.pdf.contracts import (  # noqa: E402
    CPU_SECONDS,
    MAX_BYTES,
    MAX_RESULT,
    MEMORY_BYTES,
    failed,
)

if os.name == "posix":
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RESULT, MAX_RESULT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.platform.startswith("linux"):
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))

from app.modules.reading_materials.pdf.extractor import extract  # noqa: E402

try:
    result = extract(sys.stdin.buffer.read(MAX_BYTES + 1))
except BaseException:
    result = failed("backend_failed")
sys.stdout.write(result.model_dump_json())
