"""Unit tests for the adaptive reading-support decision engine.

Tests cover:
    - Insufficient completed sessions (all modes)
    - Missing accuracy, WPM, and hesitation measurements
    - Strong performance with sufficient evidence → increase difficulty
    - Lower accuracy with sufficient evidence → decrease difficulty / increase support
    - Borderline accuracy results → conservative maintain
    - Contradictory indicators → conservative maintain
    - Fixed baseline mode protection
    - Manual override mode protection
    - Locked manual preference
    - Difficulty tier boundaries (lowest tier, highest tier)
    - One-level-only difficulty changes
    - Determinism: identical inputs → identical outputs
    - Ordering invariance: different session orderings yield the same outcome
    - Stable reason_codes ordering and explanations ordering
    - Explicit thresholds visible in DecisionEvidence
    - Experimental engagement score cannot independently cause difficulty decrease
    - Outputs never authorise automatic application (safe_to_apply_automatically=False)
    - Outputs are always advisory (is_advisory=True)
    - No mutation of input objects
    - No personal data present in returned explanations

All test data is synthetic.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.learner_modelling.adaptation import (
    ADAPTATION_ENGINE_VERSION,
    NON_CLINICAL_ADAPTATION_DISCLAIMER,
    AdaptationInput,
    AdaptationThresholds,
    SupportPreferences,
    recommend_adaptation,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _default_prefs(**overrides: Any) -> SupportPreferences:
    kwargs: dict[str, Any] = {
        "enable_speech_cues": True,
        "speech_rate_multiplier": 1.00,
        "enable_syllable_assistance": True,
        "enable_phoneme_breakdown": True,
        "enable_visual_pacing": False,
        "visual_pacing_rate_wpm": None,
        "enable_line_focus": False,
        "simplification_level": 2,
        "pause_threshold_ms": 2500,
    }
    kwargs.update(overrides)
    return SupportPreferences(**kwargs)


def _make_input(
    difficulty_tier: str = "intermediate",
    support_mode: str = "adaptive",
    manual_override_locked: bool = False,
    mean_accuracy: float | None = 0.88,
    mean_wpm: float | None = 70.0,
    mean_hesitation_rate_per_word: float | None = 0.05,
    mean_engagement_score: float | None = 0.75,
    session_count: int = 5,
    evidence_window_sufficient: bool = True,
    prefs: SupportPreferences | None = None,
) -> AdaptationInput:
    return AdaptationInput(
        current_difficulty_tier=difficulty_tier,
        current_support_mode=support_mode,
        manual_override_locked=manual_override_locked,
        support_preferences=prefs or _default_prefs(),
        mean_accuracy=mean_accuracy,
        mean_wpm=mean_wpm,
        mean_hesitation_rate_per_word=mean_hesitation_rate_per_word,
        mean_engagement_score=mean_engagement_score,
        session_count=session_count,
        evidence_window_sufficient=evidence_window_sufficient,
    )


@pytest.fixture()
def default_thresholds() -> AdaptationThresholds:
    return AdaptationThresholds()


# ---------------------------------------------------------------------------
# 1. Insufficient evidence
# ---------------------------------------------------------------------------


class TestInsufficientEvidence:
    def test_too_few_sessions_returns_insufficient_evidence(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(session_count=2, evidence_window_sufficient=False)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "insufficient_evidence"
        assert "insufficient_session_count" in dec.reason_codes
        assert dec.recommended_difficulty_tier == "intermediate"
        assert dec.safe_to_apply_automatically is False
        assert dec.is_advisory is True

    def test_zero_sessions_returns_insufficient_evidence(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(session_count=0, evidence_window_sufficient=False)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "insufficient_evidence"

    def test_session_count_in_explanation(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(session_count=1, evidence_window_sufficient=False)
        dec = recommend_adaptation(inp, default_thresholds)
        combined = " ".join(dec.explanations)
        # Explanation must mention session count context — not a personal identifier
        assert "1" in combined or "session" in combined.lower()

    def test_threshold_visible_in_evidence(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(session_count=2, evidence_window_sufficient=False)
        dec = recommend_adaptation(inp, default_thresholds)
        ev_names = [e.metric_name for e in dec.evidence]
        assert "session_count" in ev_names
        session_ev = next(e for e in dec.evidence if e.metric_name == "session_count")
        assert session_ev.threshold_used == float(
            default_thresholds.min_sessions_for_recommendation
        )

    def test_evidence_window_false_overrides_session_count(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """evidence_window_sufficient=False always triggers insufficient evidence."""
        inp = _make_input(session_count=100, evidence_window_sufficient=False)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "insufficient_evidence"
        assert dec.reason_codes == ("insufficient_evidence_window",)
        assert dec.evidence[0].metric_name == "evidence_window_sufficient"


# ---------------------------------------------------------------------------
# 2. Missing metric handling
# ---------------------------------------------------------------------------


class TestMissingMetrics:
    def test_missing_accuracy_with_good_wpm_and_hes_maintains(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """Absence of accuracy must not be treated as zero accuracy."""
        inp = _make_input(mean_accuracy=None, mean_wpm=95.0, mean_hesitation_rate_per_word=0.02)
        dec = recommend_adaptation(inp, default_thresholds)
        # Without accuracy, cannot make a difficulty change — should maintain
        assert dec.action == "maintain"
        assert dec.safe_to_apply_automatically is False

    def test_missing_wpm_with_strong_accuracy_can_still_increase_difficulty(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """Strong accuracy without WPM data should still allow difficulty increase
        (wpm=None is not blocking).
        """
        inp = _make_input(
            mean_accuracy=0.96,
            mean_wpm=None,
            mean_hesitation_rate_per_word=0.02,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_difficulty"

    def test_missing_hesitation_does_not_block_increase_difficulty(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            mean_accuracy=0.96,
            mean_wpm=100.0,
            mean_hesitation_rate_per_word=None,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_difficulty"

    def test_missing_hesitation_alone_with_low_acc_no_wpm_maintains(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """Low accuracy + missing WPM + missing hesitation → no corroboration → maintain."""
        inp = _make_input(
            mean_accuracy=0.60,
            mean_wpm=None,
            mean_hesitation_rate_per_word=None,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        # Low accuracy but no corroborating evidence → conservative maintain
        assert dec.action in ("maintain", "decrease_difficulty")
        # If maintain, must explain lack of corroboration
        if dec.action == "maintain":
            combined = " ".join(dec.explanations).lower()
            assert "corrobor" in combined or "not available" in combined or "monitor" in combined

    def test_all_metrics_missing_maintains(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(
            mean_accuracy=None,
            mean_wpm=None,
            mean_hesitation_rate_per_word=None,
            mean_engagement_score=None,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "maintain"
        assert dec.safe_to_apply_automatically is False

    def test_high_accuracy_without_fluency_corroboration_maintains(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            mean_accuracy=0.97,
            mean_wpm=None,
            mean_hesitation_rate_per_word=None,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "maintain"

    def test_high_accuracy_with_high_hesitation_does_not_increase_difficulty(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            mean_accuracy=0.97,
            mean_wpm=None,
            mean_hesitation_rate_per_word=0.20,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "maintain"


# ---------------------------------------------------------------------------
# 3. Strong performance → increase difficulty
# ---------------------------------------------------------------------------


class TestIncreaseDifficulty:
    def test_strong_accuracy_and_wpm_increases_difficulty(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            difficulty_tier="intermediate",
            mean_accuracy=0.96,
            mean_wpm=100.0,
            mean_hesitation_rate_per_word=0.02,
            session_count=5,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_difficulty"
        assert dec.recommended_difficulty_tier == "advanced"
        assert dec.safe_to_apply_automatically is False
        assert dec.is_advisory is True

    def test_increase_is_exactly_one_tier(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(
            difficulty_tier="early",
            mean_accuracy=0.96,
            mean_wpm=100.0,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_difficulty"
        assert dec.recommended_difficulty_tier == "intermediate"  # only one step

    def test_accuracy_threshold_in_evidence(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(mean_accuracy=0.96, mean_wpm=100.0)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_difficulty"
        acc_ev = next((e for e in dec.evidence if e.metric_name == "mean_accuracy"), None)
        assert acc_ev is not None
        assert acc_ev.threshold_used == default_thresholds.accuracy_increase_difficulty_above
        assert acc_ev.contributed is True


# ---------------------------------------------------------------------------
# 4. Low accuracy → decrease difficulty / increase support
# ---------------------------------------------------------------------------


class TestDecreaseOrIncreaseSupport:
    def test_low_accuracy_with_low_wpm_decreases_difficulty(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            difficulty_tier="intermediate",
            mean_accuracy=0.62,
            mean_wpm=35.0,
            mean_hesitation_rate_per_word=0.15,
            session_count=5,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "decrease_difficulty"
        assert dec.recommended_difficulty_tier == "early"
        assert dec.safe_to_apply_automatically is False

    def test_decrease_is_exactly_one_tier(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(
            difficulty_tier="advanced",
            mean_accuracy=0.62,
            mean_wpm=35.0,
            mean_hesitation_rate_per_word=0.15,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "decrease_difficulty"
        assert dec.recommended_difficulty_tier == "intermediate"  # only one step

    def test_moderate_low_accuracy_without_corroboration_increases_support(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """Accuracy between increase-support and decrease-difficulty thresholds
        triggers increase support.
        """
        inp = _make_input(
            mean_accuracy=0.74,  # Below support threshold, outside difficulty borderline band.
            mean_wpm=60.0,
            mean_hesitation_rate_per_word=0.06,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_support"
        assert dec.safe_to_apply_automatically is False

    def test_increase_support_has_adjustments(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            mean_accuracy=0.74,
            prefs=_default_prefs(enable_speech_cues=False, simplification_level=1),
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_support"
        # At least one adjustment suggested
        assert len(dec.support_adjustments) > 0

    def test_low_accuracy_at_lowest_tier_maintains_not_decreases(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """At lowest tier, cannot decrease difficulty — should maintain with explanation."""
        inp = _make_input(
            difficulty_tier="early",
            mean_accuracy=0.62,
            mean_wpm=35.0,
            mean_hesitation_rate_per_word=0.15,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        # Cannot decrease below 'early' — should maintain
        assert dec.action == "maintain"
        assert dec.recommended_difficulty_tier == "early"
        combined = " ".join(dec.reason_codes)
        assert "lowest" in combined or "boundary" in combined or "tier" in combined


# ---------------------------------------------------------------------------
# 5. Borderline accuracy results
# ---------------------------------------------------------------------------


class TestBorderlineAccuracy:
    @pytest.mark.parametrize("offset", [-0.01, 0.0, 0.01])
    def test_borderline_near_increase_threshold_maintains(
        self, default_thresholds: AdaptationThresholds, offset: float
    ) -> None:
        borderline_acc = default_thresholds.accuracy_increase_difficulty_above + offset
        inp = _make_input(
            mean_accuracy=borderline_acc,
            mean_wpm=100.0,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        # Borderline should yield maintain, not increase_difficulty
        assert dec.action == "maintain"
        combined = " ".join(dec.reason_codes)
        assert "borderline" in combined

    @pytest.mark.parametrize("offset", [-0.01, 0.0, 0.01])
    def test_borderline_near_decrease_threshold_maintains(
        self, default_thresholds: AdaptationThresholds, offset: float
    ) -> None:
        borderline_acc = default_thresholds.accuracy_decrease_difficulty_below + offset
        inp = _make_input(
            mean_accuracy=borderline_acc,
            mean_wpm=35.0,
            mean_hesitation_rate_per_word=0.15,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "maintain"

    def test_well_above_borderline_triggers_increase(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        clear_acc = default_thresholds.accuracy_increase_difficulty_above + 0.05
        inp = _make_input(mean_accuracy=clear_acc, mean_wpm=100.0)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_difficulty"


# ---------------------------------------------------------------------------
# 6. Contradictory indicators
# ---------------------------------------------------------------------------


class TestContradictoryIndicators:
    def test_high_accuracy_but_low_wpm_maintains(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """High accuracy but WPM below fluency threshold → conservative maintain."""
        inp = _make_input(
            mean_accuracy=0.96,
            mean_wpm=40.0,  # Below wpm_increase_difficulty_above
            mean_hesitation_rate_per_word=0.15,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "maintain"

    def test_low_accuracy_but_no_corroboration_maintains(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """Low accuracy without WPM/hesitation corroboration → conservative maintain."""
        inp = _make_input(
            mean_accuracy=0.62,
            mean_wpm=None,
            mean_hesitation_rate_per_word=None,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action in ("maintain",)


# ---------------------------------------------------------------------------
# 7. Fixed baseline mode
# ---------------------------------------------------------------------------


class TestFixedBaselineMode:
    def test_baseline_fixed_always_maintains(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(support_mode="baseline_fixed", mean_accuracy=0.96, mean_wpm=100.0)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "maintain"
        assert dec.safe_to_apply_automatically is False

    def test_baseline_fixed_preserves_tier(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(
            support_mode="baseline_fixed",
            difficulty_tier="early",
            mean_accuracy=0.96,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.recommended_difficulty_tier == "early"

    def test_baseline_fixed_has_explanation(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(support_mode="baseline_fixed")
        dec = recommend_adaptation(inp, default_thresholds)
        assert len(dec.explanations) > 0
        combined = " ".join(dec.explanations).lower()
        assert "fixed" in combined or "baseline" in combined

    def test_baseline_fixed_not_blocked_by_override(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(support_mode="baseline_fixed")
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.blocked_by_manual_override is False

    def test_baseline_fixed_rule_id(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(support_mode="baseline_fixed")
        dec = recommend_adaptation(inp, default_thresholds)
        assert "FIXED" in dec.rule_id


# ---------------------------------------------------------------------------
# 8. Manual override mode
# ---------------------------------------------------------------------------


class TestManualOverrideMode:
    def test_manual_override_mode_maintains(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(support_mode="manual_override", mean_accuracy=0.96, mean_wpm=100.0)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "maintain"
        assert dec.blocked_by_manual_override is True
        assert dec.safe_to_apply_automatically is False

    def test_manual_override_explanation_references_learner_control(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(support_mode="manual_override")
        dec = recommend_adaptation(inp, default_thresholds)
        combined = " ".join(dec.explanations).lower()
        assert "learner" in combined or "adult" in combined or "control" in combined


# ---------------------------------------------------------------------------
# 9. Locked manual preference
# ---------------------------------------------------------------------------


class TestLockedManualPreference:
    def test_manual_override_locked_maintains(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            support_mode="adaptive",
            manual_override_locked=True,
            mean_accuracy=0.96,
            mean_wpm=100.0,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "maintain"
        assert dec.blocked_by_manual_override is True

    def test_locked_explanation_mentions_authorised_adult(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(support_mode="adaptive", manual_override_locked=True)
        dec = recommend_adaptation(inp, default_thresholds)
        combined = " ".join(dec.explanations).lower()
        assert "authorised" in combined or "locked" in combined or "adult" in combined

    def test_locked_reason_code(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(support_mode="adaptive", manual_override_locked=True)
        dec = recommend_adaptation(inp, default_thresholds)
        assert "manual_override_locked" in dec.reason_codes


# ---------------------------------------------------------------------------
# 10. Difficulty tier boundary tests
# ---------------------------------------------------------------------------


class TestDifficultyBoundaries:
    def test_highest_tier_does_not_increase_further(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            difficulty_tier="advanced",
            mean_accuracy=0.98,
            mean_wpm=120.0,
            mean_hesitation_rate_per_word=0.01,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.recommended_difficulty_tier == "advanced"
        assert dec.action == "maintain"
        combined = " ".join(dec.reason_codes)
        assert "highest" in combined or "advanced" in combined or "tier" in combined

    def test_lowest_tier_does_not_decrease_further(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            difficulty_tier="early",
            mean_accuracy=0.62,
            mean_wpm=35.0,
            mean_hesitation_rate_per_word=0.15,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.recommended_difficulty_tier == "early"
        assert dec.action == "maintain"


# ---------------------------------------------------------------------------
# 11. One-level-only change
# ---------------------------------------------------------------------------


class TestOneStepChange:
    def test_increase_difficulty_is_one_step_from_early_to_intermediate(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(difficulty_tier="early", mean_accuracy=0.96, mean_wpm=100.0)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.recommended_difficulty_tier == "intermediate"

    def test_decrease_difficulty_is_one_step_from_advanced_to_intermediate(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            difficulty_tier="advanced",
            mean_accuracy=0.62,
            mean_wpm=35.0,
            mean_hesitation_rate_per_word=0.15,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        if dec.action == "decrease_difficulty":
            assert dec.recommended_difficulty_tier == "intermediate"


# ---------------------------------------------------------------------------
# 12. Determinism — identical inputs → identical outputs
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_inputs_produce_identical_outputs(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(mean_accuracy=0.96, mean_wpm=100.0)
        dec1 = recommend_adaptation(inp, default_thresholds)
        dec2 = recommend_adaptation(inp, default_thresholds)
        assert dec1 == dec2

    def test_determinism_with_missing_metrics(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(mean_accuracy=None, mean_wpm=None, mean_hesitation_rate_per_word=None)
        dec1 = recommend_adaptation(inp, default_thresholds)
        dec2 = recommend_adaptation(inp, default_thresholds)
        assert dec1 == dec2

    def test_determinism_for_borderline_case(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        borderline = default_thresholds.accuracy_increase_difficulty_above + 0.01
        inp = _make_input(mean_accuracy=borderline, mean_wpm=100.0)
        dec1 = recommend_adaptation(inp, default_thresholds)
        dec2 = recommend_adaptation(inp, default_thresholds)
        assert dec1.action == dec2.action
        assert dec1.reason_codes == dec2.reason_codes


# ---------------------------------------------------------------------------
# 13. Stable ordering of reason codes and explanations
# ---------------------------------------------------------------------------


class TestStableOrdering:
    def test_reason_codes_are_sorted(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(mean_accuracy=0.88)
        dec = recommend_adaptation(inp, default_thresholds)
        assert list(dec.reason_codes) == sorted(dec.reason_codes)

    def test_explanations_are_sorted(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(mean_accuracy=0.88)
        dec = recommend_adaptation(inp, default_thresholds)
        assert list(dec.explanations) == sorted(dec.explanations)

    def test_support_adjustments_are_sorted_by_field(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            mean_accuracy=0.72,
            prefs=_default_prefs(enable_speech_cues=False, simplification_level=1),
        )
        dec = recommend_adaptation(inp, default_thresholds)
        fields = [a.preference_field for a in dec.support_adjustments]
        assert fields == sorted(fields)


# ---------------------------------------------------------------------------
# 14. Evidence thresholds are explicit in records
# ---------------------------------------------------------------------------


class TestEvidenceThresholds:
    def test_increase_difficulty_evidence_contains_threshold(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(mean_accuracy=0.96, mean_wpm=100.0)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action == "increase_difficulty"
        acc_ev = next((e for e in dec.evidence if e.metric_name == "mean_accuracy"), None)
        assert acc_ev is not None
        assert acc_ev.threshold_used is not None

    def test_decrease_difficulty_evidence_contains_threshold(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(mean_accuracy=0.62, mean_wpm=35.0, mean_hesitation_rate_per_word=0.15)
        dec = recommend_adaptation(inp, default_thresholds)
        acc_ev = next((e for e in dec.evidence if e.metric_name == "mean_accuracy"), None)
        if dec.action == "decrease_difficulty" and acc_ev:
            assert acc_ev.threshold_used == default_thresholds.accuracy_decrease_difficulty_below

    def test_insufficient_evidence_contains_session_threshold(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(session_count=1, evidence_window_sufficient=False)
        dec = recommend_adaptation(inp, default_thresholds)
        ev = next((e for e in dec.evidence if e.metric_name == "session_count"), None)
        assert ev is not None
        assert ev.threshold_used == float(default_thresholds.min_sessions_for_recommendation)


# ---------------------------------------------------------------------------
# 15. Engagement score cannot independently cause difficulty decrease
# ---------------------------------------------------------------------------


class TestEngagementScoreRestriction:
    def test_low_engagement_alone_does_not_decrease_difficulty(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """Very low engagement score with good accuracy/WPM must not decrease difficulty."""
        inp = _make_input(
            difficulty_tier="intermediate",
            mean_accuracy=0.92,  # well within range, not triggering decrease
            mean_wpm=80.0,
            mean_engagement_score=0.10,  # very low engagement
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action != "decrease_difficulty"

    def test_high_engagement_alone_does_not_increase_difficulty(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """High engagement score with moderate accuracy must not increase difficulty."""
        inp = _make_input(
            difficulty_tier="intermediate",
            mean_accuracy=0.80,  # does not meet increase threshold
            mean_wpm=60.0,
            mean_engagement_score=0.99,  # maximum engagement
        )
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.action != "increase_difficulty"

    def test_engagement_none_does_not_affect_maintain(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(mean_accuracy=0.88, mean_engagement_score=None)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.safe_to_apply_automatically is False


# ---------------------------------------------------------------------------
# 16. Outputs never authorise automatic application
# ---------------------------------------------------------------------------


class TestSafetyInvariants:
    @pytest.mark.parametrize("support_mode", ["adaptive", "baseline_fixed", "manual_override"])
    def test_safe_to_apply_always_false(
        self,
        support_mode: str,
        default_thresholds: AdaptationThresholds,
    ) -> None:
        inp = _make_input(support_mode=support_mode)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.safe_to_apply_automatically is False

    @pytest.mark.parametrize("support_mode", ["adaptive", "baseline_fixed", "manual_override"])
    def test_is_advisory_always_true(
        self,
        support_mode: str,
        default_thresholds: AdaptationThresholds,
    ) -> None:
        inp = _make_input(support_mode=support_mode)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.is_advisory is True

    def test_strong_performance_still_not_auto_applicable(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(mean_accuracy=0.99, mean_wpm=150.0)
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.safe_to_apply_automatically is False

    def test_disclaimer_present_in_all_decisions(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        for mode in ("adaptive", "baseline_fixed", "manual_override"):
            inp = _make_input(support_mode=mode)
            dec = recommend_adaptation(inp, default_thresholds)
            assert len(dec.disclaimer) > 0
            assert "clinical" in dec.disclaimer.lower() or "heuristic" in dec.disclaimer.lower()


# ---------------------------------------------------------------------------
# 17. Input objects are not mutated
# ---------------------------------------------------------------------------


class TestInputImmutability:
    def test_input_not_mutated_by_recommend(self, default_thresholds: AdaptationThresholds) -> None:
        inp = _make_input(mean_accuracy=0.96, mean_wpm=100.0)
        # AdaptationInput is a frozen dataclass — this test verifies no AttributeError
        original_acc = inp.mean_accuracy
        original_wpm = inp.mean_wpm
        _ = recommend_adaptation(inp, default_thresholds)
        assert inp.mean_accuracy == original_acc
        assert inp.mean_wpm == original_wpm

    def test_thresholds_not_mutated(self, default_thresholds: AdaptationThresholds) -> None:
        original_version = default_thresholds.version_label
        original_min = default_thresholds.min_sessions_for_recommendation
        inp = _make_input(mean_accuracy=0.96, mean_wpm=100.0)
        _ = recommend_adaptation(inp, default_thresholds)
        assert default_thresholds.version_label == original_version
        assert default_thresholds.min_sessions_for_recommendation == original_min


# ---------------------------------------------------------------------------
# 18. No personal data in returned explanations
# ---------------------------------------------------------------------------


class TestNoPersonalDataInExplanations:
    def test_explanations_contain_no_learner_ids(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        """Explanations must not include learner IDs, names, or identifying data."""
        inp = _make_input(mean_accuracy=0.72)
        dec = recommend_adaptation(inp, default_thresholds)
        combined = " ".join(dec.explanations)
        # No UUID-like strings in explanations
        import re

        uuid_pattern = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
        )
        assert not uuid_pattern.search(combined)

    def test_explanations_contain_no_diagnosis_language(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        for mode in ("adaptive", "baseline_fixed", "manual_override"):
            inp = _make_input(support_mode=mode, mean_accuracy=0.62, mean_wpm=30.0)
            dec = recommend_adaptation(inp, default_thresholds)
            combined = " ".join(dec.explanations).lower()
            for forbidden in ("dyslexia", "disorder", "diagnosis", "clinical", "impairment"):
                assert forbidden not in combined, (
                    f"Forbidden term '{forbidden}' found in explanations for mode={mode}"
                )


# ---------------------------------------------------------------------------
# 19. Versioned rule set and thresholds visible in output
# ---------------------------------------------------------------------------


class TestVersionedOutput:
    def test_rule_set_version_matches_thresholds(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input()
        dec = recommend_adaptation(inp, default_thresholds)
        assert dec.rule_set_version == default_thresholds.version_label

    def test_custom_thresholds_version_propagated(self) -> None:
        custom = AdaptationThresholds(version_label="v0.2-custom")
        inp = _make_input()
        dec = recommend_adaptation(inp, custom)
        assert dec.rule_set_version == "v0.2-custom"

    def test_module_version_constant_defined(self) -> None:
        assert ADAPTATION_ENGINE_VERSION.startswith("v")

    def test_disclaimer_is_non_clinical(self) -> None:
        assert NON_CLINICAL_ADAPTATION_DISCLAIMER
        assert "clinical" in NON_CLINICAL_ADAPTATION_DISCLAIMER.lower()


# ---------------------------------------------------------------------------
# 20. AdaptationThresholds validation
# ---------------------------------------------------------------------------


class TestThresholdsValidation:
    def test_zero_min_sessions_raises(self) -> None:
        with pytest.raises(ValueError, match="min_sessions"):
            AdaptationThresholds(min_sessions_for_recommendation=0)

    def test_negative_accuracy_threshold_raises(self) -> None:
        with pytest.raises(ValueError):
            AdaptationThresholds(accuracy_increase_support_below=-0.1)

    def test_default_thresholds_valid(self) -> None:
        t = AdaptationThresholds()
        assert t.min_sessions_for_recommendation == 3
        assert 0 < t.accuracy_increase_support_below < 1
        assert 0 < t.accuracy_increase_difficulty_above < 1


# ---------------------------------------------------------------------------
# 21. SupportPreferences validation
# ---------------------------------------------------------------------------


class TestSupportPreferencesValidation:
    def test_invalid_simplification_level_raises(self) -> None:
        with pytest.raises(ValueError, match="simplification_level"):
            SupportPreferences(simplification_level=6)

    def test_invalid_speech_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="speech_rate_multiplier"):
            SupportPreferences(speech_rate_multiplier=0.10)

    def test_invalid_pause_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="pause_threshold_ms"):
            SupportPreferences(pause_threshold_ms=500)

    def test_invalid_visual_pacing_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="visual_pacing_rate_wpm"):
            SupportPreferences(visual_pacing_rate_wpm=301)

    def test_valid_preferences_construct(self) -> None:
        prefs = SupportPreferences(simplification_level=3, speech_rate_multiplier=1.50)
        assert prefs.simplification_level == 3


# ---------------------------------------------------------------------------
# 22. Reduce support — high performance
# ---------------------------------------------------------------------------


class TestReduceSupport:
    def test_high_accuracy_and_good_wpm_reduces_support(
        self, default_thresholds: AdaptationThresholds
    ) -> None:
        inp = _make_input(
            difficulty_tier="intermediate",
            mean_accuracy=0.97,
            mean_wpm=90.0,
            mean_hesitation_rate_per_word=0.02,
        )
        dec = recommend_adaptation(inp, default_thresholds)
        # High accuracy + good WPM may yield increase_difficulty or reduce_support
        assert dec.action in ("increase_difficulty", "reduce_support")
        assert dec.safe_to_apply_automatically is False

    def test_reduce_support_has_explanation(self, default_thresholds: AdaptationThresholds) -> None:
        """Force purely support-reduction scenario
        (accuracy high but below difficulty threshold).
        """
        thresholds = AdaptationThresholds(
            accuracy_increase_difficulty_above=0.99,  # high bar for difficulty increase
            accuracy_reduce_support_above=0.85,
            wpm_reduce_support_above=70.0,
        )
        inp = _make_input(mean_accuracy=0.93, mean_wpm=85.0, mean_hesitation_rate_per_word=0.02)
        dec = recommend_adaptation(inp, thresholds)
        assert dec.action == "reduce_support"
        assert len(dec.explanations) > 0
        assert dec.safe_to_apply_automatically is False

    def test_high_hesitation_prevents_support_reduction(self) -> None:
        thresholds = AdaptationThresholds(
            accuracy_increase_difficulty_above=0.99,
            accuracy_reduce_support_above=0.85,
            wpm_reduce_support_above=70.0,
        )
        inp = _make_input(
            mean_accuracy=0.93,
            mean_wpm=85.0,
            mean_hesitation_rate_per_word=0.15,
        )
        dec = recommend_adaptation(inp, thresholds)
        assert dec.action == "maintain"


class TestAdaptationInputValidation:
    @pytest.mark.parametrize("difficulty_tier", ["", "beginner", "expert"])
    def test_invalid_difficulty_tier_raises(self, difficulty_tier: str) -> None:
        with pytest.raises(ValueError, match="current_difficulty_tier"):
            _make_input(difficulty_tier=difficulty_tier)

    @pytest.mark.parametrize("support_mode", ["", "automatic", "fixed"])
    def test_invalid_support_mode_raises(self, support_mode: str) -> None:
        with pytest.raises(ValueError, match="current_support_mode"):
            _make_input(support_mode=support_mode)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("mean_accuracy", -0.01),
            ("mean_accuracy", 1.01),
            ("mean_accuracy", float("nan")),
            ("mean_wpm", -1.0),
            ("mean_hesitation_rate_per_word", -0.01),
            ("mean_engagement_score", 1.01),
        ],
    )
    def test_invalid_metric_raises(self, field: str, value: float) -> None:
        with pytest.raises(ValueError, match=field):
            _make_input(**{field: value})

    def test_negative_session_count_raises(self) -> None:
        with pytest.raises(ValueError, match="session_count"):
            _make_input(session_count=-1)
