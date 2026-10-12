"""Integration test for 0006_learner_reading_sessions migration upgrade and downgrade."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


@pytest.mark.integration
def test_learner_reading_sessions_migration_lifecycle(postgres_engine) -> None:
    with postgres_engine.begin() as connection:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection

        # Ensure starting at parent revision 0005_auth_sessions
        command.downgrade(config, "0005_auth_sessions")
        before_tables = set(inspect(connection).get_table_names())
        assert "reading_sessions" not in before_tables
        assert "learner_reading_support_settings" not in before_tables

        # Run upgrade to head (0006_learner_reading_sessions)
        command.upgrade(config, "head")
        after_tables = set(inspect(connection).get_table_names())
        added_tables = after_tables - before_tables
        assert added_tables == {"reading_sessions", "learner_reading_support_settings"}

        # Verify synthetic learner profile and user can be referenced
        user_id, learner_id = uuid4(), uuid4()
        connection.execute(
            text("INSERT INTO users (id, login_handle) VALUES (:id, 'learner_modelling_tester')"),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO learner_profiles (id, display_name, created_by_user_id) "
                "VALUES (:id, 'Synthetic Learner', :user_id)"
            ),
            {"id": learner_id, "user_id": user_id},
        )

        # Insert reading support settings
        settings_id = uuid4()
        connection.execute(
            text(
                "INSERT INTO learner_reading_support_settings ("
                "id, learner_id, support_mode, default_difficulty_tier, enable_speech_cues, "
                "speech_rate_multiplier, enable_syllable_assistance, "
                "enable_phoneme_breakdown, enable_visual_pacing, enable_line_focus, "
                "simplification_level, pause_threshold_ms, manual_override_locked, "
                "updated_by_user_id, row_version, created_at, updated_at"
                ") VALUES ("
                ":id, :learner_id, 'adaptive', 'intermediate', true, 1.00, true, true, "
                "false, false, 1, 2500, false, :user_id, 1, now(), now()"
                ")"
            ),
            {"id": settings_id, "learner_id": learner_id, "user_id": user_id},
        )

        # Insert reading session
        session_id, client_session_id = uuid4(), uuid4()
        connection.execute(
            text(
                "INSERT INTO reading_sessions ("
                "id, learner_id, client_session_id, request_digest, "
                "session_start_time, session_end_time, task_type, difficulty_tier, "
                "support_mode, completion_status, words_attempted, words_correct, "
                "target_word_count, active_duration_ms, total_duration_ms, "
                "hesitation_count, row_version, created_at, updated_at"
                ") VALUES ("
                ":id, :learner_id, :client_session_id, :digest, now(), now(), "
                "'independent_reading', 'intermediate', 'adaptive', 'completed', "
                "50, 45, 50, 60000, 70000, 2, 1, now(), now()"
                ")"
            ),
            {
                "id": session_id,
                "learner_id": learner_id,
                "client_session_id": client_session_id,
                "digest": "a" * 64,
            },
        )

        # Verify idempotency constraint on (learner_id, client_session_id)
        with pytest.raises(Exception):  # noqa: B017
            connection.execute(
                text(
                    "INSERT INTO reading_sessions ("
                    "id, learner_id, client_session_id, request_digest, "
                    "session_start_time, session_end_time, task_type, difficulty_tier, "
                    "support_mode, completion_status, words_attempted, words_correct, "
                    "target_word_count, active_duration_ms, total_duration_ms, "
                    "row_version, created_at, updated_at"
                    ") VALUES ("
                    ":id, :learner_id, :client_session_id, :digest, now(), now(), "
                    "'independent_reading', 'intermediate', 'adaptive', 'completed', "
                    "50, 45, 50, 60000, 70000, 1, now(), now()"
                    ")"
                ),
                {
                    "id": uuid4(),
                    "learner_id": learner_id,
                    "client_session_id": client_session_id,
                    "digest": "b" * 64,
                },
            )

        # Clean up records before downgrade test
        connection.execute(text("DELETE FROM reading_sessions WHERE id = :id"), {"id": session_id})
        connection.execute(
            text("DELETE FROM learner_reading_support_settings WHERE id = :id"),
            {"id": settings_id},
        )
        connection.execute(text("DELETE FROM learner_profiles WHERE id = :id"), {"id": learner_id})
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

        # Test downgrade back to 0005_auth_sessions
        command.downgrade(config, "0005_auth_sessions")
        downgraded_tables = set(inspect(connection).get_table_names())
        assert "reading_sessions" not in downgraded_tables
        assert "learner_reading_support_settings" not in downgraded_tables

        # Restore head
        command.upgrade(config, "head")
        command.check(config)
