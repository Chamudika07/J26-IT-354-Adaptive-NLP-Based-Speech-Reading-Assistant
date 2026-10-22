"""Private advisory display projection tests; no database, HTTP or model access."""

import ast
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_learner_adaptation_mapping import _evidence, _key, _observation
from test_learner_recommendation_composition import _settings

from app.modules.learner_modelling import recommendation_presentation as presentation
from app.modules.learner_modelling.dashboard_projections import project_guardian_summary
from app.modules.learner_modelling.recommendation_composition import _compose_recommendation
from app.modules.learner_modelling.router import router
from app.modules.learner_modelling.support_settings import InvalidSupportSettings


def _case(mode: str = "adaptive", locked: bool = False, limited: bool = False):
    current = _settings(support_mode=mode, manual_override_locked=locked)
    key = _key(support_mode=mode)
    evidence = _evidence(*(_observation(day, key=key) for day in range(1, 3 if limited else 7)))
    decision = _compose_recommendation(current, evidence, key)
    assert decision is not None
    return current, evidence, key, decision


@pytest.mark.parametrize("mode", ["adaptive", "manual_override", "baseline_fixed"])
@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("limited", [False, True])
def test_available_projection_separates_current_proposed_evidence_and_manual_control(
    mode: str,
    locked: bool,
    limited: bool,
) -> None:
    settings, evidence, key, decision = _case(mode, locked, limited)
    before = settings.model_dump()
    view = presentation._present_recommendation(
        settings, decision, evidence=evidence, partition=key
    )
    assert view.status == "available" and view.current is not None
    assert view.current.difficulty_tier == settings.default_difficulty_tier
    assert view.current.support_mode == mode
    assert view.current.manual_override_locked is locked
    assert view.task_type == key.task_type
    assert view.action == decision.action
    assert set(view.explanations) == set(decision.explanations)
    assert view.evidence_state == ("insufficient" if limited else "sufficient")
    assert view.fixed_baseline is (mode == "baseline_fixed")
    assert view.manual_override_active is (mode == "manual_override")
    assert view.manual_control_prevents_adjustment is (locked or mode == "manual_override")
    assert view.blocked_by_manual_override is decision.blocked_by_manual_override
    assert view.automatic_application_allowed is False and view.changes_applied is False
    assert view.is_advisory is True and view.disclaimer == decision.disclaimer
    if mode != "adaptive" or locked:
        assert view.proposed is None and view.action == "maintain"
    elif limited:
        assert view.proposed is None
        assert view.limitations == view.explanations
    else:
        assert view.proposed is not None
        assert view.proposed.difficulty_tier == decision.recommended_difficulty_tier
        assert view.current.difficulty_tier != view.proposed.difficulty_tier
        assert view.proposed.support_mode is None  # No mode change is invented.
    if decision.action != "insufficient_evidence":
        assert (
            view.limitations == ()
        )  # Do not replace manual-control explanations with invented prose.
    assert settings.model_dump() == before


def test_missing_settings_is_explicit_not_unlocked_maintain_or_default() -> None:
    view = presentation._present_recommendation(None, None)
    assert view.status == "settings_unavailable"
    assert view.current is None and view.action is None and view.proposed is None
    assert view.manual_control_prevents_adjustment is None
    assert view.fixed_baseline is None and view.manual_override_active is None
    assert view.evidence_state == "unavailable" and view.explanations == ()


def test_unavailable_recommendation_preserves_known_current_settings_without_proposals() -> None:
    settings, _, key, _ = _case(locked=True)
    view = presentation._present_recommendation(settings, None, partition=key)
    assert view.status == "recommendation_unavailable"
    assert view.current is not None and view.current.manual_override_locked is True
    assert view.manual_control_prevents_adjustment is True
    assert view.blocked_by_manual_override is None  # No decision was evaluated.
    assert view.action is None and view.proposed is None
    assert view.explanations == () and view.limitations == ()
    assert view.evidence_state == "unavailable"


@pytest.mark.parametrize("missing", ["settings", "evidence", "partition"])
def test_a_decision_cannot_be_displayed_without_its_required_context(missing: str) -> None:
    settings, evidence, key, decision = _case()
    with pytest.raises(presentation.InvalidRecommendationPresentation):
        presentation._present_recommendation(
            None if missing == "settings" else settings,
            decision,
            evidence=None if missing == "evidence" else evidence,
            partition=None if missing == "partition" else key,
        )


@pytest.mark.parametrize(
    "key",
    [
        _key(difficulty_tier="advanced"),
        _key(support_mode="manual_override"),
        _key(task_type="guided_echo_reading"),
        _key(task_type="PRIVATE"),
    ],
)
def test_invalid_or_mismatched_context_fails_closed(key: object) -> None:
    settings, evidence, _, decision = _case()
    with pytest.raises(presentation.InvalidRecommendationPresentation):
        presentation._present_recommendation(settings, decision, evidence=evidence, partition=key)


@pytest.mark.parametrize(
    "changes",
    [
        {"is_advisory": False},
        {"safe_to_apply_automatically": True},
        {"recommended_difficulty_tier": "early"},
        {"explanations": ("PRIVATE unauthorized 999 score",)},
        {"blocked_by_manual_override": True},
    ],
)
def test_nonmatching_or_unsafe_decision_is_not_relabelled_as_valid(
    changes: dict[str, object],
) -> None:
    settings, evidence, key, decision = _case()
    with pytest.raises(presentation.InvalidRecommendationPresentation) as rejected:
        presentation._present_recommendation(
            settings, replace(decision, **changes), evidence=evidence, partition=key
        )
    assert "PRIVATE" not in str(rejected.value)


def test_proposed_adjustments_match_engine_and_never_overwrite_current_settings() -> None:
    settings = _settings()
    key = _key()
    evidence = _evidence(
        *(
            _observation(day, words_correct=80, active_duration_ms=180_000, hesitation_count=20)
            for day in range(1, 7)
        )
    )
    decision = _compose_recommendation(settings, evidence, key)
    assert decision is not None and decision.support_adjustments
    view = presentation._present_recommendation(
        settings, decision, evidence=evidence, partition=key
    )
    assert view.proposed is not None
    assert {
        (item.preference_field, item.proposed_value, item.explanation)
        for item in view.proposed.support_adjustments
    } == {
        (item.preference_field, item.suggested_value, item.explanation)
        for item in decision.support_adjustments
    }
    assert view.changes_applied is False
    assert settings.enable_syllable_assistance is False


def test_invalid_settings_and_role_projection_inputs_are_not_display_preferences() -> None:
    settings, evidence, key, decision = _case()
    with pytest.raises(InvalidSupportSettings):
        presentation._present_recommendation(
            settings.model_copy(update={"row_version": 0}),
            decision,
            evidence=evidence,
            partition=key,
        )
    with pytest.raises(presentation.InvalidRecommendationPresentation):
        presentation._present_recommendation(
            settings, decision, evidence=project_guardian_summary(evidence.report), partition=key
        )


def test_projection_is_minimal_frozen_and_cannot_claim_application_or_add_roles() -> None:
    settings, evidence, key, decision = _case()
    view = presentation._present_recommendation(
        settings, decision, evidence=evidence, partition=key
    )
    data = view.model_dump()
    for forbidden in (
        "learner_id",
        "actor_id",
        "role",
        "row_version",
        "evidence",
        "rule_id",
        "rule_set_version",
        "thresholds",
        "support_preferences",
        "session_id",
    ):
        assert forbidden not in data
    assert set(data["current"]) == {"difficulty_tier", "support_mode", "manual_override_locked"}
    with pytest.raises(ValidationError):
        view.changes_applied = True
    with pytest.raises(ValidationError):
        view.current.manual_override_locked = True
    with pytest.raises(ValidationError):
        presentation.RecommendationPresentation.model_validate({**data, "learner_id": "PRIVATE"})
    with pytest.raises(ValidationError):
        presentation.RecommendationPresentation.model_validate({**data, "changes_applied": True})


def test_presentation_is_private_without_io_or_role_security_substitutes() -> None:
    path = Path(presentation.__file__).resolve()
    imports = {
        node.module or ""
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig")))
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        value.startswith(
            ("sqlalchemy", "fastapi", "httpx", "app.db", "app.modules.auth", "app.modules.learners")
        )
        for value in imports
    )
    assert all(route.endpoint.__module__ != presentation.__name__ for route in router.routes)
    for other in path.parents[2].rglob("*.py"):
        if other not in (path, path.with_name("recommendation_mobile.py")):
            text = other.read_text(encoding="utf-8")
            assert "import recommendation_presentation" not in text
            assert "from app.modules.learner_modelling.recommendation_presentation" not in text
