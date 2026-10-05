"""Strict HS256 access tokens; no roles or learner grants are token authority."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt

from app.core.config import Settings
from app.core.exceptions import authentication_required


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    session_id: UUID
    token_id: UUID
    issued_at: datetime
    expires_at: datetime


def issue_access_token(user_id: UUID, session_id: UUID, settings: Settings, now: datetime) -> str:
    issued = int(now.timestamp())
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "jti": str(uuid4()),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "token_type": "access",
            "iat": issued,
            "exp": issued + settings.access_token_ttl_seconds,
        },
        settings.jwt_signing_key.get_secret_value(),
        algorithm="HS256",
        headers={"typ": "at+jwt"},
    )


def validate_access_token(token: str, settings: Settings) -> AccessClaims:
    try:
        if len(token) > 4096:
            raise ValueError("Oversize token")
        header = jwt.get_unverified_header(token)
        if header.get("typ") != "at+jwt" or set(header) - {"typ", "alg"}:
            raise ValueError("Unexpected header")
        claims = jwt.decode(
            token,
            settings.jwt_signing_key.get_secret_value(),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            leeway=settings.jwt_clock_tolerance_seconds,
            options={
                "require": ["sub", "sid", "jti", "iss", "aud", "token_type", "iat", "exp"],
                "strict_aud": True,
            },
        )
        if claims["token_type"] != "access":
            raise ValueError("Wrong token type")
        if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
            raise ValueError("Invalid timestamps")
        if not 0 < claims["exp"] - claims["iat"] <= settings.access_token_ttl_seconds:
            raise ValueError("Invalid lifetime")
        return AccessClaims(
            user_id=UUID(claims["sub"]),
            session_id=UUID(claims["sid"]),
            token_id=UUID(claims["jti"]),
            issued_at=datetime.fromtimestamp(claims["iat"], UTC),
            expires_at=datetime.fromtimestamp(claims["exp"], UTC),
        )
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise authentication_required() from exc
