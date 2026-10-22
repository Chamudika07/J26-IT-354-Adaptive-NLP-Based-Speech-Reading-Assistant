"""Mocked PP1 persistence: no PostgreSQL, consent or production session writes."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth import dependencies
from app.modules.learner_modelling import pp1_saved as saved
from app.modules.learner_modelling.pp1_demo import APPROVED_DIGEST, FIXTURE


class MemoryDb:
    def __init__(self):
        self.rows = []

    def execute(self, query):
        if query.is_select:
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(
                    all=lambda: sorted(
                        [
                            r
                            for r in self.rows
                            if r.account_id == query.compile().params["account_id_1"]
                        ],
                        key=lambda r: r.sequence,
                    )
                )
            )
        values = query.compile().params
        existing = next(
            (
                r
                for r in self.rows
                if r.account_id == values["account_id"] and r.sequence == values["sequence"]
            ),
            None,
        )
        if existing:
            return SimpleNamespace(scalar_one_or_none=lambda: None)
        row = SimpleNamespace(**values)
        self.rows.append(row)
        return SimpleNamespace(scalar_one_or_none=lambda: row.id)


def test_save_readback_retries_and_progress():
    db = MemoryDb()
    account = uuid4()
    with patch.object(saved, "load_dataset", return_value=(FIXTURE.read_text(), APPROVED_DIGEST)):
        assert saved.read_saved(db, account).selectedSessionCount == 0
        receipt = saved.save_prefix(db, account, 2)
        assert receipt.createdSessionCount == 2 and len(db.rows) == 2
        first = saved.read_saved(db, account)
        assert saved.save_prefix(db, account, 2).createdSessionCount == 0
        assert saved.save_prefix(db, account, 3).createdSessionCount == 1
        last = saved.read_saved(db, account)
        assert last.selectedSessionCount == 3 and first.result.history != last.result.history
        assert saved.save_prefix(db, account, 1).savedSessionCount == 3
        db.rows[0].measurements["correct"] = 999
        with pytest.raises(ValueError):
            saved.read_saved(db, account)


def test_invalid_prefix_no_writes():
    db = MemoryDb()
    for count in (-1, 7, True):
        with pytest.raises(ValueError):
            saved.save_prefix(db, uuid4(), count)
    assert not db.rows


def test_http_commit_failure_never_confirms_save():
    app = FastAPI()
    app.include_router(saved.router)
    db = MagicMock()
    user = SimpleNamespace(user_id=uuid4(), roles=frozenset({"learner"}), status="active")
    app.dependency_overrides[dependencies.get_current_principal] = lambda: user
    app.dependency_overrides[dependencies.get_session] = lambda: db
    app.dependency_overrides[dependencies.get_settings] = lambda: SimpleNamespace(
        app_env="development"
    )
    with (
        TestClient(app, base_url="https://testserver") as client,
        patch.object(saved, "check_access"),
        patch.object(
            saved,
            "save_prefix",
            return_value=saved.SaveReceipt(savedSessionCount=1, createdSessionCount=1),
        ),
    ):
        assert client.post("/pp1-demo/saved-progress/1").status_code == 200
        db.commit.assert_called_once()
        db.commit.side_effect = RuntimeError("private failure")
        response = client.post("/pp1-demo/saved-progress/1")
        assert response.status_code == 503 and "private" not in response.text
        db.rollback.assert_called_once()
        assert (
            client.post("/pp1-demo/saved-progress/1", json={"words_correct": 20}).status_code == 422
        )


def test_access_fails_closed(monkeypatch):
    user = SimpleNamespace(user_id=uuid4(), roles=frozenset({"learner"}), status="active")
    settings = SimpleNamespace(app_env="development")
    request = SimpleNamespace(url=SimpleNamespace(scheme="https"), query_params={})
    db = MagicMock()
    db.execute.return_value.one.return_value = ("readbuddy_dev", "127.0.0.1", 5432)
    monkeypatch.setenv("READBUDDY_PP1_ENABLED", "1")
    monkeypatch.setenv("READBUDDY_PP1_ACCOUNT_IDS", str(user.user_id))
    with pytest.raises(Exception) as failure:
        saved.check_access(user, settings, db, request)
    assert failure.value.status_code == 403
    settings.app_env = "production"
    with pytest.raises(Exception) as failure:
        saved.check_access(user, settings, db, request)
    assert failure.value.status_code == 404


def test_storage_failure_and_fixture_change():
    with patch.object(saved, "load_dataset", side_effect=RuntimeError("unavailable")):
        with pytest.raises(RuntimeError):
            saved.read_saved(MemoryDb(), uuid4())
    raw = json.loads(FIXTURE.read_text())
    raw["records"][0]["activeMs"] = -1
    with patch.object(saved, "load_dataset", return_value=(json.dumps(raw), APPROVED_DIGEST)):
        with pytest.raises(ValueError):
            saved.save_prefix(MemoryDb(), uuid4(), 1)


def test_save_requires_authentication():
    from fastapi import HTTPException

    app = FastAPI()
    app.include_router(saved.router)

    def reject():
        raise HTTPException(401, "Authentication required")

    app.dependency_overrides[dependencies.get_current_principal] = reject
    app.dependency_overrides[dependencies.get_session] = lambda: MagicMock()
    app.dependency_overrides[dependencies.get_settings] = lambda: SimpleNamespace(
        app_env="development"
    )
    with (
        TestClient(app, base_url="https://testserver") as client,
        patch.object(saved, "save_prefix") as write,
    ):
        assert client.post("/pp1-demo/saved-progress/1").status_code == 401
        write.assert_not_called()


@pytest.mark.parametrize(
    "roles,status,allow",
    [
        (frozenset({"educator"}), "active", True),
        (frozenset({"learner"}), "disabled", True),
        (frozenset({"learner"}), "active", False),
    ],
)
def test_save_rejects_wrong_account_or_role(monkeypatch, roles, status, allow):
    user = SimpleNamespace(user_id=uuid4(), roles=roles, status=status)
    monkeypatch.setenv("READBUDDY_PP1_ENABLED", "1")
    monkeypatch.setenv("READBUDDY_PP1_ACCOUNT_IDS", str(user.user_id) if allow else str(uuid4()))
    db = MagicMock()
    with pytest.raises(Exception) as error:
        saved.check_access(
            user,
            SimpleNamespace(app_env="development"),
            db,
            SimpleNamespace(url=SimpleNamespace(scheme="https")),
        )
    assert error.value.status_code == 403
    db.execute.assert_not_called()


def test_saved_accounts_are_partitioned():
    db = MemoryDb()
    first, second = uuid4(), uuid4()
    with patch.object(saved, "load_dataset", return_value=(FIXTURE.read_text(), APPROVED_DIGEST)):
        saved.save_prefix(db, first, 3)
        assert saved.read_saved(db, second).selectedSessionCount == 0
        saved.save_prefix(db, second, 1)
        assert saved.read_saved(db, second).selectedSessionCount == 1
        assert saved.read_saved(db, first).selectedSessionCount == 3
