from sqlalchemy import DateTime, Uuid
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase

from app.db.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.model_registry import target_metadata


def test_mixins_use_postgresql_uuid_and_timezone_aware_timestamps() -> None:
    class IsolatedBase(DeclarativeBase):
        pass

    class SyntheticRecord(UUIDPrimaryKeyMixin, TimestampMixin, IsolatedBase):
        __tablename__ = "synthetic_test_record"

    columns = SyntheticRecord.__table__.columns
    assert isinstance(columns.id.type, Uuid)
    assert columns.id.type.compile(dialect=postgresql.dialect()) == "UUID"
    assert columns.id.primary_key
    for name in ("created_at", "updated_at"):
        assert isinstance(columns[name].type, DateTime)
        assert columns[name].type.timezone
        assert not columns[name].nullable


def test_foundation_has_no_application_tables() -> None:
    assert len(target_metadata.tables) == 0
