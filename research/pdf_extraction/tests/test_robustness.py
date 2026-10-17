"""Benign fixtures / controlled process faults, outside the 66-document corpus."""

import subprocess

import pytest

from adapters import production_extractor as adapter
from generators.corpus import author, render


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("encrypted", "encrypted_pdf"),
        ("malformed", "malformed_pdf"),
        ("action", "unsupported_pdf_features"),
        ("attachment", "unsupported_pdf_features"),
        ("form", "unsupported_pdf_features"),
    ],
)
def test_safe_rejections(tmp_path, mode, code):
    source = author("simple_single_column", "development", 0, 321)
    source["mode"] = mode
    path = tmp_path / "benign.pdf"
    render(source, path)
    result = adapter.extract(path)
    assert result["status"] == "failed"
    assert result["outcome_code"] == code
    assert result["assembled_text"] is None
    assert result["pages"] == []
    assert str(tmp_path) not in str(result)


@pytest.mark.parametrize(("pages", "status"), [(25, "extracted"), (26, "failed")])
def test_page_boundary(tmp_path, pages, status):
    source = author("simple_single_column", "development", 0, 333)
    source["pages"] *= pages
    path = tmp_path / "boundary.pdf"
    render(source, path)
    result = adapter.extract(path)
    assert result["status"] == status
    if status == "failed":
        assert result["outcome_code"] == "page_limit_exceeded"


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("timeout", "resource_limit_exceeded"),
        ("exit", "backend_failed"),
        ("json", "backend_failed"),
        ("unknown_code", "backend_failed"),
    ],
)
def test_controlled_child_faults(tmp_path, monkeypatch, mode, code):
    children = []

    class Child:
        def __init__(self, *args, **kwargs):
            self.returncode = 1 if mode == "exit" else 0
            self.waits = 0
            self.killed = False
            children.append(self)
            kwargs["stdout"].write(
                b'{"status":"failed","outcome_code":"private-secret"}'
                if mode == "unknown_code"
                else b"not JSON"
            )

        def wait(self, timeout=None):
            self.waits += 1
            if mode == "timeout" and not self.killed:
                raise subprocess.TimeoutExpired("harmless-stub", timeout)

        def kill(self):
            self.killed = True

    monkeypatch.setattr(adapter.runner.subprocess, "Popen", Child)
    path = tmp_path / "stub.pdf"
    path.write_bytes(b"%PDF-harmless")
    result = adapter.extract(path)
    assert result["outcome_code"] == code
    assert "private-secret" not in str(result)
    if mode == "timeout":
        assert children[0].killed and children[0].waits == 2


def test_real_timeout_reaps_child(tmp_path, monkeypatch):
    import sys

    original = subprocess.Popen
    children = []

    def spawn(_args, **kwargs):
        child = original([sys.executable, "-I", "-c", "import time; time.sleep(10)"], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(adapter.runner.subprocess, "Popen", spawn)
    monkeypatch.setattr(adapter.runner, "WALL_SECONDS", 0.05)
    path = tmp_path / "timeout.pdf"
    path.write_bytes(b"%PDF-safe-stub")
    result = adapter.extract(path)
    assert result["outcome_code"] == "resource_limit_exceeded"
    assert children[0].poll() is not None


@pytest.mark.parametrize("extra", [0, 1])
def test_byte_boundary_is_safe(tmp_path, extra):
    # Benign bounded comment padding; no compressed streams or payloads.
    path = tmp_path / "padded.pdf"
    path.write_bytes(b"%PDF-1.7\n%" + b"a" * (adapter.contracts.MAX_BYTES + extra - 10))
    assert path.stat().st_size == adapter.contracts.MAX_BYTES + extra
    result = adapter.extract(path)
    assert result["status"] == "failed"
    assert result["assembled_text"] is None
    assert result["outcome_code"] == "malformed_pdf"
