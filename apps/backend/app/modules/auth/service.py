"""Authentication transactions; all writes belong to auth, never learners."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import SecurityError, authentication_required
from app.modules.auth import repository as repo
from app.modules.auth.contracts import Principal
from app.modules.auth.models import AuthRefreshToken, AuthSession, User
from app.modules.auth.passwords import verify_password
from app.modules.auth.schemas import TokenResponse
from app.modules.auth.tokens import issue_access_token, validate_access_token

logger = logging.getLogger(__name__)


def _active(user: User | None) -> bool:
    return user is not None and user.status == "active" and user.deleted_at is None


def _live(session: AuthSession, now: datetime) -> bool:
    return session.revoked_at is None and session.expires_at > now and session.idle_expires_at > now


def _invalid_session() -> SecurityError:
    return SecurityError(401, "invalid_session", "Sign in again")


def refresh_digest(credential: str) -> bytes:
    return hashlib.sha256(credential.encode()).digest()


def _credential(db: Session, session: AuthSession, generation: int, now: datetime) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        AuthRefreshToken(
            session_id=session.id,
            token_digest=refresh_digest(raw),
            generation=generation,
            created_at=now,
            expires_at=session.idle_expires_at,
        )
    )
    return raw


def _response(session: AuthSession, raw: str, settings: Settings, now: datetime) -> TokenResponse:
    return TokenResponse(
        access_token=issue_access_token(session.user_id, session.id, settings, now),
        refresh_token=raw,
        expires_in=settings.access_token_ttl_seconds,
    )


def _revoke(session: AuthSession, now: datetime, reason: str) -> None:
    if session.revoked_at is None:
        session.updated_at = now
        session.revoked_at = now
        session.revocation_reason = reason


def login(db: Session, settings: Settings, handle: str, password: str) -> TokenResponse:
    user = repo.user_by_handle(db, handle.strip().lower())
    observed_hash = user.password_hash if user else None
    valid, replacement = verify_password(password, observed_hash)
    if not valid or not _active(user) or user is None:
        raise SecurityError(401, "invalid_credentials", "Invalid login credentials")
    # Re-read after taking the lock: credential/status may have changed during hashing.
    user = repo.user_by_id(db, user.id, lock=True)
    if not _active(user) or user is None or user.password_hash != observed_hash:
        raise SecurityError(401, "invalid_credentials", "Invalid login credentials")
    if replacement:
        user.password_hash = replacement
    now = repo.now(db)
    session = AuthSession(
        user_id=user.id,
        authenticated_at=now,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(seconds=settings.refresh_absolute_ttl_seconds),
        idle_expires_at=now + timedelta(seconds=settings.refresh_idle_ttl_seconds),
    )
    db.add(session)
    db.flush()
    raw = _credential(db, session, 0, now)
    response = _response(session, raw, settings, now)
    db.commit()
    return response


def refresh(db: Session, settings: Settings, credential: str) -> TokenResponse:
    digest = refresh_digest(credential)
    owner = repo.credential_owner(db, digest)
    if owner is None:
        raise _invalid_session()
    user = repo.user_by_id(db, owner[0], lock=True)
    session = repo.session_by_id(db, owner[1], lock=True)
    token = repo.locked_credential(db, digest)
    now = repo.now(db)
    if session is None or token is None or not _live(session, now):
        raise _invalid_session()
    if not _active(user):
        _revoke(session, now, "account_security")
        db.commit()
        raise _invalid_session()
    # Check replay even if this consumed generation itself has expired.
    if token.consumed_at is not None:
        _revoke(session, now, "replay")
        db.commit()  # MUST survive the error response and dependency rollback.
        logger.warning("auth_refresh_replay_session_revoked")
        raise _invalid_session()
    if token.expires_at <= now:
        raise _invalid_session()
    token.consumed_at = now
    db.flush()  # Release the partial unique current-token slot before inserting.
    session.idle_expires_at = min(
        session.expires_at, now + timedelta(seconds=settings.refresh_idle_ttl_seconds)
    )
    session.updated_at = now
    raw = _credential(db, session, token.generation + 1, now)
    response = _response(session, raw, settings, now)
    db.commit()
    return response


def logout(db: Session, credential: str) -> None:
    owner = repo.credential_owner(db, refresh_digest(credential))
    if owner is None:
        return
    repo.user_by_id(db, owner[0], lock=True)
    session = repo.session_by_id(db, owner[1], lock=True)
    if session is not None:
        _revoke(session, repo.now(db), "logout")
    db.commit()


def revoke_all_sessions(db: Session, user_id: UUID) -> None:
    """Internal lifecycle contract. Caller MUST commit with its account mutation.

    Acquire this user lock BEFORE mutating/flushing account status or credentials.
    It serializes account-wide revocation with login, refresh, and logout.
    """
    repo.user_by_id(db, user_id, lock=True)
    now = repo.now(db)
    for session in repo.locked_open_sessions(db, user_id):
        _revoke(session, now, "account_security")
    db.flush()


def resolve_principal(db: Session, settings: Settings, token: str) -> Principal:
    claims = validate_access_token(token, settings)
    session = repo.session_by_id(db, claims.session_id)
    if session is None or session.user_id != claims.user_id or not _live(session, repo.now(db)):
        raise authentication_required()
    user = repo.user_by_id(db, claims.user_id)
    if not _active(user) or user is None or user.login_handle is None:
        raise authentication_required()
    return Principal(
        user_id=user.id,
        login_handle=user.login_handle,
        roles=repo.active_roles(db, user.id),
        session_id=session.id,
        authenticated_at=session.authenticated_at,
        token_id=claims.token_id,
        issued_at=claims.issued_at,
        expires_at=claims.expires_at,
    )


def protect_principal_for_write(db: Session, principal: Principal) -> Principal:
    """Read-only cross-module contract for short, authorized write transactions.

    The input MUST come from current JWT principal resolution. Lock order: user,
    session, role definitions/assignments; caller then locks its own domain rows.
    Revalidate after waiting, and retain these locks until caller commit/rollback.
    No auth rows are written and this function never commits.
    """
    from dataclasses import replace

    user = repo.user_by_id(db, principal.user_id, lock=True)
    session = repo.session_by_id(db, principal.session_id, lock=True)
    roles = repo.protected_active_roles(db, principal.user_id)
    now = repo.now(db)
    if (
        not _active(user)
        or user is None
        or user.login_handle is None
        or session is None
        or session.user_id != principal.user_id
        or not _live(session, now)
        or principal.expires_at <= now
    ):
        raise authentication_required()
    return replace(principal, login_handle=user.login_handle, roles=roles)


def assert_protected_session_live(db: Session, principal: Principal) -> None:
    """Recheck deadlines after domain-lock waits, immediately before a mutation.

    Call only after protect_principal_for_write in the SAME transaction: those
    locks protect identity, session revocation, and roles, but cannot stop time.
    This read-only check acquires no new locks and never commits.
    """
    session = repo.session_by_id(db, principal.session_id)
    now = repo.now(db)
    if (
        session is None
        or session.user_id != principal.user_id
        or not _live(session, now)
        or principal.expires_at <= now
    ):
        raise authentication_required()
