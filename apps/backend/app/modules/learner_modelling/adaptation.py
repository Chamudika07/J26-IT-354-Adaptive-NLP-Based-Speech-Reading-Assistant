"""Deterministic, transparent adaptive reading-support decision engine.

This module produces advisory-only recommendations for reading-difficulty tier
and support-mode adjustments, derived from validated educational metrics.

IMPORTANT — RESEARCH HEURISTICS DISCLAIMER:
    All decision thresholds and rules are EXPERIMENTAL EDUCATIONAL HEURISTICS
    for software scaffolding. They are NOT clinically validated, do NOT constitute
    a diagnosis, and must NEVER be presented as clinical, psychological, or
    diagnostic findings. This module must not be used for medical assessment,
    dyslexia classification, or any high-stakes determination about a learner.

Design invariants:
    - Pure computation: no database sessions, ORM writes, HTTP requests, or AI calls.
    - Fully deterministic: identical versioned inputs always produce identical outputs.
    - Advisory-only: no output field authorises automatic application of any change.
    - Privacy-conscious: inputs contain only anonymised educational metrics — no
      learner names, birth dates, raw audio, document text, or clinical identifiers.
    - Missing data treated as missing, never coerced to zero or a default value.
    - No single metric (including engagement) can independently trigger a difficulty
      decrease; converging evidence across multiple indicators is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

ADAPTATION_ENGINE_VERSION: str = "v0.1-research-heuristic"

NON_CLINICAL_ADAPTATION_DISCLAIMER: str = (
    "Adaptive reading recommendations are experimental educational heuristics "
    "for software scaffolding only. They do not constitute a clinical assessment, "
    "diagnosis, or any determination of a learner's psychological or neurological state."
)

# ---------------------------------------------------------------------------
# Difficulty tier ordering — canonical sort for boundary detection
# ---------------------------------------------------------------------------

_DIFFICULTY_ORDER: list[str] = ["early", "intermediate", "advanced"]
_SUPPORT_MODES: tuple[str, ...] = ("baseline_fixed", "adaptive", "manual_override")


def _tier_index(tier: str) -> int:
    """Return canonical integer position for a difficulty tier string."""
    try:
        return _DIFFICULTY_ORDER.index(tier)
    except ValueError:
        # Unknown tier treated as middle tier to prevent boundary errors.
        return 1


# ---------------------------------------------------------------------------
# Versioned threshold configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdaptationThresholds:
    """Versioned, configurable thresholds for the adaptation rule set.

    All numeric values are RESEARCH HEURISTICS — not clinically validated.
    Callers may override individual values; version_label should be updated
    whenever thresholds are changed to support reproducibility.

    Accuracy thresholds (proportions in [0.0, 1.0]):
        accuracy_increase_support_below: Mean accuracy below this level triggers
            an increase-support recommendation when evidence is sufficient.
        accuracy_reduce_support_above: Mean accuracy above this level is one
            prerequisite for a reduce-support recommendation.
        accuracy_increase_difficulty_above: Mean accuracy above this level is one
            prerequisite for an increase-difficulty recommendation.
        accuracy_decrease_difficulty_below: Mean accuracy below this level is a
            prerequisite for a decrease-difficulty recommendation.
        accuracy_borderline_band: ±half-width around each threshold considered
            "borderline"; borderline results yield maintain, not a change.

    WPM thresholds (words per minute):
        wpm_reduce_support_above: Sufficient WPM above this level supports
            a reduce-support recommendation (used alongside accuracy).
        wpm_increase_support_below: Fluency below this level supports an
            increase-support recommendation (used alongside accuracy).
        wpm_increase_difficulty_above: Sufficient WPM above this level is one
            prerequisite for an increase-difficulty recommendation.

    Hesitation thresholds (rate per attempted word):
        hesitation_increase_support_above: High hesitation rate supports
            an increase-support recommendation.
        hesitation_reduce_support_below: Low hesitation rate supports a
            reduce-support recommendation (used alongside accuracy and WPM).

    Evidence requirements:
        min_sessions_for_recommendation: Minimum completed sessions required
            before any difficulty or support change is recommended. Fewer
            sessions always yield insufficient_evidence.
    """

    version_label: str = "v0.1-research-heuristic"

    # Accuracy thresholds
    accuracy_increase_support_below: float = 0.75
    accuracy_reduce_support_above: float = 0.90
    accuracy_increase_difficulty_above: float = 0.92
    accuracy_decrease_difficulty_below: float = 0.70
    accuracy_borderline_band: float = 0.03

    # WPM thresholds
    wpm_reduce_support_above: float = 80.0
    wpm_increase_support_below: float = 50.0
    wpm_increase_difficulty_above: float = 90.0

    # Hesitation thresholds (rate per word)
    hesitation_increase_support_above: float = 0.10
    hesitation_reduce_support_below: float = 0.04

    # Evidence requirements
    min_sessions_for_recommendation: int = 3

    def __post_init__(self) -> None:
        if self.min_sessions_for_recommendation < 1:
            raise ValueError("min_sessions_for_recommendation must be >= 1")
        if not (0.0 <= self.accuracy_increase_support_below <= 1.0):
            raise ValueError("accuracy_increase_support_below must be in [0.0, 1.0]")
        if not (0.0 <= self.accuracy_reduce_support_above <= 1.0):
            raise ValueError("accuracy_reduce_support_above must be in [0.0, 1.0]")
        if not (0.0 <= self.accuracy_increase_difficulty_above <= 1.0):
            raise ValueError("accuracy_increase_difficulty_above must be in [0.0, 1.0]")
        if not (0.0 <= self.accuracy_decrease_difficulty_below <= 1.0):
            raise ValueError("accuracy_decrease_difficulty_below must be in [0.0, 1.0]")
        if self.accuracy_borderline_band < 0.0:
            raise ValueError("accuracy_borderline_band must be non-negative")
        if self.wpm_reduce_support_above < 0.0:
            raise ValueError("wpm_reduce_support_above must be non-negative")
        if self.wpm_increase_support_below < 0.0:
            raise ValueError("wpm_increase_support_below must be non-negative")
        if self.wpm_increase_difficulty_above < 0.0:
            raise ValueError("wpm_increase_difficulty_above must be non-negative")
        if self.hesitation_increase_support_above < 0.0:
            raise ValueError("hesitation_increase_support_above must be non-negative")
        if self.hesitation_reduce_support_below < 0.0:
            raise ValueError("hesitation_reduce_support_below must be non-negative")


# ---------------------------------------------------------------------------
# Decision inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SupportPreferences:
    """Current configured reading-support preferences for the learner.

    Mirrors the configurable fields of LearnerReadingSupportSettings without
    coupling adaptation logic to ORM or database types.
    """

    enable_speech_cues: bool = True
    speech_rate_multiplier: float = 1.00
    enable_syllable_assistance: bool = True
    enable_phoneme_breakdown: bool = True
    enable_visual_pacing: bool = False
    visual_pacing_rate_wpm: int | None = None
    enable_line_focus: bool = False
    simplification_level: int = 1
    pause_threshold_ms: int = 2500

    def __post_init__(self) -> None:
        if not (1 <= self.simplification_level <= 5):
            raise ValueError(f"simplification_level must be 1–5, got {self.simplification_level}")
        if not (0.50 <= self.speech_rate_multiplier <= 2.00):
            raise ValueError(
                f"speech_rate_multiplier must be in [0.50, 2.00], got {self.speech_rate_multiplier}"
            )
        if not (1000 <= self.pause_threshold_ms <= 10000):
            raise ValueError(
                f"pause_threshold_ms must be in [1000, 10000], got {self.pause_threshold_ms}"
            )
        if self.visual_pacing_rate_wpm is not None and not (
            20 <= self.visual_pacing_rate_wpm <= 300
        ):
            raise ValueError(
                "visual_pacing_rate_wpm must be in [20, 300] when provided, "
                f"got {self.visual_pacing_rate_wpm}"
            )


@dataclass(frozen=True, slots=True)
class AdaptationInput:
    """Immutable, privacy-conscious input for a single adaptation decision.

    Contains only anonymised educational metrics and configuration state —
    no learner names, birth dates, diagnoses, raw audio, or document contents.

    Attributes:
        current_difficulty_tier: The tier at which sessions were conducted.
        current_support_mode: The active support mode for those sessions.
        manual_override_locked: True when an authorised adult has locked
            support preferences; implies advisory-only output.
        support_preferences: Current configured support settings.

        mean_accuracy: Mean decoding accuracy across valid sessions (None if
            no valid accuracy measurements exist).
        mean_wpm: Mean reading pace in words per minute across valid sessions
            (None if unmeasured or insufficient active duration).
        mean_hesitation_rate_per_word: Mean hesitation rate per attempted word
            across sessions where hesitation was instrumented (None if no
            instrumented sessions).
        mean_engagement_score: Mean experimental engagement heuristic score
            (None if unmeasured). NOTE: must NOT independently trigger a
            difficulty decrease; treated as corroborating evidence only.

        session_count: Number of completed, valid sessions providing the metrics.
        evidence_window_sufficient: True when session_count meets the configured
            minimum for the supplied thresholds.
    """

    current_difficulty_tier: str
    current_support_mode: str
    manual_override_locked: bool
    support_preferences: SupportPreferences

    # Aggregated educational metrics (all optional — missing ≠ zero)
    mean_accuracy: float | None
    mean_wpm: float | None
    mean_hesitation_rate_per_word: float | None
    mean_engagement_score: float | None  # corroborating evidence only

    session_count: int
    evidence_window_sufficient: bool

    def __post_init__(self) -> None:
        if self.current_difficulty_tier not in _DIFFICULTY_ORDER:
            raise ValueError(
                "current_difficulty_tier must be one of "
                f"{tuple(_DIFFICULTY_ORDER)}, got {self.current_difficulty_tier!r}"
            )
        if self.current_support_mode not in _SUPPORT_MODES:
            raise ValueError(
                f"current_support_mode must be one of {_SUPPORT_MODES}, "
                f"got {self.current_support_mode!r}"
            )
        if self.session_count < 0:
            raise ValueError(f"session_count cannot be negative, got {self.session_count}")

        bounded_metrics = (
            ("mean_accuracy", self.mean_accuracy),
            ("mean_engagement_score", self.mean_engagement_score),
        )
        for name, value in bounded_metrics:
            if value is not None and (not isfinite(value) or not 0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be finite and in [0.0, 1.0], got {value}")

        nonnegative_metrics = (
            ("mean_wpm", self.mean_wpm),
            ("mean_hesitation_rate_per_word", self.mean_hesitation_rate_per_word),
        )
        for name, value in nonnegative_metrics:
            if value is not None and (not isfinite(value) or value < 0.0):
                raise ValueError(f"{name} must be finite and non-negative, got {value}")


# ---------------------------------------------------------------------------
# Decision outputs
# ---------------------------------------------------------------------------

AdaptationAction = Literal[
    "maintain",
    "increase_support",
    "reduce_support",
    "increase_difficulty",
    "decrease_difficulty",
    "insufficient_evidence",
]


@dataclass(frozen=True, slots=True)
class SupportAdjustment:
    """A single recommended change to a learner support preference.

    Every adjustment carries its reason code and plain-language explanation.
    """

    preference_field: str
    suggested_value: object
    reason_code: str
    explanation: str


@dataclass(frozen=True, slots=True)
class DecisionEvidence:
    """Input metric values and threshold references supporting a specific decision.

    Provides full reproducibility: given the same versioned inputs and thresholds,
    any decision can be independently verified from this evidence record.
    """

    metric_name: str
    measured_value: float | None
    threshold_used: float | None
    comparison: str  # e.g. "< 0.75", ">= 0.92", "not available"
    contributed: bool  # True when this metric contributed to the action taken


@dataclass(frozen=True, slots=True)
class AdaptationDecision:
    """Immutable, fully explainable adaptation recommendation.

    IMPORTANT: safe_to_apply_automatically is ALWAYS False in this milestone.
    No output from this engine authorises automatic mutation of learner settings.

    Attributes:
        recommended_difficulty_tier: The recommended tier (may equal current).
        recommended_support_mode: The recommended support mode (may equal current).
        support_adjustments: Specific preference changes that may help the learner.
        action: Machine-readable summary of the recommended action.
        reason_codes: Sorted tuple of machine-readable reason identifiers.
        explanations: Sorted tuple of age-appropriate plain-language explanations.
        evidence: Tuple of evidence records for each considered metric.
        rule_id: Identifier of the specific rule that produced this action.
        rule_set_version: Version of the rule set and thresholds used.
        is_advisory: Always True — this recommendation requires human review.
        blocked_by_manual_override: True when manual override or lock suppressed
            a stronger recommendation.
        safe_to_apply_automatically: Always False in Milestone 4A.
        disclaimer: Non-clinical research disclaimer.
    """

    recommended_difficulty_tier: str
    recommended_support_mode: str
    support_adjustments: tuple[SupportAdjustment, ...]
    action: AdaptationAction
    reason_codes: tuple[str, ...]
    explanations: tuple[str, ...]
    evidence: tuple[DecisionEvidence, ...]
    rule_id: str
    rule_set_version: str
    is_advisory: bool
    blocked_by_manual_override: bool
    safe_to_apply_automatically: bool
    disclaimer: str


# ---------------------------------------------------------------------------
# Internal helper — borderline detection
# ---------------------------------------------------------------------------


def _is_borderline(value: float, threshold: float, band: float) -> bool:
    """Return True when value is within ±band of threshold (borderline zone)."""
    return abs(value - threshold) <= band


# ---------------------------------------------------------------------------
# Internal helper — build evidence record
# ---------------------------------------------------------------------------


def _evidence(
    metric_name: str,
    measured_value: float | None,
    threshold_used: float | None,
    comparison: str,
    contributed: bool,
) -> DecisionEvidence:
    return DecisionEvidence(
        metric_name=metric_name,
        measured_value=measured_value,
        threshold_used=threshold_used,
        comparison=comparison,
        contributed=contributed,
    )


# ---------------------------------------------------------------------------
# Internal helper — fixed-mode decision
# ---------------------------------------------------------------------------


def _fixed_mode_decision(
    inp: AdaptationInput,
    thresholds: AdaptationThresholds,
) -> AdaptationDecision:
    """Return a transparent fixed-baseline-mode advisory decision."""
    return AdaptationDecision(
        recommended_difficulty_tier=inp.current_difficulty_tier,
        recommended_support_mode=inp.current_support_mode,
        support_adjustments=(),
        action="maintain",
        reason_codes=("baseline_fixed_mode",),
        explanations=(
            "This learner is using the fixed baseline support configuration. "
            "Adaptive recommendations are not applied in fixed-baseline mode.",
        ),
        evidence=(),
        rule_id="FIXED_MODE_PRESERVE",
        rule_set_version=thresholds.version_label,
        is_advisory=True,
        blocked_by_manual_override=False,
        safe_to_apply_automatically=False,
        disclaimer=NON_CLINICAL_ADAPTATION_DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# Internal helper — manual-override decision
# ---------------------------------------------------------------------------


def _manual_override_decision(
    inp: AdaptationInput,
    thresholds: AdaptationThresholds,
    locked: bool,
) -> AdaptationDecision:
    """Return a transparent manual-override advisory decision."""
    if locked:
        explanation = (
            "An authorised adult has locked the support preferences for this learner. "
            "Adaptive recommendations are shown for information only and cannot be "
            "applied automatically."
        )
        reason = "manual_override_locked"
    else:
        explanation = (
            "The learner or an authorised adult controls the current support settings. "
            "Adaptive recommendations are shown for information only."
        )
        reason = "manual_override_active"

    return AdaptationDecision(
        recommended_difficulty_tier=inp.current_difficulty_tier,
        recommended_support_mode=inp.current_support_mode,
        support_adjustments=(),
        action="maintain",
        reason_codes=(reason,),
        explanations=(explanation,),
        evidence=(),
        rule_id="MANUAL_OVERRIDE_PRESERVE",
        rule_set_version=thresholds.version_label,
        is_advisory=True,
        blocked_by_manual_override=True,
        safe_to_apply_automatically=False,
        disclaimer=NON_CLINICAL_ADAPTATION_DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# Internal helper — insufficient evidence decision
# ---------------------------------------------------------------------------


def _insufficient_evidence_decision(
    inp: AdaptationInput,
    thresholds: AdaptationThresholds,
) -> AdaptationDecision:
    """Return an insufficient-evidence advisory decision with session count context."""
    if inp.session_count < thresholds.min_sessions_for_recommendation:
        reason_codes = ("insufficient_session_count",)
        explanation = (
            f"Not enough completed reading sessions are available to make a reliable "
            f"recommendation (found {inp.session_count}, need at least "
            f"{thresholds.min_sessions_for_recommendation}). "
            f"Continuing to gather reading session data before making adjustments."
        )
        evidence = (
            _evidence(
                "session_count",
                float(inp.session_count),
                float(thresholds.min_sessions_for_recommendation),
                f"< {thresholds.min_sessions_for_recommendation}",
                contributed=True,
            ),
        )
    else:
        reason_codes = ("insufficient_evidence_window",)
        explanation = (
            "The available sessions do not yet form a sufficiently consistent evidence "
            "window for an adaptation recommendation. Continuing to gather comparable "
            "reading sessions before making adjustments."
        )
        evidence = (
            _evidence(
                "evidence_window_sufficient",
                0.0,
                1.0,
                "is false",
                contributed=True,
            ),
        )
    return AdaptationDecision(
        recommended_difficulty_tier=inp.current_difficulty_tier,
        recommended_support_mode=inp.current_support_mode,
        support_adjustments=(),
        action="insufficient_evidence",
        reason_codes=reason_codes,
        explanations=(explanation,),
        evidence=evidence,
        rule_id="INSUFFICIENT_EVIDENCE",
        rule_set_version=thresholds.version_label,
        is_advisory=True,
        blocked_by_manual_override=False,
        safe_to_apply_automatically=False,
        disclaimer=NON_CLINICAL_ADAPTATION_DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# Internal — difficulty-change rules (adaptive mode only)
# ---------------------------------------------------------------------------


def _evaluate_difficulty(
    inp: AdaptationInput,
    thresholds: AdaptationThresholds,
) -> tuple[
    AdaptationAction,
    list[str],
    list[str],
    list[DecisionEvidence],
    str,
]:
    """Evaluate difficulty-tier change rules.

    Returns (action, reason_codes, explanations, evidence_list, rule_id).

    Rules (in priority order):
        DECREASE_DIFFICULTY: accuracy below threshold AND (WPM below threshold
            OR hesitation above threshold) — must not be in lowest tier already.
        INCREASE_DIFFICULTY: accuracy above threshold AND (WPM above threshold
            OR hesitation below threshold when available) — must not be in
            highest tier already.
        MAINTAIN: borderline accuracy OR contradictory indicators.

    Safety:
        - Borderline accuracy → maintain (conservative bias).
        - Only one tier step allowed per decision.
        - Engagement score alone cannot trigger difficulty decrease.
        - Missing WPM/hesitation treated as unavailable, not as zero.
    """
    acc = inp.mean_accuracy
    wpm = inp.mean_wpm
    hes = inp.mean_hesitation_rate_per_word
    tier_idx = _tier_index(inp.current_difficulty_tier)

    evidence: list[DecisionEvidence] = []
    reason_codes: list[str] = []
    explanations: list[str] = []

    # Build evidence records for each considered metric
    def acc_ev(contributed: bool) -> DecisionEvidence:
        if acc is None:
            return _evidence("mean_accuracy", None, None, "not available", contributed)
        return _evidence(
            "mean_accuracy",
            acc,
            thresholds.accuracy_decrease_difficulty_below
            if contributed and acc < thresholds.accuracy_increase_difficulty_above
            else thresholds.accuracy_increase_difficulty_above,
            f"= {acc:.4f}",
            contributed,
        )

    def wpm_ev(threshold: float, contributed: bool) -> DecisionEvidence:
        if wpm is None:
            return _evidence("mean_wpm", None, threshold, "not available", contributed)
        return _evidence("mean_wpm", wpm, threshold, f"= {wpm:.2f}", contributed)

    def hes_ev(threshold: float, contributed: bool) -> DecisionEvidence:
        if hes is None:
            return _evidence(
                "mean_hesitation_rate_per_word", None, threshold, "not available", contributed
            )
        return _evidence(
            "mean_hesitation_rate_per_word", hes, threshold, f"= {hes:.4f}", contributed
        )

    # ---- Rule: DECREASE DIFFICULTY ----
    if acc is not None and (
        acc < thresholds.accuracy_decrease_difficulty_below
        or _is_borderline(
            acc, thresholds.accuracy_decrease_difficulty_below, thresholds.accuracy_borderline_band
        )
    ):
        # Borderline check for decrease threshold
        if _is_borderline(
            acc, thresholds.accuracy_decrease_difficulty_below, thresholds.accuracy_borderline_band
        ):
            evidence.append(
                _evidence(
                    "mean_accuracy",
                    acc,
                    thresholds.accuracy_decrease_difficulty_below,
                    f"= {acc:.4f} (borderline near threshold "
                    f"{thresholds.accuracy_decrease_difficulty_below:.2f})",
                    contributed=False,
                )
            )
            return (
                "maintain",
                ["borderline_accuracy_decrease_threshold"],
                [
                    "Recent reading accuracy is close to the practice support threshold. "
                    "Monitoring a few more sessions before adjusting difficulty."
                ],
                evidence,
                "BORDERLINE_ACCURACY_DECREASE",
            )

        # Need corroborating evidence from WPM or hesitation (engagement alone is not enough)
        low_wpm = wpm is not None and wpm < thresholds.wpm_increase_support_below
        high_hes = hes is not None and hes > thresholds.hesitation_increase_support_above

        if tier_idx > 0 and (low_wpm or high_hes):
            # One tier step down
            reason_codes.append("low_accuracy_with_corroboration")
            explanations.append(
                f"Recent reading accuracy ({acc:.0%}) is below the configured practice "
                f"threshold ({thresholds.accuracy_decrease_difficulty_below:.0%}), "
                f"and other reading indicators also suggest the current level may be "
                f"challenging. Trying the previous difficulty level may help."
            )
            evidence.extend(
                [
                    _evidence(
                        "mean_accuracy",
                        acc,
                        thresholds.accuracy_decrease_difficulty_below,
                        f"< {thresholds.accuracy_decrease_difficulty_below:.2f}",
                        contributed=True,
                    ),
                    wpm_ev(thresholds.wpm_increase_support_below, contributed=low_wpm),
                    hes_ev(thresholds.hesitation_increase_support_above, contributed=high_hes),
                ]
            )
            return (
                "decrease_difficulty",
                sorted(reason_codes),
                sorted(explanations),
                evidence,
                "DECREASE_DIFFICULTY_LOW_ACC_CORROBORATED",
            )
        elif tier_idx == 0:
            # Already at lowest tier — cannot decrease further
            reason_codes.append("already_at_lowest_difficulty_tier")
            explanations.append(
                f"Recent reading accuracy ({acc:.0%}) is below the practice threshold, "
                f"but this learner is already at the earliest difficulty level. "
                f"Consider increasing support instead."
            )
            evidence.append(
                _evidence(
                    "mean_accuracy",
                    acc,
                    thresholds.accuracy_decrease_difficulty_below,
                    f"< {thresholds.accuracy_decrease_difficulty_below:.2f}",
                    contributed=True,
                )
            )
            return (
                "maintain",
                sorted(reason_codes),
                sorted(explanations),
                evidence,
                "AT_LOWEST_TIER_LOW_ACC",
            )
        else:
            # Low accuracy but no corroborating evidence — conservative maintain
            evidence.append(
                _evidence(
                    "mean_accuracy",
                    acc,
                    thresholds.accuracy_decrease_difficulty_below,
                    f"< {thresholds.accuracy_decrease_difficulty_below:.2f}",
                    contributed=False,
                )
            )
            return (
                "maintain",
                ["low_accuracy_no_corroboration"],
                [
                    f"Recent reading accuracy ({acc:.0%}) is below the practice threshold, "
                    f"but other reading pace and hesitation data are not available to confirm "
                    f"the pattern. Monitoring further before adjusting."
                ],
                evidence,
                "LOW_ACC_NO_CORROBORATION",
            )

    # ---- Rule: INCREASE DIFFICULTY ----
    if acc is not None and _is_borderline(
        acc, thresholds.accuracy_increase_difficulty_above, thresholds.accuracy_borderline_band
    ):
        evidence.append(
            _evidence(
                "mean_accuracy",
                acc,
                thresholds.accuracy_increase_difficulty_above,
                f"= {acc:.4f} (borderline near threshold "
                f"{thresholds.accuracy_increase_difficulty_above:.2f})",
                contributed=False,
            )
        )
        return (
            "maintain",
            ["borderline_accuracy_increase_threshold"],
            [
                "Recent reading accuracy is close to the difficulty progression threshold. "
                "Monitoring a few more sessions before suggesting a harder level."
            ],
            evidence,
            "BORDERLINE_ACCURACY_INCREASE",
        )

    if acc is not None and acc > thresholds.accuracy_increase_difficulty_above:
        # Need corroborating fluency evidence
        good_wpm = wpm is not None and wpm > thresholds.wpm_increase_difficulty_above
        low_hes = hes is not None and hes < thresholds.hesitation_reduce_support_below

        if tier_idx < len(_DIFFICULTY_ORDER) - 1 and (good_wpm or low_hes):
            # One tier step up — final tier is computed in recommend_adaptation
            reason_codes.append("high_accuracy_with_fluency_evidence")
            explanations.append(
                f"Recent sessions show consistent reading accuracy ({acc:.0%}) above the "
                f"configured progression threshold "
                f"({thresholds.accuracy_increase_difficulty_above:.0%}), "
                f"and reading pace supports trying the next difficulty level."
            )
            evidence.extend(
                [
                    _evidence(
                        "mean_accuracy",
                        acc,
                        thresholds.accuracy_increase_difficulty_above,
                        f"> {thresholds.accuracy_increase_difficulty_above:.2f}",
                        contributed=True,
                    ),
                    wpm_ev(thresholds.wpm_increase_difficulty_above, contributed=good_wpm),
                    hes_ev(thresholds.hesitation_reduce_support_below, contributed=low_hes),
                ]
            )
            return (
                "increase_difficulty",
                sorted(reason_codes),
                sorted(explanations),
                evidence,
                "INCREASE_DIFFICULTY_HIGH_ACC",
            )
        elif tier_idx == len(_DIFFICULTY_ORDER) - 1:
            reason_codes.append("already_at_highest_difficulty_tier")
            explanations.append(
                f"Recent reading accuracy ({acc:.0%}) is above the progression threshold. "
                f"This learner is already at the most advanced difficulty level available."
            )
            evidence.append(
                _evidence(
                    "mean_accuracy",
                    acc,
                    thresholds.accuracy_increase_difficulty_above,
                    f"> {thresholds.accuracy_increase_difficulty_above:.2f}",
                    contributed=True,
                )
            )
            return (
                "maintain",
                sorted(reason_codes),
                sorted(explanations),
                evidence,
                "AT_HIGHEST_TIER_HIGH_ACC",
            )
        else:
            # High accuracy without corroborating fluency evidence — conservative maintain
            evidence.extend(
                [
                    _evidence(
                        "mean_accuracy",
                        acc,
                        thresholds.accuracy_increase_difficulty_above,
                        f"> {thresholds.accuracy_increase_difficulty_above:.2f}",
                        contributed=False,
                    ),
                    wpm_ev(thresholds.wpm_increase_difficulty_above, contributed=False),
                    hes_ev(thresholds.hesitation_reduce_support_below, contributed=False),
                ]
            )
            if wpm is None:
                reason = "high_accuracy_without_fluency_corroboration"
                explanation = (
                    f"Recent reading accuracy ({acc:.0%}) is above the progression threshold, "
                    "but reading pace data is unavailable and the other available fluency "
                    "indicators do not support a difficulty increase. Continuing at the "
                    "current level while gathering more evidence."
                )
                rule_id = "HIGH_ACC_NO_FLUENCY_CORROBORATION"
            else:
                reason = "high_accuracy_wpm_below_fluency_threshold"
                explanation = (
                    f"Recent reading accuracy ({acc:.0%}) is above the progression threshold, "
                    f"but reading pace ({wpm:.1f} WPM) has not yet reached the fluency "
                    f"threshold ({thresholds.wpm_increase_difficulty_above:.0f} WPM). "
                    "Continuing at the current level to build pace."
                )
                rule_id = "HIGH_ACC_LOW_WPM"
            return (
                "maintain",
                [reason],
                [explanation],
                evidence,
                rule_id,
            )

    # ---- No difficulty change warranted ----
    evidence.append(
        _evidence(
            "mean_accuracy",
            acc,
            None,
            f"= {acc:.4f}" if acc is not None else "not available",
            contributed=False,
        )
    )
    return (
        "maintain",
        ["metrics_within_practice_range"],
        [
            "Recent reading performance is within the expected practice range. "
            "Continuing at the current difficulty level."
        ],
        evidence,
        "MAINTAIN_WITHIN_RANGE",
    )


# ---------------------------------------------------------------------------
# Internal — support-mode / support-preference rules (adaptive mode only)
# ---------------------------------------------------------------------------


def _evaluate_support(
    inp: AdaptationInput,
    thresholds: AdaptationThresholds,
) -> tuple[
    AdaptationAction | None,
    list[str],
    list[str],
    list[DecisionEvidence],
    list[SupportAdjustment],
    str,
]:
    """Evaluate support-level change rules.

    Returns (action_or_None, reason_codes, explanations, evidence_list,
             adjustments, rule_id).
    action_or_None is None when no support change is recommended.
    """
    acc = inp.mean_accuracy
    wpm = inp.mean_wpm
    hes = inp.mean_hesitation_rate_per_word
    prefs = inp.support_preferences

    evidence: list[DecisionEvidence] = []
    reason_codes: list[str] = []
    explanations: list[str] = []
    adjustments: list[SupportAdjustment] = []

    # ---- Increase support: low accuracy OR (low WPM + high hesitation) ----
    low_acc = acc is not None and acc < thresholds.accuracy_increase_support_below
    low_wpm = wpm is not None and wpm < thresholds.wpm_increase_support_below
    high_hes = hes is not None and hes > thresholds.hesitation_increase_support_above

    if low_acc or (low_wpm and high_hes):
        if acc is not None:
            evidence.append(
                _evidence(
                    "mean_accuracy",
                    acc,
                    thresholds.accuracy_increase_support_below,
                    f"< {thresholds.accuracy_increase_support_below:.2f}",
                    contributed=low_acc,
                )
            )
        if wpm is not None:
            evidence.append(
                _evidence(
                    "mean_wpm",
                    wpm,
                    thresholds.wpm_increase_support_below,
                    f"< {thresholds.wpm_increase_support_below:.1f}",
                    contributed=low_wpm,
                )
            )
        if hes is not None:
            evidence.append(
                _evidence(
                    "mean_hesitation_rate_per_word",
                    hes,
                    thresholds.hesitation_increase_support_above,
                    f"> {thresholds.hesitation_increase_support_above:.3f}",
                    contributed=high_hes,
                )
            )

        reason_codes.append("support_increase_indicated")
        if low_acc:
            explanations.append(
                "Recent reading accuracy is below the configured practice threshold, so "
                "additional reading support may help."
            )
        else:
            explanations.append(
                "Recent reading pace is below the configured fluency threshold and the "
                "hesitation rate is elevated, so additional reading support may help."
            )

        # Suggest specific support adjustments
        if not prefs.enable_speech_cues:
            adjustments.append(
                SupportAdjustment(
                    preference_field="enable_speech_cues",
                    suggested_value=True,
                    reason_code="enable_speech_cues_for_accuracy",
                    explanation="Enabling speech cues may help with word decoding.",
                )
            )
        if not prefs.enable_syllable_assistance:
            adjustments.append(
                SupportAdjustment(
                    preference_field="enable_syllable_assistance",
                    suggested_value=True,
                    reason_code="enable_syllable_assistance_for_accuracy",
                    explanation="Syllable assistance may support word recognition.",
                )
            )
        if prefs.simplification_level < 3:
            adjustments.append(
                SupportAdjustment(
                    preference_field="simplification_level",
                    suggested_value=min(prefs.simplification_level + 1, 5),
                    reason_code="increase_simplification_level",
                    explanation="Increasing the simplification level may reduce reading load.",
                )
            )

        return (
            "increase_support",
            sorted(reason_codes),
            sorted(explanations),
            evidence,
            adjustments,
            "INCREASE_SUPPORT_LOW_ACC_OR_FLUENCY",
        )

    # ---- Reduce support: high accuracy AND good WPM AND low hesitation ----
    high_acc = acc is not None and acc > thresholds.accuracy_reduce_support_above
    good_wpm = wpm is not None and wpm > thresholds.wpm_reduce_support_above
    low_hes = hes is not None and hes < thresholds.hesitation_reduce_support_below

    if high_acc and good_wpm and low_hes:
        if acc is not None:
            evidence.append(
                _evidence(
                    "mean_accuracy",
                    acc,
                    thresholds.accuracy_reduce_support_above,
                    f"> {thresholds.accuracy_reduce_support_above:.2f}",
                    contributed=True,
                )
            )
        if wpm is not None:
            evidence.append(
                _evidence(
                    "mean_wpm",
                    wpm,
                    thresholds.wpm_reduce_support_above,
                    f"> {thresholds.wpm_reduce_support_above:.1f}",
                    contributed=True,
                )
            )
        if hes is not None:
            evidence.append(
                _evidence(
                    "mean_hesitation_rate_per_word",
                    hes,
                    thresholds.hesitation_reduce_support_below,
                    f"< {thresholds.hesitation_reduce_support_below:.3f}",
                    contributed=low_hes,
                )
            )

        reason_codes.append("support_reduction_indicated")
        explanations.append(
            "Recent sessions show consistent accuracy and reading pace, "
            "so reducing support levels may be appropriate to help build independence."
        )

        # Suggest reducing simplification level if elevated
        if prefs.simplification_level > 1:
            adjustments.append(
                SupportAdjustment(
                    preference_field="simplification_level",
                    suggested_value=max(prefs.simplification_level - 1, 1),
                    reason_code="reduce_simplification_level",
                    explanation=(
                        "Reducing the simplification level slightly may build reading independence."
                    ),
                )
            )

        return (
            "reduce_support",
            sorted(reason_codes),
            sorted(explanations),
            evidence,
            adjustments,
            "REDUCE_SUPPORT_HIGH_ACC_GOOD_FLUENCY",
        )

    return None, [], [], [], [], "NO_SUPPORT_CHANGE"


# ---------------------------------------------------------------------------
# Public API — main decision function
# ---------------------------------------------------------------------------


def recommend_adaptation(
    inp: AdaptationInput,
    thresholds: AdaptationThresholds | None = None,
) -> AdaptationDecision:
    """Produce a fully explainable, advisory-only reading-support recommendation.

    This is the sole public entry point for the adaptation decision engine.

    Evaluation order (short-circuits on first applicable rule):
        1. Fixed baseline mode  → FIXED_MODE_PRESERVE (no change)
        2. Manual override      → MANUAL_OVERRIDE_PRESERVE (no change)
        3. Insufficient evidence → INSUFFICIENT_EVIDENCE (no change)
        4. Adaptive rules       → difficulty and support evaluation

    Returns:
        AdaptationDecision with safe_to_apply_automatically=False always.

    Invariants:
        - No database access, ORM operations, or HTTP calls.
        - No mutation of input objects.
        - Identical inputs + identical thresholds → identical output.
        - Every decision includes reason codes, explanations, and evidence.
        - safe_to_apply_automatically is ALWAYS False.
        - is_advisory is ALWAYS True.
    """
    applied_thresholds = thresholds if thresholds is not None else AdaptationThresholds()

    # Rule 1: Fixed baseline mode
    if inp.current_support_mode == "baseline_fixed":
        return _fixed_mode_decision(inp, applied_thresholds)

    # Rule 2: Manual override or locked
    if inp.current_support_mode == "manual_override" or inp.manual_override_locked:
        return _manual_override_decision(inp, applied_thresholds, locked=inp.manual_override_locked)

    # Rule 3: Insufficient evidence
    if (
        not inp.evidence_window_sufficient
        or inp.session_count < applied_thresholds.min_sessions_for_recommendation
    ):
        return _insufficient_evidence_decision(inp, applied_thresholds)

    # Rule 4: Adaptive evaluation — evaluate difficulty first, then support
    diff_action, diff_reasons, diff_exps, diff_ev, diff_rule = _evaluate_difficulty(
        inp, applied_thresholds
    )

    sup_action, sup_reasons, sup_exps, sup_ev, sup_adjustments, sup_rule = _evaluate_support(
        inp, applied_thresholds
    )

    # Merge: difficulty changes and explicit maintain decisions (borderline, boundary,
    # contradictory indicators) take precedence over support changes. Support adjustments
    # are evaluated when difficulty is within the normal practice range.
    final_action: AdaptationAction
    if diff_action in ("decrease_difficulty", "increase_difficulty"):
        final_action = diff_action
        final_reasons = diff_reasons
        final_exps = diff_exps
        final_ev = diff_ev
        final_adjustments: tuple[SupportAdjustment, ...] = ()
        final_rule = diff_rule
    elif diff_rule != "MAINTAIN_WITHIN_RANGE":
        # Preserve explicit maintain decisions from difficulty evaluation.
        final_action = "maintain"
        final_reasons = diff_reasons
        final_exps = diff_exps
        final_ev = diff_ev
        final_adjustments = ()
        final_rule = diff_rule
    elif sup_action is not None and sup_action != "maintain":
        final_action = sup_action
        final_reasons = sup_reasons
        final_exps = sup_exps
        final_ev = sup_ev
        final_adjustments = tuple(sorted(sup_adjustments, key=lambda a: a.preference_field))
        final_rule = sup_rule
    else:
        # Maintain — merge evidence from both evaluations
        final_action = "maintain"
        final_reasons = sorted(set(diff_reasons + sup_reasons))
        final_exps = sorted(set(diff_exps + sup_exps))
        final_ev = diff_ev + sup_ev
        final_adjustments = ()
        final_rule = diff_rule if diff_rule != "MAINTAIN_WITHIN_RANGE" else sup_rule

    # Determine recommended tiers/modes
    if final_action == "increase_difficulty":
        tier_idx = _tier_index(inp.current_difficulty_tier)
        recommended_tier = _DIFFICULTY_ORDER[min(tier_idx + 1, len(_DIFFICULTY_ORDER) - 1)]
    elif final_action == "decrease_difficulty":
        tier_idx = _tier_index(inp.current_difficulty_tier)
        recommended_tier = _DIFFICULTY_ORDER[max(tier_idx - 1, 0)]
    else:
        recommended_tier = inp.current_difficulty_tier

    return AdaptationDecision(
        recommended_difficulty_tier=recommended_tier,
        recommended_support_mode=inp.current_support_mode,
        support_adjustments=final_adjustments,
        action=final_action,
        reason_codes=tuple(sorted(final_reasons)),
        explanations=tuple(sorted(final_exps)),
        evidence=tuple(final_ev),
        rule_id=final_rule,
        rule_set_version=applied_thresholds.version_label,
        is_advisory=True,
        blocked_by_manual_override=False,
        safe_to_apply_automatically=False,
        disclaimer=NON_CLINICAL_ADAPTATION_DISCLAIMER,
    )
