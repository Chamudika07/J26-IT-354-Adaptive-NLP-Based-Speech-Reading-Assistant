from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import SecurityError, rate_limited
from app.modules.auth.contracts import Principal
from app.modules.auth.dependencies import check_role
from app.modules.auth.passwords import hash_password, verify_password
from app.modules.auth.schemas import LoginRequest, RefreshRequest, TokenResponse
from app.modules.auth.tokens import issue_access_token, validate_access_token

PASSWORD = "Synthetic accessible passphrase 42"


def test_password_salts_and_verification():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second
    assert first.startswith("$argon2id$")
    assert PASSWORD not in first
    assert verify_password(PASSWORD, first) == (True, None)
    assert verify_password("Wrong synthetic password", first) == (False, None)


@pytest.mark.parametrize(
    "encoded", [None, "plaintext", "$argon2id$bad", "$argon2id$v=19$m=1,t=1,p=1$bad$bad"]
)
def test_malformed_hash_fails_closed(encoded):
    assert verify_password(PASSWORD, encoded) == (False, None)


def test_outdated_hash_is_upgraded():
    old = PasswordHash((Argon2Hasher(memory_cost=19456, time_cost=2, parallelism=1),)).hash(
        PASSWORD
    )
    valid, upgraded = verify_password(PASSWORD, old)
    assert valid and upgraded and upgraded != old
    assert verify_password(PASSWORD, upgraded) == (True, None)


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_new_password_length_policy(password):
    with pytest.raises(ValueError):
        hash_password(password)


def test_password_preserves_spaces_and_unicode():
    password = "  Synthetic සතුට passphrase  "
    encoded = hash_password(password)
    assert verify_password(password, encoded)[0]
    assert not verify_password(password.strip(), encoded)[0]


def test_hashing_capacity_fails_without_waiting(monkeypatch):
    from unittest.mock import Mock

    from app.modules.auth import passwords

    capacity = Mock()
    capacity.acquire.return_value = False
    monkeypatch.setattr(passwords, "_capacity", capacity)
    for operation in (lambda: hash_password(PASSWORD), lambda: verify_password(PASSWORD, None)):
        with pytest.raises(SecurityError) as error:
            operation()
        assert error.value.status == 429
        assert error.value.headers == {"Retry-After": "1"}
    capacity.release.assert_not_called()


def test_access_token_roundtrip_is_minimal(settings):
    user, session = uuid4(), uuid4()
    token = issue_access_token(user, session, settings, datetime.now(UTC))
    claims = validate_access_token(token, settings)
    assert (claims.user_id, claims.session_id) == (user, session)
    assert claims.expires_at - claims.issued_at == timedelta(minutes=5)
    assert set(jwt.decode(token, options={"verify_signature": False})) == {
        "sub",
        "sid",
        "jti",
        "iss",
        "aud",
        "token_type",
        "iat",
        "exp",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "wrong"},
        {"aud": "wrong"},
        {"aud": ["adaptive-assistant-api"]},
        {"token_type": "refresh"},
        {"sub": "not-a-uuid"},
        {"sid": 5},
        {"jti": "bad"},
        {"iat": True},
        {"exp": "9999999999"},
        {"iat": 9999999999, "exp": 10000000000},
        {"exp": 1},
        {"exp": 9999999999},
        {"sub": None},
    ],
)
def test_invalid_claims(settings, change):
    token = issue_access_token(uuid4(), uuid4(), settings, datetime.now(UTC))
    payload = jwt.decode(token, options={"verify_signature": False})
    payload.update(change)
    invalid = jwt.encode(
        payload,
        settings.jwt_signing_key.get_secret_value(),
        algorithm="HS256",
        headers={"typ": "at+jwt"},
    )
    with pytest.raises(SecurityError) as error:
        validate_access_token(invalid, settings)
    assert error.value.code == "authentication_required"


@pytest.mark.parametrize("missing", ["sub", "sid", "jti", "iss", "aud", "token_type", "iat", "exp"])
def test_required_claims(settings, missing):
    token = issue_access_token(uuid4(), uuid4(), settings, datetime.now(UTC))
    payload = jwt.decode(token, options={"verify_signature": False})
    del payload[missing]
    invalid = jwt.encode(
        payload,
        settings.jwt_signing_key.get_secret_value(),
        algorithm="HS256",
        headers={"typ": "at+jwt"},
    )
    with pytest.raises(SecurityError):
        validate_access_token(invalid, settings)


@pytest.mark.parametrize(
    "algorithm,header,key",
    [
        ("HS384", {"typ": "at+jwt"}, None),
        ("none", {"typ": "at+jwt"}, ""),
        ("HS256", {"typ": "JWT"}, None),
        ("HS256", {"typ": "at+jwt", "jku": "https://untrusted.invalid/key"}, None),
        ("HS256", {"typ": "at+jwt"}, "different-synthetic-secret-of-sufficient-length"),
    ],
)
def test_algorithm_header_and_signature_rejection(settings, algorithm, header, key):
    payload = jwt.decode(
        issue_access_token(uuid4(), uuid4(), settings, datetime.now(UTC)),
        options={"verify_signature": False},
    )
    invalid = jwt.encode(
        payload,
        settings.jwt_signing_key.get_secret_value() if key is None else key,
        algorithm=algorithm,
        headers=header,
    )
    with pytest.raises(SecurityError):
        validate_access_token(invalid, settings)


def test_expiry_and_tampering(settings):
    old = issue_access_token(uuid4(), uuid4(), settings, datetime.now(UTC) - timedelta(minutes=6))
    current = issue_access_token(uuid4(), uuid4(), settings, datetime.now(UTC))
    parts = current.split(".")
    parts[1] = parts[1][:-3] + "AAA"
    for token in (old, ".".join(parts), "broken", "x" * 4097):
        with pytest.raises(SecurityError):
            validate_access_token(token, settings)


@pytest.mark.parametrize("role", ["learner", "guardian", "educator", "administrator"])
def test_role_guard_and_immutable_principal(role):
    now = datetime.now(UTC)
    principal = Principal(uuid4(), "synthetic", frozenset({role}), uuid4(), now, uuid4(), now, now)
    assert check_role(principal, role) is principal
    with pytest.raises(FrozenInstanceError):
        principal.login_handle = "changed"
    other = "educator" if role != "educator" else "guardian"
    with pytest.raises(SecurityError) as error:
        check_role(principal, other)
    assert error.value.code == "forbidden"


def test_credentials_not_in_representations():
    assert PASSWORD not in repr(LoginRequest(login_handle="  SAMPLE  ", password=PASSWORD))
    assert LoginRequest(login_handle="  SAMPLE  ", password=PASSWORD).login_handle == "sample"
    assert "synthetic-credential" not in repr(RefreshRequest(refresh_token="synthetic-credential"))
    assert "synthetic-credential" not in repr(
        TokenResponse(
            access_token="synthetic-credential",
            refresh_token="synthetic-credential",
            expires_in=300,
        )
    )
    assert rate_limited(0).headers == {"Retry-After": "1"}


@pytest.mark.parametrize(
    "values",
    [
        {"jwt_signing_key": "short"},
        {"jwt_signing_key": "replace_with_random_signing_secret"},
        {"jwt_issuer": " "},
        {"jwt_audience": " api "},
        {"access_token_ttl_seconds": 301},
        {"refresh_idle_ttl_seconds": 86401},
        {"refresh_absolute_ttl_seconds": 604801},
        {"refresh_absolute_ttl_seconds": 300},
        {"jwt_clock_tolerance_seconds": 31},
    ],
)
def test_security_settings_validation(settings, values):
    source = settings.model_dump()
    source.update(values)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **source)
