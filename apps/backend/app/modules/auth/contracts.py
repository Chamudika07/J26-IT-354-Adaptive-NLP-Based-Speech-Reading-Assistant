"""Safe immutable service contract; no ORM models or credentials."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    login_handle: str
    roles: frozenset[str]
    session_id: UUID
    authenticated_at: datetime
    token_id: UUID
    issued_at: datetime
    expires_at: datetime
    status: Literal["active"] = "active"
