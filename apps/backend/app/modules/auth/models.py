"""Account identities and historical role grants. No authentication flow lives here."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint(
            "login_handle IS NULL OR login_handle ~ '^[a-z0-9][a-z0-9._-]{2,63}$'",
            name="handle_format",
        ),
        CheckConstraint(
            "email IS NULL OR (length(btrim(email)) > 0 AND email = lower(btrim(email)))",
            name="email_normalized",
        ),
        CheckConstraint(
            "email_verified_at IS NULL OR email IS NOT NULL", name="email_verification"
        ),
        CheckConstraint("status IN ('active', 'disabled', 'anonymized')", name="status_values"),
        CheckConstraint(
            "status = 'anonymized' OR login_handle IS NOT NULL", name="handle_required"
        ),
        CheckConstraint(
            "status <> 'active' OR (password_hash IS NOT NULL AND deleted_at IS NULL)",
            name="active_credentials",
        ),
        CheckConstraint(
            "status <> 'anonymized' OR (deleted_at IS NOT NULL AND login_handle IS NULL "
            "AND email IS NULL AND email_verified_at IS NULL AND password_hash IS NULL)",
            name="anonymized_fields",
        ),
        CheckConstraint(
            "password_hash IS NULL OR length(btrim(password_hash)) > 0", name="password_nonblank"
        ),
        Index("ix_users_deleted_at", "deleted_at", postgresql_where=text("deleted_at IS NOT NULL")),
    )

    login_handle: Mapped[str | None] = mapped_column(String(64), unique=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="disabled")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Role(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint(
            "code IN ('guardian', 'educator', 'learner', 'administrator')", name="code_values"
        ),
        CheckConstraint("length(btrim(description)) > 0", name="description_nonblank"),
    )

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class UserRole(UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        CheckConstraint("row_version > 0", name="row_version_positive"),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoked_by_user_id IS NULL)", name="revocation_pair"
        ),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="revocation_order"),
        Index(
            "uq_user_roles_open",
            "user_id",
            "role_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_user_roles_history", "user_id", "role_id", text("created_at DESC")),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), index=True
    )
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
