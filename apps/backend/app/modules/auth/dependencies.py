"""Reusable authentication and global-role guards; no learner authorization here."""

from collections.abc import Callable
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import SecurityError, authentication_required
from app.db.session import get_session
from app.modules.auth.contracts import Principal
from app.modules.auth.schemas import RoleCode
from app.modules.auth.service import resolve_principal

_bearer = HTTPBearer(auto_error=False)
Database = Annotated[Session, Depends(get_session)]


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


RuntimeSettings = Annotated[Settings, Depends(get_settings)]


def get_current_principal(
    db: Database,
    settings: RuntimeSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise authentication_required()
    return resolve_principal(db, settings, credentials.credentials)


Authenticated = Annotated[Principal, Depends(get_current_principal)]


def check_role(principal: Principal, role: RoleCode) -> Principal:
    if principal.status != "active" or role not in principal.roles:
        raise SecurityError(403, "forbidden", "Access denied")
    return principal


def require_role(role: RoleCode) -> Callable[..., Principal]:
    def guard(principal: Authenticated) -> Principal:
        return check_role(principal, role)

    return guard


require_learner = require_role("learner")
require_guardian = require_role("guardian")
require_educator = require_role("educator")
require_administrator = require_role("administrator")
