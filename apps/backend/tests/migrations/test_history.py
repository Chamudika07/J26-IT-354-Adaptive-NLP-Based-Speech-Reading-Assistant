from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migration_history_has_one_root_and_one_head() -> None:
    backend = Path(__file__).resolve().parents[2]
    history = ScriptDirectory.from_config(Config(str(backend / "alembic.ini")))
    assert len(history.get_heads()) == 1
    assert len(history.get_bases()) == 1
