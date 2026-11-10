"""Bootstrap must remain explicit and development-only without leaking input."""

import warnings
from types import SimpleNamespace

import pytest

from app.modules.auth import bootstrap


def test_requires_confirmation_flag(monkeypatch):
    monkeypatch.setattr("sys.argv", ["bootstrap"])
    with pytest.raises(SystemExit) as exc:
        bootstrap.main()
    assert exc.value.code == 2


@pytest.mark.parametrize("environment", ["production", "staging", "test"])
def test_non_development_refuses_before_password_or_database(monkeypatch, environment, capsys):
    monkeypatch.setattr("sys.argv", ["bootstrap", "--confirm-local-development"])
    monkeypatch.setattr(bootstrap, "Settings", lambda: SimpleNamespace(app_env=environment))
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Must not prompt"))
    monkeypatch.setattr(bootstrap, "create_db_engine", lambda _: pytest.fail("Must not connect"))
    assert bootstrap.main() == 1
    assert "restricted" in capsys.readouterr().out


def test_password_mismatch_does_not_connect(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["bootstrap", "--confirm-local-development"])
    monkeypatch.setattr(bootstrap, "Settings", lambda: SimpleNamespace(app_env="development"))
    monkeypatch.setattr("builtins.input", lambda _: "synthetic_admin")
    values = iter(["Synthetic secret one", "Synthetic secret two"])
    monkeypatch.setattr(bootstrap.getpass, "getpass", lambda _: next(values))
    monkeypatch.setattr(bootstrap, "create_db_engine", lambda _: pytest.fail("Must not connect"))
    assert bootstrap.main() == 1
    output = capsys.readouterr().out
    assert "do not match" in output
    assert "Synthetic secret" not in output


def test_refuses_password_echo_fallback(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["bootstrap", "--confirm-local-development"])
    monkeypatch.setattr(bootstrap, "Settings", lambda: SimpleNamespace(app_env="development"))
    monkeypatch.setattr("builtins.input", lambda _: "synthetic_admin")

    def unsafe_prompt(_):
        warnings.warn("Cannot disable echo", bootstrap.getpass.GetPassWarning, stacklevel=1)
        pytest.fail("Must not read an echoed password")

    monkeypatch.setattr(bootstrap.getpass, "getpass", unsafe_prompt)
    assert bootstrap.main() == 1
    assert "hidden password input" in capsys.readouterr().out
