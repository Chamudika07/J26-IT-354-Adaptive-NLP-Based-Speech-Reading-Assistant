"""Argon2id only. Call from synchronous workers, never the event loop."""

from functools import lru_cache
from secrets import token_urlsafe
from threading import BoundedSemaphore

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.exceptions import rate_limited

_hasher = PasswordHash((Argon2Hasher(memory_cost=65536, time_cost=3, parallelism=1),))
# Bound memory use per process. This is capacity protection, not a brute-force limiter.
_capacity = BoundedSemaphore(2)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash(token_urlsafe(32))


def hash_password(password: str) -> str:
    """Length policy for new credentials; provisioning/recovery is out of scope."""
    if not 15 <= len(password) <= 128:
        raise ValueError("Passwords must contain 15 to 128 characters")
    if not _capacity.acquire(blocking=False):
        raise rate_limited(1)
    try:
        return _hasher.hash(password)
    finally:
        _capacity.release()


def verify_password(password: str, encoded: str | None) -> tuple[bool, str | None]:
    """Unknown and malformed hashes perform a dummy verification and fail closed."""
    if not _capacity.acquire(blocking=False):
        raise rate_limited(1)
    try:
        if encoded is None or not encoded.startswith("$argon2id$"):
            _hasher.verify(password, _dummy_hash())
            return False, None
        try:
            return _hasher.verify_and_update(password, encoded)
        except (UnknownHashError, ValueError):
            _hasher.verify(password, _dummy_hash())
            return False, None
    finally:
        _capacity.release()
