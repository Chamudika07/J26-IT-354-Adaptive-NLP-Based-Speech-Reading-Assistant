from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


@pytest.mark.integration
def test_sprint_one_to_auth_preserves_existing_rows(postgres_engine):
    with postgres_engine.begin() as connection:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0004_consent_evidence")
        before = set(inspect(connection).get_table_names())
        user_id, learner_id = uuid4(), uuid4()
        connection.execute(
            text("INSERT INTO users (id, login_handle) VALUES (:id, 'migration_synthetic')"),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO learner_profiles (id, display_name, created_by_user_id) "
                "VALUES (:id, 'Synthetic', :user_id)"
            ),
            {"id": learner_id, "user_id": user_id},
        )
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) - before == {
            "auth_sessions",
            "auth_refresh_tokens",
        }
        assert (
            connection.execute(
                text("SELECT login_handle FROM users WHERE id = :id"), {"id": user_id}
            ).scalar_one()
            == "migration_synthetic"
        )
        assert (
            connection.execute(
                text("SELECT created_by_user_id FROM learner_profiles WHERE id = :id"),
                {"id": learner_id},
            ).scalar_one()
            == user_id
        )
        command.check(config)
        connection.execute(text("DELETE FROM learner_profiles WHERE id = :id"), {"id": learner_id})
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
