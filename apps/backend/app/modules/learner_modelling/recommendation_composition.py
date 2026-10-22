"""Pure private composition; no retrieval, authorization, consent, writes or routes.

Caller must supply settings and completed evidence for the same already-authorized
learner/window. These identity-free types cannot establish that association. Explicit
partition selection remains trusted caller policy, never an end-user permission.
No production module calls this foundation. Missing settings are not defaults.
"""

from pydantic import ValidationError

from app.modules.learner_modelling.adaptation import (
    AdaptationDecision,
    AdaptationThresholds,
    SupportPreferences,
    recommend_adaptation,
)
from app.modules.learner_modelling.adaptation_mapping import (
    AdaptationMappingError,
    CompletedSessionEvidence,
    map_longitudinal_partition_to_adaptation_input,
)
from app.modules.learner_modelling.analytics import PartitionKey
from app.modules.learner_modelling.schemas import SupportSettingsRead
from app.modules.learner_modelling.support_settings import InvalidSupportSettings


def _validated_settings(settings: SupportSettingsRead | None) -> SupportSettingsRead | None:
    if settings is None:
        return None
    if type(settings) is not SupportSettingsRead:
        raise InvalidSupportSettings()
    try:
        # Pydantic model_copy/model_construct can bypass initial validation.
        return SupportSettingsRead.model_validate(
            settings.model_dump(mode="python", warnings=False)
        )
    except (ValidationError, ValueError, TypeError):
        raise InvalidSupportSettings() from None


def _map_support_preferences(settings: SupportSettingsRead | None) -> SupportPreferences | None:
    """Copy every approved preference explicitly; only Decimal speech rate becomes float."""
    current = _validated_settings(settings)
    if current is None:
        return None
    return SupportPreferences(
        enable_speech_cues=current.enable_speech_cues,
        speech_rate_multiplier=float(current.speech_rate_multiplier),
        enable_syllable_assistance=current.enable_syllable_assistance,
        enable_phoneme_breakdown=current.enable_phoneme_breakdown,
        enable_visual_pacing=current.enable_visual_pacing,
        visual_pacing_rate_wpm=current.visual_pacing_rate_wpm,
        enable_line_focus=current.enable_line_focus,
        simplification_level=current.simplification_level,
        pause_threshold_ms=current.pause_threshold_ms,
    )


def _compose_recommendation(
    settings: SupportSettingsRead | None,
    evidence: CompletedSessionEvidence,
    partition: PartitionKey,
) -> AdaptationDecision | None:
    """None means absent settings, not unlocked/maintain or a default recommendation.

    Refuse conflicting configured/observed difficulty or mode; do not overwrite either
    or invent a partition policy. Fixed/manual/lock precedence is the existing engine's
    responsibility, after verified evidence and context checks. Empty or invalid
    evidence still raises the existing mapping error, even for a locked setting.
    """
    current = _validated_settings(settings)
    if current is None:
        return None
    if not isinstance(partition, PartitionKey) or (
        partition.difficulty_tier != current.default_difficulty_tier
        or partition.support_mode != current.support_mode
    ):
        raise AdaptationMappingError("Configured settings and selected context do not match")
    preferences = _map_support_preferences(current)
    if preferences is None:  # A mapping failure is not evidence of an absent stored row.
        raise InvalidSupportSettings()
    thresholds = AdaptationThresholds()
    adaptation = map_longitudinal_partition_to_adaptation_input(
        evidence,
        partition,
        support_preferences=preferences,
        manual_override_locked=current.manual_override_locked,
        thresholds=thresholds,
    )
    return recommend_adaptation(adaptation, thresholds)
