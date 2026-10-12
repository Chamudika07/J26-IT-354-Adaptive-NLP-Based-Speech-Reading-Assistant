from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_history_has_one_root_and_one_head() -> None:
    backend = Path(__file__).resolve().parents[2]
    history = ScriptDirectory.from_config(Config(str(backend / "alembic.ini")))
    assert len(history.get_heads()) == 1
    assert len(history.get_bases()) == 1
    assert history.get_current_head() == "0006_learner_reading_sessions"


def test_historical_migration_test_targets_intended_revision() -> None:
    """Historical migration test must target 0005_auth_sessions specifically."""
    test_file = Path(__file__).resolve().parent / "test_auth_sessions.py"
    content = test_file.read_text(encoding="utf-8")
    assert 'command.upgrade(config, "0005_auth_sessions")' in content
