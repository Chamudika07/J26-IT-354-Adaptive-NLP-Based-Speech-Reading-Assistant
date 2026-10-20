import hashlib
import os
import time
from pathlib import Path

import pytest

from app.modules.reading_materials.pdf.storage import GRACE_SECONDS, LocalStorage


def test_private_storage_and_grace_cleanup(tmp_path):
    store = LocalStorage(tmp_path / "private")
    data = b"%PDF-synthetic"
    with store.store(data) as obj:
        assert obj.digest == hashlib.sha256(data).hexdigest()
        assert obj.size == len(data)
        assert store.path(obj.key).stat().st_mode & 0o777 == 0o600
        with store.open(obj.key) as stream:
            assert stream.read() == data
        old = time.time() - GRACE_SECONDS - 10
        os.utime(store.path(obj.key), (old, old))
        assert store.cleanup(lambda key: False) == 0  # in-flight DB registration owns file lock
    assert store.cleanup(lambda key: True) == 0
    assert store.cleanup(lambda key: False) == 1
    with store.store(data) as fresh:
        pass
    assert store.cleanup(lambda key: False) == 0
    assert store.path(fresh.key).exists()


@pytest.mark.parametrize("key", ["../secret", "/tmp/secret", "a" * 33, "not-a-key", ""])
def test_invalid_keys(tmp_path, key):
    store = LocalStorage(tmp_path / "private")
    with pytest.raises(ValueError):
        store.open(key)


def test_symlink_and_root_rules(tmp_path):
    store = LocalStorage(tmp_path / "private")
    target = tmp_path / "synthetic"
    target.write_bytes(b"test")
    store.path("a" * 32).symlink_to(target)
    with pytest.raises(OSError):
        store.open("a" * 32)
    assert store.cleanup(lambda key: False) == 0
    with pytest.raises(ValueError):
        LocalStorage(None)
    with pytest.raises(ValueError):
        LocalStorage(Path("relative"))
    with pytest.raises(ValueError):
        LocalStorage(Path(__file__).resolve().parents[4])
    with pytest.raises(ValueError):
        store.cleanup(lambda key: False, grace=0)


def test_cleanup_database_unavailable_preserves_object(tmp_path):
    store = LocalStorage(tmp_path / "private")
    with store.store(b"synthetic") as obj:
        pass
    old = time.time() - GRACE_SECONDS - 10
    os.utime(store.path(obj.key), (old, old))

    def unavailable(key):
        raise RuntimeError("DB unavailable")

    with pytest.raises(RuntimeError):
        store.cleanup(unavailable)
    assert store.path(obj.key).exists()


def test_failed_database_registration_leaves_safe_orphan(tmp_path):
    store = LocalStorage(tmp_path / "private")
    with pytest.raises(RuntimeError):
        with store.store(b"synthetic") as obj:
            raise RuntimeError("uncertain commit")
    assert store.path(obj.key).exists()
    assert store.cleanup(lambda key: False) == 0
