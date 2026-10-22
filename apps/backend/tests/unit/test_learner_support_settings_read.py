"""Private settings foundation tests: synthetic ORM values and mocked Session only."""

import ast
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session

from app.modules.learner_modelling import repository
from app.modules.learner_modelling import support_settings as settings
from app.modules.learner_modelling.models import LearnerReadingSupportSettings
from app.modules.learner_modelling.router import router
from app.modules.learner_modelling.schemas import SupportSettingsRead

LEARNER = UUID("77777777-7777-4777-8777-777777777777")


def _values() -> dict[str, object]:
    return {
        "row_version": 2,
        "support_mode": "adaptive",
        "default_difficulty_tier": "intermediate",
        "enable_speech_cues": True,
        "speech_rate_multiplier": Decimal("0.80"),
        "enable_syllable_assistance": False,
        "enable_phoneme_breakdown": True,
        "enable_visual_pacing": True,
        "visual_pacing_rate_wpm": 70,
        "enable_line_focus": True,
        "simplification_level": 2,
        "pause_threshold_ms": 3000,
        "manual_override_locked": True,
    }


def _row(**changes: object) -> LearnerReadingSupportSettings:
    values = _values()
    values.update(changes)
    return LearnerReadingSupportSettings(
        **values, learner_id=LEARNER, id=UUID(int=100), updated_by_user_id=UUID(int=200)
    )


def _db(row: LearnerReadingSupportSettings | None) -> MagicMock:
    db = MagicMock(spec=Session)
    db.scalars.return_value.one_or_none.return_value = row
    return db


def _no_writes(db: MagicMock) -> None:
    for name in (
        "add",
        "add_all",
        "flush",
        "commit",
        "rollback",
        "delete",
        "merge",
        "begin",
        "begin_nested",
    ):
        getattr(db, name).assert_not_called()
    db.execute.assert_not_called()
    db.connection.assert_not_called()


def test_valid_settings_are_minimized_validated_frozen_and_detached_from_orm() -> None:
    row = _row()
    db = _db(row)
    result = settings._read_support_settings(db, LEARNER)
    assert type(result) is SupportSettingsRead
    assert result.model_dump() == _values()
    for forbidden in ("id", "learner_id", "updated_by_user_id", "created_at", "updated_at"):
        assert forbidden not in result.model_dump()
    row.manual_override_locked = False
    assert result.manual_override_locked is True
    with pytest.raises(ValidationError):
        result.manual_override_locked = False
    _no_writes(db)


def test_missing_row_is_none_and_never_creates_defaults() -> None:
    db = _db(None)
    assert settings._read_support_settings(db, LEARNER) is None
    db.scalars.return_value.one_or_none.assert_called_once_with()
    _no_writes(db)


@pytest.mark.parametrize(
    "field,value",
    [
        ("row_version", 0),
        ("row_version", True),
        ("support_mode", "unknown"),
        ("default_difficulty_tier", "expert"),
        ("enable_speech_cues", "true"),
        ("enable_line_focus", 1),
        ("manual_override_locked", None),
        ("manual_override_locked", 0),
        ("speech_rate_multiplier", 0.8),
        ("speech_rate_multiplier", Decimal("NaN")),
        ("speech_rate_multiplier", Decimal("Infinity")),
        ("speech_rate_multiplier", Decimal("0.49")),
        ("speech_rate_multiplier", Decimal("2.01")),
        ("speech_rate_multiplier", Decimal("1.111")),
        ("visual_pacing_rate_wpm", 19),
        ("visual_pacing_rate_wpm", 301),
        ("visual_pacing_rate_wpm", True),
        ("simplification_level", 0),
        ("simplification_level", 6),
        ("pause_threshold_ms", 999),
        ("pause_threshold_ms", 10001),
        ("enable_visual_pacing", None),
    ],
)
def test_invalid_stored_settings_fail_closed_without_partial_or_default_values(
    field: str,
    value: object,
) -> None:
    db = _db(_row(**{field: value}))
    with pytest.raises(settings.InvalidSupportSettings) as rejected:
        settings._read_support_settings(db, LEARNER)
    assert str(rejected.value) == "Stored support settings are invalid."
    assert str(LEARNER) not in str(rejected.value)
    _no_writes(db)


@pytest.mark.parametrize("mode", ["adaptive", "manual_override", "baseline_fixed"])
@pytest.mark.parametrize("locked", [True, False])
def test_modes_and_global_lock_are_preserved_without_reinterpreting_precedence(
    mode: str, locked: bool
) -> None:
    db = _db(_row(support_mode=mode, manual_override_locked=locked))
    result = settings._read_support_settings(db, LEARNER)
    assert result is not None
    assert result.support_mode == mode
    assert result.manual_override_locked is locked
    _no_writes(db)


@pytest.mark.parametrize("value", [None, 20, 300])
def test_nullable_pacing_and_existing_bounds_do_not_acquire_new_cross_field_rules(
    value: int | None,
) -> None:
    db = _db(_row(enable_visual_pacing=True, visual_pacing_rate_wpm=value))
    result = settings._read_support_settings(db, LEARNER)
    assert result is not None and result.visual_pacing_rate_wpm == value
    _no_writes(db)


def test_wrong_learner_row_is_invalid_and_not_disclosed() -> None:
    row = _row()
    row.learner_id = UUID(int=300)
    db = _db(row)
    with pytest.raises(settings.InvalidSupportSettings):
        settings._read_support_settings(db, LEARNER)
    _no_writes(db)


@pytest.mark.parametrize(
    "error,expected",
    [
        (
            RuntimeError("PRIVATE SQL credentials learner details"),
            settings.SupportSettingsUnavailable,
        ),
        (MultipleResultsFound("PRIVATE duplicate rows"), settings.InvalidSupportSettings),
    ],
)
def test_repository_failure_never_becomes_missing_or_exposes_details(
    error: Exception,
    expected: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    db = _db(None)
    db.scalars.side_effect = error
    with pytest.raises(expected) as caught:
        settings._read_support_settings(db, LEARNER)
    assert "PRIVATE" not in str(caught.value)
    assert caught.value.__suppress_context__ is True
    assert caplog.text == ""
    _no_writes(db)


def test_repository_scopes_exact_learner_and_suppresses_autoflush() -> None:
    row = _row()
    db = _db(row)
    assert repository.get_support_settings(db, LEARNER) is row
    statement = db.scalars.call_args.args[0]
    sql = str(
        statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert f"learner_reading_support_settings.learner_id = '{LEARNER}'" in sql
    assert "FOR UPDATE" not in sql
    assert "JOIN" not in sql
    assert "LIMIT" not in sql  # Multiple rows must raise, never silently select one.
    db.no_autoflush.__enter__.assert_called_once_with()
    db.no_autoflush.__exit__.assert_called_once()
    calls = [str(call) for call in db.mock_calls]
    assert next(i for i, value in enumerate(calls) if "__enter__" in value) < next(
        i for i, value in enumerate(calls) if value.startswith("call.scalars(")
    )
    _no_writes(db)


@pytest.mark.parametrize(
    "extra", ["learner_id", "updated_by_user_id", "consent", "access_path", "secret"]
)
def test_projection_rejects_extra_fields(extra: str) -> None:
    with pytest.raises(ValidationError):
        SupportSettingsRead.model_validate({**_values(), extra: "PRIVATE"})


def test_projection_has_no_defaults_and_rejects_orm_object_input() -> None:
    for name in SupportSettingsRead.model_fields:
        values = _values()
        del values[name]
        with pytest.raises(ValidationError):
            SupportSettingsRead.model_validate(values)
    with pytest.raises(ValidationError):
        SupportSettingsRead.model_validate(_row())


def test_invalid_request_identity_stops_before_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    read = MagicMock()
    monkeypatch.setattr(repository, "get_support_settings", read)
    with pytest.raises(settings.InvalidSupportSettings):
        settings._read_support_settings(MagicMock(spec=Session), "not-a-UUID")  # type: ignore[arg-type]
    read.assert_not_called()


def test_no_production_importers_router_registration_or_cross_module_dependencies() -> None:
    path = Path(settings.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        value.startswith(("fastapi", "app.modules.auth", "app.modules.learners", "app.db"))
        for value in imports
    )
    assert all(route.endpoint.__module__ != settings.__name__ for route in router.routes)
    for other in path.parents[2].rglob("*.py"):
        # The private pure composition layer imports only the validation error;
        # its own boundary tests prohibit production callers or I/O dependencies.
        if other not in (path, path.with_name("recommendation_composition.py")):
            assert "import support_settings" not in other.read_text(encoding="utf-8")
            assert "from app.modules.learner_modelling.support_settings" not in other.read_text(
                encoding="utf-8"
            )
