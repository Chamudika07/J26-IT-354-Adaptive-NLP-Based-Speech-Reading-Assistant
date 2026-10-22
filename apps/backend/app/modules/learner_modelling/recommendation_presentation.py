"""Private pure advisory presentation, not a role authorization or public API contract.

Caller must bind settings, evidence and decision to one authorized learner/window.
No identities, role selectors, repository objects or model services are accepted.
"""

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt

from app.modules.learner_modelling.adaptation import AdaptationAction, AdaptationDecision
from app.modules.learner_modelling.adaptation_mapping import (
    CompletedSessionEvidence,
    map_longitudinal_partition_to_adaptation_input,
)
from app.modules.learner_modelling.analytics import (
    DifficultyTier,
    PartitionKey,
    SupportMode,
    TaskType,
)
from app.modules.learner_modelling.decision_snapshots import (
    AdaptationDecisionOutput,
    Explanation,
    PreferenceField,
)
from app.modules.learner_modelling.recommendation_composition import (
    _compose_recommendation,
    _map_support_preferences,
    _validated_settings,
)
from app.modules.learner_modelling.schemas import SupportSettingsRead


class InvalidRecommendationPresentation(ValueError):
    def __init__(self) -> None:
        super().__init__("Recommendation presentation is invalid or inconsistent.")


class _FrozenPresentation(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", from_attributes=False)


class CurrentSupportSummary(_FrozenPresentation):
    """Configured summary, not observed session context or full learner settings."""

    difficulty_tier: DifficultyTier
    support_mode: SupportMode
    manual_override_locked: bool


class ProposedSupportAdjustment(_FrozenPresentation):
    preference_field: PreferenceField
    proposed_value: StrictBool | StrictInt
    explanation: Explanation


class AdvisoryChanges(_FrozenPresentation):
    """Only differences proposed for review; never an applied settings record."""

    difficulty_tier: DifficultyTier | None
    support_mode: SupportMode | None
    support_adjustments: tuple[ProposedSupportAdjustment, ...]


class RecommendationPresentation(_FrozenPresentation):
    status: Literal["settings_unavailable", "recommendation_unavailable", "available"]
    current: CurrentSupportSummary | None
    task_type: TaskType | None
    action: AdaptationAction | None
    proposed: AdvisoryChanges | None
    explanations: tuple[Explanation, ...]
    limitations: tuple[Explanation, ...]
    evidence_state: Literal["unavailable", "sufficient", "insufficient"]
    fixed_baseline: bool | None
    manual_override_active: bool | None
    manual_control_prevents_adjustment: bool | None
    blocked_by_manual_override: bool | None
    is_advisory: Literal[True] = True
    automatic_application_allowed: Literal[False] = False
    changes_applied: Literal[False] = False
    disclaimer: Explanation | None


def _present_recommendation(
    settings: SupportSettingsRead | None,
    decision: AdaptationDecision | None,
    *,
    evidence: CompletedSessionEvidence | None = None,
    partition: PartitionKey | None = None,
) -> RecommendationPresentation:
    """Minimize a context-verified engine decision without new claims or application.

    None settings/decision are explicit unavailable outcomes, not maintain/defaults.
    Reader errors must propagate before this pure function is invoked. Invalid
    settings are rejected through the existing settings validator. Available decisions
    require matching verified evidence/context and unchanged default engine rules.
    """
    current = _validated_settings(settings)
    if current is None:
        if decision is not None or partition is not None or evidence is not None:
            raise InvalidRecommendationPresentation()
        return RecommendationPresentation(
            status="settings_unavailable",
            current=None,
            task_type=None,
            action=None,
            proposed=None,
            explanations=(),
            limitations=(),
            evidence_state="unavailable",
            fixed_baseline=None,
            manual_override_active=None,
            manual_control_prevents_adjustment=None,
            blocked_by_manual_override=None,
            disclaimer=None,
        )
    try:
        if partition is not None and (
            type(partition) is not PartitionKey
            or partition.difficulty_tier != current.default_difficulty_tier
            or partition.support_mode != current.support_mode
            or partition.task_type
            not in ("independent_reading", "assisted_read_aloud", "guided_echo_reading")
        ):
            raise InvalidRecommendationPresentation()
        summary = CurrentSupportSummary(
            difficulty_tier=current.default_difficulty_tier,
            support_mode=current.support_mode,
            manual_override_locked=current.manual_override_locked,
        )
        task_type = cast(TaskType, partition.task_type) if partition is not None else None
        fixed_baseline = current.support_mode == "baseline_fixed"
        manual_override_active = current.support_mode == "manual_override"
        manual_control_prevents_adjustment = (
            current.manual_override_locked or manual_override_active
        )
        if decision is None:
            return RecommendationPresentation(
                status="recommendation_unavailable",
                current=summary,
                task_type=task_type,
                action=None,
                proposed=None,
                explanations=(),
                limitations=(),
                evidence_state="unavailable",
                blocked_by_manual_override=None,
                disclaimer=None,
                fixed_baseline=fixed_baseline,
                manual_override_active=manual_override_active,
                manual_control_prevents_adjustment=manual_control_prevents_adjustment,
            )
        if (
            type(decision) is not AdaptationDecision
            or decision.is_advisory is not True
            or decision.safe_to_apply_automatically is not False
            or partition is None
            or evidence is None
        ):
            raise InvalidRecommendationPresentation()
        expected = _compose_recommendation(current, evidence, partition)
        if expected is None or decision != expected:
            raise InvalidRecommendationPresentation()
        validated = AdaptationDecisionOutput.from_decision(expected)
        preferences = _map_support_preferences(current)
        if preferences is None:
            raise InvalidRecommendationPresentation()
        adaptation = map_longitudinal_partition_to_adaptation_input(
            evidence,
            partition,
            support_preferences=preferences,
            manual_override_locked=current.manual_override_locked,
        )
        adjustments = tuple(
            ProposedSupportAdjustment(
                preference_field=item.preference_field,
                proposed_value=item.suggested_value,
                explanation=item.explanation,
            )
            for item in validated.support_adjustments
        )
        difficulty = (
            validated.recommended_difficulty_tier
            if validated.recommended_difficulty_tier != current.default_difficulty_tier
            else None
        )
        mode = (
            validated.recommended_support_mode
            if validated.recommended_support_mode != current.support_mode
            else None
        )
        proposed = (
            AdvisoryChanges(
                difficulty_tier=difficulty, support_mode=mode, support_adjustments=adjustments
            )
            if difficulty or mode or adjustments
            else None
        )
        return RecommendationPresentation(
            status="available",
            current=summary,
            task_type=task_type,
            action=validated.action,
            proposed=proposed,
            explanations=validated.explanations,
            limitations=validated.explanations
            if validated.action == "insufficient_evidence"
            else (),
            evidence_state="sufficient"
            if adaptation.evidence_window_sufficient
            else "insufficient",
            blocked_by_manual_override=validated.blocked_by_manual_override,
            disclaimer=validated.disclaimer,
            fixed_baseline=fixed_baseline,
            manual_override_active=manual_override_active,
            manual_control_prevents_adjustment=manual_control_prevents_adjustment,
        )
    except Exception:
        # Never reveal decision text, identifiers or raw validation/engine exceptions.
        raise InvalidRecommendationPresentation() from None
