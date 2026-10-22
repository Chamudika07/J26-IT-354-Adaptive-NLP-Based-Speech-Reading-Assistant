"""Private label adapter. No routing, authorization, persistence or application."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.learner_modelling.adaptation import AdaptationDecision
from app.modules.learner_modelling.adaptation_mapping import CompletedSessionEvidence
from app.modules.learner_modelling.analytics import PartitionKey
from app.modules.learner_modelling.recommendation_presentation import _present_recommendation
from app.modules.learner_modelling.schemas import SupportSettingsRead

TIERS = {"early": "beginner", "intermediate": "intermediate", "advanced": "advanced"}
MODES = {
    "baseline_fixed": "Fixed baseline",
    "adaptive": "Adaptive support",
    "manual_override": "Manual support",
}
ACTIONS = {
    "maintain": "Keep current support",
    "increase_support": "Try more support",
    "reduce_support": "Try less support",
    "increase_difficulty": "Try a harder reading level",
    "decrease_difficulty": "Try an easier reading level",
    "insufficient_evidence": "More reading evidence needed",
}


class MobileRecommendation(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    status: Literal["settings_unavailable", "recommendation_unavailable", "available"]
    task_type: str | None
    current: str | None
    action: str | None
    proposed: tuple[str, ...]
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_state: Literal["unavailable", "sufficient", "insufficient"]
    fixed_baseline: bool | None
    manual_override_active: bool | None
    global_lock: bool | None
    manual_control_prevents_adjustment: bool | None
    blocked_by_manual_override: bool | None
    advisory_only: Literal[True] = True
    changes_applied: Literal[False] = False
    automatic_application_allowed: Literal[False] = False
    disclaimer: str | None


def _mobile_recommendation(
    settings: SupportSettingsRead | None,
    decision: AdaptationDecision | None,
    *,
    evidence: CompletedSessionEvidence | None = None,
    partition: PartitionKey | None = None,
) -> MobileRecommendation:
    # Recheck the actual engine decision/context rather than trusting display text.
    view = _present_recommendation(settings, decision, evidence=evidence, partition=partition)
    proposed: list[str] = []
    if view.proposed:
        if view.proposed.difficulty_tier:
            proposed.append("Reading level: " + TIERS[view.proposed.difficulty_tier])
        if view.proposed.support_mode:
            proposed.append("Support: " + MODES[view.proposed.support_mode])
        for adjustment in view.proposed.support_adjustments:
            proposed.append(
                adjustment.preference_field.replace("_", " ")
                + ": "
                + str(adjustment.proposed_value)
                + ". "
                + adjustment.explanation
            )
    return MobileRecommendation(
        status=view.status,
        task_type=view.task_type,
        current=(TIERS[view.current.difficulty_tier] + " / " + MODES[view.current.support_mode])
        if view.current
        else None,
        action=ACTIONS[view.action] if view.action else None,
        proposed=tuple(proposed),
        reasons=view.explanations,
        limitations=view.limitations,
        evidence_state=view.evidence_state,
        fixed_baseline=view.fixed_baseline,
        manual_override_active=view.manual_override_active,
        global_lock=view.current.manual_override_locked if view.current else None,
        manual_control_prevents_adjustment=view.manual_control_prevents_adjustment,
        blocked_by_manual_override=view.blocked_by_manual_override,
        disclaimer=view.disclaimer,
    )
