"""Private local objects with advisory locking shared by ingestion and orphan cleanup."""

import fcntl
import hashlib
import os
import re
import stat
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from app.modules.reading_materials.pdf.contracts import MAX_BYTES

KEY = re.compile(r"^[0-9a-f]{32}$")
GRACE_SECONDS = 86400


@dataclass(frozen=True, repr=False)
class StoredObject:
    key: str
    digest: str
    size: int


class PrivateStorage(Protocol):
    def open(self, key: str) -> BinaryIO: ...


class LocalStorage:
    backend = "local-v1"

    def __init__(self, root: Path | None):
        if root is None or not root.is_absolute() or root.is_symlink():
            raise ValueError("Private storage is not configured")
        repository = next(
            (p for p in Path(__file__).resolve().parents if (p / ".git").exists()),
            Path(__file__).resolve().parents[4],
        )
        root = root.resolve()
        if root == repository or repository in root.parents:
            raise ValueError("Storage must be outside the repository")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("Storage must be private to the runtime user")
        self.root = root

    def path(self, key: str) -> Path:
        if not KEY.fullmatch(key):
            raise ValueError("Invalid object identifier")
        return self.root / key

    @contextmanager
    def store(self, data: bytes) -> Iterator[StoredObject]:
        if not 0 < len(data) <= MAX_BYTES:
            raise ValueError("Invalid object size")
        key = uuid4().hex
        fd = os.open(self.path(key), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            # Keep the object locked through the caller's database commit/rollback.
            # Never delete on uncertain commit outcome.
            yield StoredObject(key, hashlib.sha256(data).hexdigest(), len(data))

    def open(self, key: str) -> BinaryIO:
        fd = os.open(self.path(key), os.O_RDONLY | os.O_NOFOLLOW)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise ValueError("Invalid object")
        return os.fdopen(fd, "rb")

    def cleanup(self, referenced: Callable[[str], bool], *, grace: int = GRACE_SECONDS) -> int:
        if grace < GRACE_SECONDS:
            raise ValueError("Unsafe grace period")
        removed = 0
        for path in self.root.iterdir():
            if not KEY.fullmatch(path.name) or path.is_symlink():
                continue
            try:
                with self.open(path.name) as stream:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        continue
                    info = os.fstat(stream.fileno())
                    if time.time() - info.st_mtime < grace or referenced(path.name):
                        continue
                    if path.stat().st_ino == info.st_ino:
                        path.unlink()
                        removed += 1
            except FileNotFoundError:
                continue
        return removed
