"""Auth-owned persistence. Lock order for mutations: user, session, refresh token."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import AuthRefreshToken, AuthSession, Role, User, UserRole


def now(db: Session) -> datetime:
    return cast(datetime, db.execute(select(func.clock_timestamp())).scalar_one())


def user_by_handle(db: Session, handle: str) -> User | None:
    return db.scalar(select(User).where(User.login_handle == handle))


def user_by_id(db: Session, user_id: UUID, *, lock: bool = False) -> User | None:
    query = select(User).where(User.id == user_id).execution_options(populate_existing=True)
    return db.scalar(query.with_for_update() if lock else query)


def session_by_id(db: Session, session_id: UUID, *, lock: bool = False) -> AuthSession | None:
    query = select(AuthSession).where(AuthSession.id == session_id)
    query = query.execution_options(populate_existing=True)
    return db.scalar(query.with_for_update() if lock else query)


def credential_owner(db: Session, digest: bytes) -> tuple[UUID, UUID] | None:
    row = db.execute(
        select(AuthSession.user_id, AuthSession.id)
        .join(AuthRefreshToken, AuthRefreshToken.session_id == AuthSession.id)
        .where(AuthRefreshToken.token_digest == digest)
    ).one_or_none()
    return (row[0], row[1]) if row else None


def locked_credential(db: Session, digest: bytes) -> AuthRefreshToken | None:
    return db.scalar(
        select(AuthRefreshToken)
        .where(AuthRefreshToken.token_digest == digest)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def active_roles(db: Session, user_id: UUID) -> frozenset[str]:
    return frozenset(
        db.scalars(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id, UserRole.revoked_at.is_(None), Role.is_active.is_(True)
            )
        )
    )


def locked_open_sessions(db: Session, user_id: UUID) -> list[AuthSession]:
    return list(
        db.scalars(
            select(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .order_by(AuthSession.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


def protected_active_roles(db: Session, user_id: UUID) -> frozenset[str]:
    """Hold supporting role definitions and assignments until the caller commits.

    Called only after locking user/session. SHARE locks block revocation and role
    deactivation without serializing unrelated users with the same role.
    """
    return frozenset(
        db.scalars(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id, UserRole.revoked_at.is_(None), Role.is_active.is_(True)
            )
            .order_by(Role.id, UserRole.id)
            .with_for_update(read=True, of=(Role, UserRole))
        )
    )
