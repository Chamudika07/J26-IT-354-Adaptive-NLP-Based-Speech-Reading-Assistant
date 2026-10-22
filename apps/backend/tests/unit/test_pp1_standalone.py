"""No database connections: standalone head, seed guards and idempotence."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.modules.learner_modelling import pp1_seed as seed


def test_standalone_head():
    root = Path(__file__).resolve().parents[2]
    scripts = ScriptDirectory.from_config(Config(str(root / "alembic.ini")))
    assert scripts.get_heads() == ["0008_c4_pp1_saved"]
    assert scripts.get_revision("0007_c4_pp1_demo").down_revision == "0006_learner_reading_sessions"


@pytest.mark.parametrize("database", ["readbuddy_dev", "readbuddy_component4_test", "other"])
def test_reject_other_databases(monkeypatch, database):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv(
        "READBUDDY_PP1_DATABASE_URL",
        f"postgresql+psycopg://fictional:unused@127.0.0.1:5432/{database}",
    )
    with pytest.raises(ValueError):
        seed.configured_url()


def test_requires_development_and_exact_url(monkeypatch):
    monkeypatch.setenv(
        "READBUDDY_PP1_DATABASE_URL",
        "postgresql+psycopg://fictional:unused@127.0.0.1:5432/readbuddy_component4_pp1_demo",
    )
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValueError):
        seed.configured_url()
    monkeypatch.setenv("APP_ENV", "development")
    assert seed.configured_url().get_secret_value()


@pytest.mark.parametrize("inserted", [None, uuid4()])
def test_seed_insert_or_exact_noop(inserted):
    row = SimpleNamespace(
        fixture_version=1,
        source_digest=seed.APPROVED_DIGEST,
        provenance=seed.PROVENANCE,
        source_payload=json.loads(seed.FIXTURE.read_text()),
    )
    db = MagicMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: inserted),
        SimpleNamespace(scalar_one=lambda: row),
    ]
    assert seed.seed_dataset(db) == (inserted is not None)
    assert db.execute.call_count == 2
    assert not db.commit.called


def test_conflicting_dataset_refused():
    row = SimpleNamespace(fixture_version=2)
    db = MagicMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: None),
        SimpleNamespace(scalar_one=lambda: row),
    ]
    with pytest.raises(ValueError):
        seed.seed_dataset(db)
    assert not db.commit.called


def test_corrupt_fixture_rejected_before_sql(monkeypatch):
    monkeypatch.setattr(seed, "dataset_digest", lambda raw: "0" * 64)
    db = MagicMock()
    with pytest.raises(ValueError):
        seed.seed_dataset(db)
    db.execute.assert_not_called()


def test_bootstrap_uses_hash_helper_and_only_three_inserts(monkeypatch):
    from tools import component4_pp1_bootstrap as tool

    monkeypatch.setattr(tool, "verify_target", lambda db: None)
    hashed = MagicMock(return_value="mock-hash-not-a-credential")
    monkeypatch.setattr(tool, "hash_password", hashed)
    db = MagicMock()

    def result(value):
        return SimpleNamespace(scalar_one=lambda: value)

    db.execute.side_effect = [
        result(0),
        result(uuid4()),
        result(0),
        result(0),
        result(None),
        result(None),
        result(None),
        result(1),
    ]
    assert tool.bootstrap(db, "fictional-unit-test-password")
    hashed.assert_called_once_with("fictional-unit-test-password")
    inserts = [
        str(call.args[0])
        for call in db.execute.call_args_list
        if str(call.args[0]).startswith("INSERT")
    ]
    assert len(inserts) == 3
    assert all(
        any(
            sql.startswith(f"INSERT INTO {table} ")
            for table in ("users", "user_roles", "learner_profiles")
        )
        for sql in inserts
    )
    assert not db.commit.called


def test_bootstrap_refuses_existing_accounts(monkeypatch):
    from tools import component4_pp1_bootstrap as tool

    monkeypatch.setattr(tool, "verify_target", lambda db: None)
    db = MagicMock()
    db.execute.return_value.scalar_one.return_value = 1
    with pytest.raises(ValueError):
        tool.bootstrap(db, "not-used")
    assert db.execute.call_count == 1
