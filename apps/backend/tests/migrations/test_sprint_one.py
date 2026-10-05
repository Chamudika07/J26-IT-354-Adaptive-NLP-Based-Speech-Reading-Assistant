"""Destructive migration tests: the guarded fixture requires a disposable database."""

import hashlib
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, UniqueConstraint, inspect, text

from app.db.model_registry import target_metadata


def test_original_baseline_is_unchanged() -> None:
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0001_foundation.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "74c741cb33817e5b4757c3887689ae3c09f3eccec6d44c3619683b507948a6f7"
    )


@pytest.mark.integration
@pytest.mark.parametrize("start", ["base", "0001_foundation"])
def test_migration_upgrade_paths_and_role_only_seed(postgres_engine, start):
    with postgres_engine.begin() as connection:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        if start != "base":
            command.upgrade(config, start)
        assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) == set(target_metadata.tables) | {
            "alembic_version"
        }
        for name in target_metadata.tables:
            # Names are exclusively from the fixed, application-owned metadata registry.
            count = connection.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one()
            assert count == (4 if name == "roles" else 0)
        assert set(connection.execute(text("SELECT code FROM roles")).scalars()) == {
            "guardian",
            "educator",
            "learner",
            "administrator",
        }
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0005_auth_sessions"
        )
        command.check(config)


@pytest.mark.integration
def test_schema_drift_constraints_indexes_and_no_native_enums(postgres_engine):
    with postgres_engine.begin() as connection:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.check(config)
        inspector = inspect(connection)
        preparer = connection.dialect.identifier_preparer
        for table in target_metadata.tables.values():
            assert {item["name"] for item in inspector.get_check_constraints(table.name)} == {
                preparer.format_constraint(item).strip('"')
                for item in table.constraints
                if isinstance(item, CheckConstraint)
            }
            assert {item["name"] for item in inspector.get_unique_constraints(table.name)} == {
                preparer.format_constraint(item).strip('"')
                for item in table.constraints
                if isinstance(item, UniqueConstraint)
            }
            actual_indexes = {
                item["name"]
                for item in inspector.get_indexes(table.name)
                if not item.get("duplicates_constraint")
            }
            assert actual_indexes == {
                preparer.format_index(index).strip('"') for index in table.indexes
            }
            actual_fks = {
                tuple(item["constrained_columns"]): item
                for item in inspector.get_foreign_keys(table.name)
            }
            for fk in table.foreign_key_constraints:
                reflected = actual_fks[tuple(column.name for column in fk.columns)]
                assert reflected["options"]["ondelete"] == fk.ondelete
            for column in inspector.get_columns(table.name):
                if column["name"] in {"age_band", "grade_level"}:
                    assert str(column["type"]) == "SMALLINT"
                if column["name"] == "id":
                    assert str(column["type"]) == "UUID"
        assert inspector.get_enums(schema="public") == []
        assert (
            connection.execute(
                text("""
            SELECT count(*) FROM pg_trigger t JOIN pg_class c ON t.tgrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE n.nspname = 'public' AND NOT t.tgisinternal
        """)
            ).scalar_one()
            == 10
        )
