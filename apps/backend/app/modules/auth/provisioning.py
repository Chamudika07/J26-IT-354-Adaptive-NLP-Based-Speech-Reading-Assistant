"""Auth-owned account provisioning and public management authorization contracts."""

from typing import NoReturn
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth import repository as repo
from app.modules.auth.contracts import Principal
from app.modules.auth.models import Role, User, UserRole
from app.modules.auth.passwords import hash_password
from app.modules.auth.provisioning_schemas import AccountCreate, AccountCreated
from app.modules.auth.service import assert_protected_session_live, protect_principal_for_write


def require_administrator(principal: Principal) -> None:
    if "administrator" not in principal.roles:
        raise SecurityError(403, "forbidden", "Access denied")


def protect_administrator(
    db: Session, principal: Principal, target_user_id: UUID | None = None
) -> Principal:
    """No writes/commit. Lock users in UUID order, then actor session and roles.

    Target identity locks must precede domain locks. This avoids reciprocal
    administrator/educator assignment deadlocks. Revalidate after lock waits.
    """
    require_administrator(principal)
    for identity in sorted({principal.user_id, target_user_id or principal.user_id}):
        repo.user_by_id(db, identity, lock=True)
    protected = protect_principal_for_write(db, principal)
    require_administrator(protected)
    return protected


def assert_educator(db: Session, identity: UUID) -> None:
    """Caller holds target user lock from protect_administrator; no writes/commit."""
    user = repo.user_by_id(db, identity)
    if (
        user is None
        or user.status != "active"
        or user.deleted_at is not None
        or "educator" not in repo.protected_active_roles(db, identity)
    ):
        raise SecurityError(422, "invalid_educator", "An active educator is required")


def insert_account(
    db: Session, payload: AccountCreate, encoded: str, role_code: str, grantor: UUID | None
) -> AccountCreated:
    """Auth-internal persistence; caller owns commit/rollback."""
    role = db.scalar(select(Role).where(Role.code == role_code).with_for_update(read=True))
    if role is None or not role.is_active:
        raise SecurityError(409, "role_unavailable", "Required role is unavailable")
    user = User(login_handle=payload.login_handle, password_hash=encoded, status="active")
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id, granted_by_user_id=grantor or user.id))
    db.flush()
    return AccountCreated(
        user_id=user.id, login_handle=payload.login_handle, status="active", roles=[role_code]
    )


def account_conflict(exc: IntegrityError) -> NoReturn:
    if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "uq_users_login_handle":
        raise SecurityError(409, "handle_unavailable", "Login handle is unavailable") from None
    raise exc


def create_educator(db: Session, principal: Principal, payload: AccountCreate) -> AccountCreated:
    require_administrator(principal)
    encoded = hash_password(payload.password.get_secret_value())
    try:
        protected = protect_administrator(db, principal)
        result = insert_account(db, payload, encoded, "educator", protected.user_id)
        assert_protected_session_live(db, protected)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        account_conflict(exc)
    except Exception:
        db.rollback()
        raise


def bootstrap_administrator(db: Session, payload: AccountCreate) -> AccountCreated:
    """CLI-only first administrator. Never reset, elevate, or replace an account.

    A historical administrator assignment also blocks bootstrap. The first grant
    is explicitly self-attributed. Concurrent bootstrap attempts serialize.
    """
    encoded = hash_password(payload.password.get_secret_value())
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(354, 22081766)"))
        existing = db.scalar(
            select(UserRole.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.code == "administrator")
            .limit(1)
        )
        if existing is not None:
            raise SecurityError(409, "administrator_exists", "Administrator already provisioned")
        result = insert_account(db, payload, encoded, "administrator", None)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        account_conflict(exc)
    except Exception:
        db.rollback()
        raise
