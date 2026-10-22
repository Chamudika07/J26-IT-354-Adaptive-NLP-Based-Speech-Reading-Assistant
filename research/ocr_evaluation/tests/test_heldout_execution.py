"""Mock-only execution safety tests: no OCR or real subprocess runs."""

import json

import pytest

from heldout_execution import Capture, guard, write_new


def test_reservation_prevents_retry(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    with pytest.raises(ValueError, match="rerun forbidden"):
        guard(run, tmp_path / "index")


def test_index_prevents_retry(tmp_path):
    index = tmp_path / "index"
    index.write_text("{}")
    with pytest.raises(ValueError, match="rerun forbidden"):
        guard(tmp_path / "absent", index)


def test_immutable_write(tmp_path):
    path = tmp_path / "record"
    write_new(path, {"original": True})
    with pytest.raises(FileExistsError):
        write_new(path, {"original": False})
    assert json.loads(path.read_bytes()) == {"original": True}


@pytest.mark.parametrize("returncode", [0, 1])
def test_capture_preserves_output_and_failure(tmp_path, monkeypatch, returncode):
    class Child:
        pid = 123

        def __init__(self, command, stdout, stderr, **kwargs):
            stdout.write(b"native output")
            stderr.write(b"diagnostic error")
            self.returncode = returncode

        def wait(self, timeout):
            return self.returncode

    monkeypatch.setattr("heldout_execution.subprocess.Popen", Child)
    capture = Capture(tmp_path)
    if returncode:
        with pytest.raises(ValueError, match="abnormal_engine_exit"):
            capture(["mock-only"])
    else:
        assert capture(["mock-only"]) == b"native output"
    assert (tmp_path / "process-0.stdout").read_bytes() == b"native output"
    assert (tmp_path / "process-0.stderr").read_bytes() == b"diagnostic error"
    assert json.loads((tmp_path / "process-0.json").read_bytes())["returncode"] == returncode
    assert len(capture.calls) == 1


def test_completed_evidence_is_read_only(monkeypatch):
    from heldout_execution import INDEX, verify

    if not INDEX.exists():
        pytest.skip("completed local evaluation required")

    def forbidden(*args, **kwargs):
        raise AssertionError("verification must not execute a subprocess")

    monkeypatch.setattr("heldout_execution.subprocess.Popen", forbidden)
    assert verify()["evaluations"] == 96
    with pytest.raises(ValueError, match="rerun forbidden"):
        guard()
