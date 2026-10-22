"""Offline backend/mobile contract tests using existing synthetic fixtures."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from test_learner_adaptation_mapping import _evidence, _key, _observation
from test_learner_recommendation_composition import _settings

from app.modules.learner_modelling.recommendation_composition import _compose_recommendation
from app.modules.learner_modelling.recommendation_mobile import (
    ACTIONS,
    MODES,
    TIERS,
    _mobile_recommendation,
)
from app.modules.learner_modelling.recommendation_presentation import (
    InvalidRecommendationPresentation,
)
from app.modules.learner_modelling.recommendation_snapshot import _build_snapshot


@pytest.mark.parametrize("mode", ["adaptive", "baseline_fixed", "manual_override"])
@pytest.mark.parametrize("locked", [True, False])
@pytest.mark.parametrize("limited", [True, False])
def test_real_engine_mapping(mode: str, locked: bool, limited: bool) -> None:
    settings = _settings(support_mode=mode, manual_override_locked=locked)
    key = _key(support_mode=mode)

    evidence = _evidence(*(_observation(day, key=key) for day in range(1, 2 if limited else 7)))
    decision = _compose_recommendation(settings, evidence, key)
    view = _mobile_recommendation(settings, decision, evidence=evidence, partition=key)
    assert decision is not None
    assert view.current == "intermediate / " + MODES[mode]
    assert view.action == ACTIONS[decision.action]
    assert view.reasons == decision.explanations
    assert view.global_lock is locked
    assert view.fixed_baseline == (mode == "baseline_fixed")
    assert view.manual_control_prevents_adjustment == (locked or mode == "manual_override")
    assert view.changes_applied is False and view.automatic_application_allowed is False
    if limited and mode == "adaptive" and not locked:
        assert view.limitations and view.evidence_state == "insufficient"
    if mode != "adaptive" or locked:
        assert not view.proposed


@pytest.mark.parametrize(
    "change",
    [
        {"action": "unknown"},
        {"recommended_difficulty_tier": "unknown"},
        {"safe_to_apply_automatically": True},
    ],
)
def test_invalid_decision_rejected(change: dict[str, object]) -> None:
    settings, evidence, key = (
        _settings(),
        _evidence(*(_observation(day) for day in range(1, 7))),
        _key(),
    )
    decision = _compose_recommendation(settings, evidence, key)
    assert decision is not None
    with pytest.raises(InvalidRecommendationPresentation):
        _mobile_recommendation(
            settings, replace(decision, **change), evidence=evidence, partition=key
        )


def test_context_missing_and_unavailable() -> None:
    assert _mobile_recommendation(None, None).status == "settings_unavailable"
    assert _mobile_recommendation(_settings(), None).status == "recommendation_unavailable"
    evidence = _evidence(*(_observation(day) for day in range(1, 7)))
    with pytest.raises(InvalidRecommendationPresentation):
        _mobile_recommendation(
            _settings(),
            _compose_recommendation(_settings(), evidence, _key()),
            evidence=evidence,
            partition=_key(difficulty_tier="early"),
        )


def test_explicit_labels_and_snapshot_is_engine_generated_without_io() -> None:
    assert TIERS == {"early": "beginner", "intermediate": "intermediate", "advanced": "advanced"}
    assert set(ACTIONS) == {
        "maintain",
        "increase_support",
        "reduce_support",
        "increase_difficulty",
        "decrease_difficulty",
        "insufficient_evidence",
    }
    with patch("socket.socket", side_effect=AssertionError("No network")):
        snapshot = _build_snapshot()
    data = snapshot.model_dump(mode="json")
    assert data["synthetic"] is True and data["role"] == "learner"
    assert data["source"] == "backend-recommendation-engine"
    artifact = (
        Path(__file__).resolve().parents[3]
        / "mobile/src/features/learnerModelling/preview/backendRecommendationSnapshot.json"
    )
    assert json.loads(artifact.read_text()) == data
    for forbidden in ("learner_id", "session_id", "actor_id", "raw_sessions", "row_version"):
        assert forbidden not in snapshot.model_dump_json()


@pytest.mark.parametrize(
    "tier,label",
    [("early", "beginner"), ("intermediate", "intermediate"), ("advanced", "advanced")],
)
def test_all_difficulty_labels(tier: str, label: str) -> None:
    settings = _settings(default_difficulty_tier=tier)
    key = _key(difficulty_tier=tier)
    evidence = _evidence(*(_observation(day, key=key) for day in range(1, 7)))
    view = _mobile_recommendation(
        settings, _compose_recommendation(settings, evidence, key), evidence=evidence, partition=key
    )
    assert view.current == label + " / Adaptive support"


def test_export_requires_development_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.learner_modelling.recommendation_snapshot import main

    monkeypatch.setattr("sys.argv", ["recommendation_snapshot"])
    with pytest.raises(SystemExit) as rejected:
        main()
    assert rejected.value.code == 2


def test_support_changes_keep_engine_values_and_explanations() -> None:
    settings, key = _settings(), _key()
    evidence = _evidence(
        *(
            _observation(day, words_correct=80, active_duration_ms=180_000, hesitation_count=20)
            for day in range(1, 7)
        )
    )
    decision = _compose_recommendation(settings, evidence, key)
    assert decision is not None and decision.support_adjustments
    view = _mobile_recommendation(settings, decision, evidence=evidence, partition=key)
    for item in decision.support_adjustments:
        assert any(
            item.explanation in text and str(item.suggested_value) in text for text in view.proposed
        )
    assert settings.enable_syllable_assistance is False


def test_private_modules_have_no_production_importers() -> None:
    import app.modules.learner_modelling.recommendation_mobile as module

    path = Path(module.__file__).resolve()
    approved = {
        path,
        path.with_name("recommendation_snapshot.py"),
        path.with_name("connected_demo.py"),
        path.with_name("demo_calculation.py"),
    }
    for other in path.parents[2].rglob("*.py"):
        if other not in approved:
            text = other.read_text(encoding="utf-8")
            assert "from app.modules.learner_modelling.recommendation_mobile" not in text
            assert "from app.modules.learner_modelling.recommendation_snapshot" not in text
