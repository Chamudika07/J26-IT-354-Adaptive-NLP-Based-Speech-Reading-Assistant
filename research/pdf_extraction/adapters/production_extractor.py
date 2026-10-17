"""Call the approved isolated runner; never import or call extract()."""

import hashlib
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/backend"))
from app.modules.reading_materials.normalization import normalize  # noqa: E402
from app.modules.reading_materials.pdf import contracts, runner  # noqa: E402


def commit():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def extract(path):
    start = time.perf_counter_ns()
    data = path.read_bytes()
    with path.open("rb") as stream:
        result = runner.run(stream, hashlib.sha256(data).hexdigest(), len(data))
    return {
        **result.model_dump(),
        "elapsed_ms": (time.perf_counter_ns() - start) / 1e6,
        "fingerprint": contracts.fingerprint(),
        "versions": contracts.provenance(),
    }


def normalized(text):
    if not text:
        return ""
    return normalize(text).text


def environment():
    from schemas import digest

    cpu, ram = platform.processor() or None, None
    if sys.platform == "darwin":
        try:
            cpu = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip()
            ram = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True))
        except (OSError, ValueError, subprocess.CalledProcessError):
            pass
    return {
        "os": platform.system(),
        "os_version": platform.platform(),
        "architecture": platform.machine(),
        "cpu": cpu,
        "ram_bytes": ram,
        "ram_reason": None if ram is not None else "host memory query unavailable",
        "python": platform.python_version(),
        "production_commit": commit(),
        "versions": contracts.provenance(),
        "extraction_fingerprint": contracts.fingerprint(),
        "production_lock_sha256": digest(ROOT / "apps/backend/uv.lock"),
        "research_lock_sha256": digest(Path(__file__).resolve().parents[1] / "uv.lock"),
        "resource_capabilities": {
            "cpu_seconds": 15 if sys.platform != "win32" else None,
            "wall_seconds": 30,
            "hard_address_space_bytes": 512 * 1024 * 1024
            if sys.platform.startswith("linux")
            else None,
            "memory_note": "no hard memory limit claimed on macOS; RSS unavailable",
        },
    }
