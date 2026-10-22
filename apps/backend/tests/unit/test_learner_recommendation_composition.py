"""Pure composition coverage reusing existing synthetic settings/evidence fixtures."""

import ast
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from test_learner_adaptation_mapping import _evidence, _key, _observation
from test_learner_support_settings_read import LEARNER, _db, _no_writes, _row, _values

from app.modules.learner_modelling import recommendation_composition as composition
from app.modules.learner_modelling import support_settings
from app.modules.learner_modelling.adaptation import (
    AdaptationThresholds,
    SupportPreferences,
    recommend_adaptation,
)
from app.modules.learner_modelling.adaptation_mapping import (
    AdaptationMappingError,
    map_longitudinal_partition_to_adaptation_input,
)
from app.modules.learner_modelling.dashboard_projections import (
    project_educator_analytics,
    project_guardian_summary,
    project_learner_progress,
)
from app.modules.learner_modelling.router import router
from app.modules.learner_modelling.schemas import SupportSettingsRead


def _settings(**changes: object) -> SupportSettingsRead:
    return SupportSettingsRead.model_validate(
        {**_values(), "manual_override_locked": False, **changes}
    )


def test_mapping_copies_every_preference_without_defaults_or_mutation() -> None:
    settings = _settings()
    before = settings.model_dump()
    preferences = composition._map_support_preferences(settings)
    assert type(preferences) is SupportPreferences
    expected = {name: before[name] for name in asdict(preferences)}
    expected["speech_rate_multiplier"] = 0.8
    assert asdict(preferences) == expected
    assert settings.model_dump() == before
    assert settings.row_version == 2
    assert settings.default_difficulty_tier == "intermediate"


@pytest.mark.parametrize("rate", [Decimal("0.50"), Decimal("2.00")])
def test_decimal_rates_and_nullable_pacing_are_preserved_in_existing_preference_types(
    rate: Decimal,
) -> None:
    preferences = composition._map_support_preferences(
        _settings(speech_rate_multiplier=rate, visual_pacing_rate_wpm=None)
    )
    assert preferences is not None
    assert preferences.speech_rate_multiplier == float(rate)
    assert preferences.visual_pacing_rate_wpm is None


def test_absent_settings_short_circuit_without_inventing_unlocked_preferences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapper = MagicMock(side_effect=AssertionError("Must not map absent settings"))
    engine = MagicMock(side_effect=AssertionError("Must not recommend absent settings"))
    monkeypatch.setattr(composition, "map_longitudinal_partition_to_adaptation_input", mapper)
    monkeypatch.setattr(composition, "recommend_adaptation", engine)
    assert composition._map_support_preferences(None) is None
    assert composition._compose_recommendation(None, _evidence(), _key()) is None
    mapper.assert_not_called()
    engine.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [
        _settings().model_copy(update={"row_version": 0}),
        _settings().model_copy(update={"manual_override_locked": "PRIVATE"}),
        _settings().model_copy(update={"speech_rate_multiplier": Decimal("NaN")}),
        _settings().model_copy(update={"support_mode": "unknown"}),
        _values(),
        SupportPreferences(),
    ],
)
def test_invalid_or_preview_like_inputs_are_not_replaced_by_defaults(
    value: object, caplog: pytest.LogCaptureFixture
) -> None:
    for call in (
        lambda: composition._map_support_preferences(value),
        lambda: composition._compose_recommendation(value, _evidence(), _key()),
    ):
        with pytest.raises(support_settings.InvalidSupportSettings) as rejected:
            call()
        assert str(rejected.value) == "Stored support settings are invalid."
    assert "PRIVATE" not in caplog.text


@pytest.mark.parametrize("mode", ["adaptive", "baseline_fixed", "manual_override"])
@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("evidence_case", ["adequate", "few", "missing"])
def test_composition_reuses_engine_precedence_and_never_changes_settings(
    mode: str, locked: bool, evidence_case: str
) -> None:
    settings = _settings(support_mode=mode, manual_override_locked=locked)
    key = _key(support_mode=mode)
    count = 2 if evidence_case == "few" else 6
    evidence = _evidence(
        *(
            _observation(
                day,
                key=key,
                hesitation_count=None if evidence_case == "missing" and day == 1 else 2,
            )
            for day in range(1, count + 1)
        )
    )
    before = settings.model_dump()
    evidence_before = evidence.report.model_dump()
    decision = composition._compose_recommendation(settings, evidence, key)
    assert decision is not None
    preferences = composition._map_support_preferences(settings)
    assert preferences is not None
    thresholds = AdaptationThresholds()
    expected_input = map_longitudinal_partition_to_adaptation_input(
        evidence,
        key,
        support_preferences=preferences,
        manual_override_locked=locked,
        thresholds=thresholds,
    )
    assert decision == recommend_adaptation(expected_input, thresholds)
    assert decision.is_advisory is True and decision.safe_to_apply_automatically is False
    if mode == "baseline_fixed":
        assert decision.reason_codes == ("baseline_fixed_mode",)
        assert decision.blocked_by_manual_override is False
    elif mode == "manual_override" or locked:
        assert decision.reason_codes == (
            ("manual_override_locked" if locked else "manual_override_active"),
        )
        assert decision.blocked_by_manual_override is True
    elif evidence_case != "adequate":
        assert decision.action == "insufficient_evidence"
    else:
        assert decision.action == "increase_difficulty"
    if mode != "adaptive" or locked:
        assert decision.action == "maintain"
        assert decision.support_adjustments == ()
        assert decision.recommended_difficulty_tier == settings.default_difficulty_tier
        assert decision.recommended_support_mode == settings.support_mode
    assert settings.model_dump() == before
    assert evidence.report.model_dump() == evidence_before


@pytest.mark.parametrize("change", ["mode", "difficulty", "absent_task"])
def test_context_mismatch_never_selects_an_alternative_partition(change: str) -> None:
    settings = _settings()
    evidence = _evidence(*(_observation(day) for day in range(1, 7)))
    key = (
        _key(support_mode="manual_override")
        if change == "mode"
        else (
            _key(difficulty_tier="advanced")
            if change == "difficulty"
            else _key(task_type="guided_echo_reading")
        )
    )
    with pytest.raises(AdaptationMappingError):
        composition._compose_recommendation(settings, evidence, key)


@pytest.mark.parametrize("locked", [False, True])
def test_empty_evidence_is_not_hidden_by_a_lock(locked: bool) -> None:
    with pytest.raises(AdaptationMappingError, match="matching partition"):
        composition._compose_recommendation(
            _settings(manual_override_locked=locked), _evidence(), _key()
        )


@pytest.mark.parametrize(
    "projector", [project_learner_progress, project_guardian_summary, project_educator_analytics]
)
def test_role_dashboard_projections_cannot_substitute_for_completed_evidence(
    projector: object,
) -> None:
    evidence = _evidence(*(_observation(day) for day in range(1, 7)))
    projection = projector(evidence.report)
    with pytest.raises(TypeError, match="verified CompletedSessionEvidence"):
        composition._compose_recommendation(_settings(), projection, _key())


def test_mocked_read_projection_composes_without_any_settings_writes() -> None:
    db = _db(_row(manual_override_locked=True))
    current = support_settings._read_support_settings(db, LEARNER)
    evidence = _evidence(*(_observation(day) for day in range(1, 7)))
    decision = composition._compose_recommendation(current, evidence, _key())
    assert decision is not None and decision.reason_codes == ("manual_override_locked",)
    _no_writes(db)


@pytest.mark.parametrize(
    "failure", [RuntimeError("PRIVATE repository"), ValueError("PRIVATE repository")]
)
def test_repository_unavailability_is_not_absence_or_a_default_recommendation(
    failure: Exception,
) -> None:
    db = _db(None)
    db.scalars.side_effect = failure
    compose = MagicMock(wraps=composition._compose_recommendation)
    with pytest.raises(support_settings.SupportSettingsUnavailable):
        compose(support_settings._read_support_settings(db, LEARNER), _evidence(), _key())
    compose.assert_not_called()
    _no_writes(db)


def test_pure_composition_never_calls_settings_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    read = MagicMock(side_effect=AssertionError("No I/O in pure composition"))
    monkeypatch.setattr(support_settings.repository, "get_support_settings", read)
    assert (
        composition._compose_recommendation(_settings(), _evidence(_observation(1)), _key())
        is not None
    )
    read.assert_not_called()


def test_composition_is_unregistered_and_has_no_io_or_security_substitute_imports() -> None:
    path = Path(composition.__file__).resolve()
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        value.startswith(
            ("sqlalchemy", "httpx", "fastapi", "app.db", "app.modules.auth", "app.modules.learners")
        )
        for value in imports
    )
    assert all(route.endpoint.__module__ != composition.__name__ for route in router.routes)
    for other in path.parents[2].rglob("*.py"):
        # This named private mapper is the only approved additional consumer.
        if other not in (
            path,
            path.with_name("recommendation_presentation.py"),
            path.with_name("recommendation_snapshot.py"),
            path.with_name("connected_demo.py"),
            path.with_name("demo_calculation.py"),
        ):
            assert "import recommendation_composition" not in other.read_text(encoding="utf-8")
            assert (
                "from app.modules.learner_modelling.recommendation_composition"
                not in other.read_text(encoding="utf-8")
            )


def test_missing_row_stays_none_through_read_and_composition() -> None:
    db = _db(None)
    current = support_settings._read_support_settings(db, LEARNER)
    assert current is None
    assert composition._compose_recommendation(current, _evidence(), _key()) is None
    _no_writes(db)


def test_invalid_stored_row_never_becomes_absence_or_a_recommendation() -> None:
    db = _db(_row(row_version=0))
    compose = MagicMock(wraps=composition._compose_recommendation)
    with pytest.raises(support_settings.InvalidSupportSettings):
        compose(support_settings._read_support_settings(db, LEARNER), _evidence(), _key())
    compose.assert_not_called()
    _no_writes(db)


def test_explicit_task_partition_does_not_pool_other_task_evidence() -> None:
    primary = tuple(_observation(day) for day in range(1, 7))
    other_key = _key(task_type="guided_echo_reading")
    other = tuple(
        _observation(
            day, key=other_key, words_correct=40, active_duration_ms=180_000, hesitation_count=25
        )
        for day in range(1, 7)
    )
    baseline = composition._compose_recommendation(_settings(), _evidence(*primary), _key())
    combined = _evidence(*reversed((*primary, *other)))
    assert composition._compose_recommendation(_settings(), combined, _key()) == baseline
    other_decision = composition._compose_recommendation(_settings(), combined, other_key)
    assert other_decision is not None and other_decision != baseline
    assert other_decision.is_advisory is True
    assert other_decision.safe_to_apply_automatically is False
