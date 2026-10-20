"""Single-head additive migration, downgrade/re-upgrade, and frozen prior revisions."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


@pytest.mark.integration
def test_0005_upgrade_preserves_data_and_downgrade_reupgrade(postgres_engine):
    with postgres_engine.begin() as connection:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0005_auth_sessions")
        tables = set(inspect(connection).get_table_names())
        identity = uuid4()
        connection.execute(
            text("INSERT INTO users (id, login_handle) VALUES (:id, :handle)"),
            {"id": identity, "handle": "migration_" + identity.hex},
        )
        command.upgrade(config, "head")
        added = {
            "reading_assessment_materials",
            "reading_materials",
            "reading_material_revisions",
            "reading_material_processing_runs",
            "reading_material_sentence_features",
            "reading_material_sources",
            "reading_material_extraction_runs",
            "reading_material_extraction_pages",
            "reading_assessment_sessions",
            "reading_assessment_results",
            "simplification_sessions",
            "simplification_vocabulary",
            "simplification_feedback",
        }
        assert set(inspect(connection).get_table_names()) - tables == added
        assert (
            connection.scalar(text("SELECT id FROM users WHERE id=:id"), {"id": identity})
            == identity
        )
        for table in added:
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0009_merge_heads"
        )
        command.check(config)
        command.downgrade(config, "0005_auth_sessions")
        assert set(inspect(connection).get_table_names()) == tables
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_proc WHERE proname IN "
                    "('reading_material_guard','reading_session_guard',"
                    "'reading_result_guard','reading_result_state_guard')"
                )
            )
            == 0
        )
        command.upgrade(config, "head")
        command.check(config)
        connection.execute(text("DELETE FROM users WHERE id=:id"), {"id": identity})
