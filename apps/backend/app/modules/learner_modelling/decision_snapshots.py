"""Pure, immutable contracts for explainable adaptation decision snapshots.

This module has no database, HTTP, authentication, consent-policy, or network
dependencies.  It records validated educational evidence and the advisory output
produced by :mod:`app.modules.learner_modelling.adaptation`.

The canonical representation deliberately preserves decimal values without
quantizing them to a future database scale.  The adaptation engine accepts finite
values beyond the scale currently used by reading-session persistence, so rounding
here could change a replayed threshold decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.schemas import Schema
from app.modules.learner_modelling.adaptation import (
    ADAPTATION_ENGINE_VERSION,
    AdaptationAction,
    AdaptationDecision,
    AdaptationInput,
    AdaptationThresholds,
    DecisionEvidence,
    SupportAdjustment,
    SupportPreferences,
)
from app.modules.learner_modelling.analytics import DifficultyTier, SupportMode, TaskType

SnapshotSchemaVersion = Literal["adaptation-evaluation-v1"]
SNAPSHOT_SCHEMA_VERSION: SnapshotSchemaVersion = "adaptation-evaluation-v1"

MAX_REASON_CODES = 16
MAX_EXPLANATIONS = 16
MAX_EVIDENCE_RECORDS = 16
MAX_SUPPORT_ADJUSTMENTS = 16

VersionLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
RuleIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Z][A-Z0-9_]{0,63}$"),
]
ReasonCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]{0,63}$"),
]
Explanation = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=28)]
Probability = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), allow_inf_nan=False, max_digits=28),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False, max_digits=28),
]

ActorKind = Literal["authenticated_user", "internal_service"]
PurposeCode = Literal["learning_support", "research_participation"]
MetricName = Literal[
    "mean_accuracy",
    "mean_wpm",
    "mean_hesitation_rate_per_word",
    "mean_engagement_score",
    "session_count",
    "evidence_window_sufficient",
]
PreferenceField = Literal[
    "enable_speech_cues",
    "speech_rate_multiplier",
    "enable_syllable_assistance",
    "enable_phoneme_breakdown",
    "enable_visual_pacing",
    "visual_pacing_rate_wpm",
    "enable_line_focus",
    "simplification_level",
    "pause_threshold_ms",
]


class FrozenSnapshotModel(Schema):
    """Strict immutable base for every nested snapshot contract."""

    model_config = ConfigDict(from_attributes=True, extra="forbid", frozen=True)


class SnapshotActor(FrozenSnapshotModel):
    """Provenance only; this contract never grants authorization."""

    kind: ActorKind
    initiating_user_id: UUID | None = None

    @model_validator(mode="after")
    def validate_actor_identity(self) -> SnapshotActor:
        if self.kind == "authenticated_user" and self.initiating_user_id is None:
            raise ValueError("authenticated_user requires initiating_user_id")
        if self.kind == "internal_service" and self.initiating_user_id is not None:
            raise ValueError("internal_service cannot claim an initiating user")
        return self


class PurposeContext(FrozenSnapshotModel):
    """Minimal result supplied by a future approved consent-policy service."""

    purpose_code: PurposeCode
    policy_version: VersionLabel
    evaluated_at: AwareDatetime


class AnalyticsVersions(FrozenSnapshotModel):
    """Versions of analytics that contributed a value to the evidence."""

    engagement_formula_version: VersionLabel | None = None


class SupportPreferencesSnapshot(FrozenSnapshotModel):
    """Only the support preferences consumed by the adaptation engine."""

    enable_speech_cues: bool
    speech_rate_multiplier: Annotated[
        Decimal,
        Field(
            ge=Decimal("0.50"),
            le=Decimal("2.00"),
            allow_inf_nan=False,
            max_digits=28,
        ),
    ]
    enable_syllable_assistance: bool
    enable_phoneme_breakdown: bool
    enable_visual_pacing: bool
    visual_pacing_rate_wpm: Annotated[int, Field(ge=20, le=300)] | None
    enable_line_focus: bool
    simplification_level: Annotated[int, Field(ge=1, le=5)]
    pause_threshold_ms: Annotated[int, Field(ge=1000, le=10000)]

    @classmethod
    def from_preferences(cls, preferences: SupportPreferences) -> SupportPreferencesSnapshot:
        return cls(
            enable_speech_cues=preferences.enable_speech_cues,
            speech_rate_multiplier=_decimal(preferences.speech_rate_multiplier),
            enable_syllable_assistance=preferences.enable_syllable_assistance,
            enable_phoneme_breakdown=preferences.enable_phoneme_breakdown,
            enable_visual_pacing=preferences.enable_visual_pacing,
            visual_pacing_rate_wpm=preferences.visual_pacing_rate_wpm,
            enable_line_focus=preferences.enable_line_focus,
            simplification_level=preferences.simplification_level,
            pause_threshold_ms=preferences.pause_threshold_ms,
        )


class AdaptationThresholdSnapshot(FrozenSnapshotModel):
    """Exact threshold values used for one historical engine evaluation."""

    version_label: VersionLabel
    accuracy_increase_support_below: Probability
    accuracy_reduce_support_above: Probability
    accuracy_increase_difficulty_above: Probability
    accuracy_decrease_difficulty_below: Probability
    accuracy_borderline_band: NonNegativeDecimal
    wpm_reduce_support_above: NonNegativeDecimal
    wpm_increase_support_below: NonNegativeDecimal
    wpm_increase_difficulty_above: NonNegativeDecimal
    hesitation_increase_support_above: NonNegativeDecimal
    hesitation_reduce_support_below: NonNegativeDecimal
    min_sessions_for_recommendation: Annotated[int, Field(ge=1)]

    @classmethod
    def from_thresholds(cls, thresholds: AdaptationThresholds) -> AdaptationThresholdSnapshot:
        return cls(
            version_label=thresholds.version_label,
            accuracy_increase_support_below=_decimal(thresholds.accuracy_increase_support_below),
            accuracy_reduce_support_above=_decimal(thresholds.accuracy_reduce_support_above),
            accuracy_increase_difficulty_above=_decimal(
                thresholds.accuracy_increase_difficulty_above
            ),
            accuracy_decrease_difficulty_below=_decimal(
                thresholds.accuracy_decrease_difficulty_below
            ),
            accuracy_borderline_band=_decimal(thresholds.accuracy_borderline_band),
            wpm_reduce_support_above=_decimal(thresholds.wpm_reduce_support_above),
            wpm_increase_support_below=_decimal(thresholds.wpm_increase_support_below),
            wpm_increase_difficulty_above=_decimal(thresholds.wpm_increase_difficulty_above),
            hesitation_increase_support_above=_decimal(
                thresholds.hesitation_increase_support_above
            ),
            hesitation_reduce_support_below=_decimal(thresholds.hesitation_reduce_support_below),
            min_sessions_for_recommendation=thresholds.min_sessions_for_recommendation,
        )


class DecisionEvidenceSnapshot(FrozenSnapshotModel):
    """One deterministic metric comparison emitted by the decision engine."""

    metric_name: MetricName
    measured_value: FiniteDecimal | None
    threshold_used: FiniteDecimal | None
    comparison: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
    ]
    contributed: bool

    @classmethod
    def from_evidence(cls, evidence: DecisionEvidence) -> DecisionEvidenceSnapshot:
        return cls(
            metric_name=evidence.metric_name,
            measured_value=(
                _decimal(evidence.measured_value) if evidence.measured_value is not None else None
            ),
            threshold_used=(
                _decimal(evidence.threshold_used) if evidence.threshold_used is not None else None
            ),
            comparison=evidence.comparison,
            contributed=evidence.contributed,
        )


class SupportAdjustmentSnapshot(FrozenSnapshotModel):
    """A bounded, typed support suggestion; never an instruction to mutate settings."""

    preference_field: PreferenceField
    suggested_value: StrictBool | StrictInt
    reason_code: ReasonCode
    explanation: Explanation

    @field_validator("explanation", mode="after")
    @classmethod
    def reject_identifier_in_explanation(cls, value: str) -> str:
        if _UUID_PATTERN.search(value):
            raise ValueError("support explanations must not contain UUID identifiers")
        return value

    @classmethod
    def from_adjustment(cls, adjustment: SupportAdjustment) -> SupportAdjustmentSnapshot:
        suggested_value = adjustment.suggested_value
        if not isinstance(suggested_value, (bool, int)):
            raise ValueError("the current engine supports only boolean or integer suggestions")
        return cls(
            preference_field=adjustment.preference_field,
            suggested_value=suggested_value,
            reason_code=adjustment.reason_code,
            explanation=adjustment.explanation,
        )


class AdaptationDecisionOutput(FrozenSnapshotModel):
    """Explainable, advisory-only output preserved exactly for later review."""

    rule_id: RuleIdentifier
    rule_set_version: VersionLabel
    action: AdaptationAction
    recommended_difficulty_tier: DifficultyTier
    recommended_support_mode: SupportMode
    support_adjustments: Annotated[
        tuple[SupportAdjustmentSnapshot, ...],
        Field(max_length=MAX_SUPPORT_ADJUSTMENTS),
    ] = ()
    reason_codes: Annotated[
        tuple[ReasonCode, ...],
        Field(min_length=1, max_length=MAX_REASON_CODES),
    ]
    evidence: Annotated[
        tuple[DecisionEvidenceSnapshot, ...],
        Field(max_length=MAX_EVIDENCE_RECORDS),
    ] = ()
    explanations: Annotated[
        tuple[Explanation, ...],
        Field(min_length=1, max_length=MAX_EXPLANATIONS),
    ]
    blocked_by_manual_override: bool
    disclaimer: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ]
    is_advisory: Literal[True] = True
    safe_to_apply_automatically: Literal[False] = False

    @field_validator("reason_codes", "explanations", mode="after")
    @classmethod
    def sort_unique_text(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("decision text collections must not contain duplicates")
        if any(_UUID_PATTERN.search(item) for item in value):
            raise ValueError("decision text must not contain UUID identifiers")
        return tuple(sorted(value))

    @field_validator("support_adjustments", mode="after")
    @classmethod
    def sort_adjustments(
        cls, value: tuple[SupportAdjustmentSnapshot, ...]
    ) -> tuple[SupportAdjustmentSnapshot, ...]:
        fields = [item.preference_field for item in value]
        if len(set(fields)) != len(fields):
            raise ValueError("only one adjustment per preference field is allowed")
        return tuple(sorted(value, key=lambda item: (item.preference_field, item.reason_code)))

    @classmethod
    def from_decision(cls, decision: AdaptationDecision) -> AdaptationDecisionOutput:
        return cls(
            rule_id=decision.rule_id,
            rule_set_version=decision.rule_set_version,
            action=decision.action,
            recommended_difficulty_tier=decision.recommended_difficulty_tier,
            recommended_support_mode=decision.recommended_support_mode,
            support_adjustments=tuple(
                SupportAdjustmentSnapshot.from_adjustment(item)
                for item in decision.support_adjustments
            ),
            reason_codes=decision.reason_codes,
            evidence=tuple(
                DecisionEvidenceSnapshot.from_evidence(item) for item in decision.evidence
            ),
            explanations=decision.explanations,
            blocked_by_manual_override=decision.blocked_by_manual_override,
            disclaimer=decision.disclaimer,
            is_advisory=decision.is_advisory,
            safe_to_apply_automatically=decision.safe_to_apply_automatically,
        )


class AdaptationDecisionSnapshot(FrozenSnapshotModel):
    """Validated Phase A snapshot with no persistence or application behavior."""

    snapshot_schema_version: SnapshotSchemaVersion = SNAPSHOT_SCHEMA_VERSION
    learner_id: UUID
    evaluation_key: UUID
    trigger_reading_session_id: UUID | None = None
    actor: SnapshotActor
    purpose_context: PurposeContext | None = None

    task_type: TaskType
    current_difficulty_tier: DifficultyTier
    current_support_mode: SupportMode
    manual_override_locked: bool
    support_preferences: SupportPreferencesSnapshot
    session_count: Annotated[int, Field(ge=0)]
    evidence_window_sufficient: bool
    mean_accuracy: Probability | None = None
    mean_wpm: NonNegativeDecimal | None = None
    mean_hesitation_rate_per_word: NonNegativeDecimal | None = None
    mean_engagement_score: Probability | None = None
    analytics_versions: AnalyticsVersions
    source_window_digest: Digest | None = None

    adaptation_engine_version: VersionLabel
    thresholds: AdaptationThresholdSnapshot
    decision: AdaptationDecisionOutput

    @model_validator(mode="after")
    def validate_engine_invariants(self) -> AdaptationDecisionSnapshot:
        if self.decision.rule_set_version != self.thresholds.version_label:
            raise ValueError("decision and threshold rule-set versions must match")
        if (
            self.mean_engagement_score is not None
            and self.analytics_versions.engagement_formula_version is None
        ):
            raise ValueError("an engagement score requires its formula version")
        if self.decision.recommended_support_mode != self.current_support_mode:
            raise ValueError("the current engine does not change support mode automatically")

        tiers = ("early", "intermediate", "advanced")
        current_index = tiers.index(self.current_difficulty_tier)
        recommended_index = tiers.index(self.decision.recommended_difficulty_tier)
        if abs(current_index - recommended_index) > 1:
            raise ValueError("difficulty recommendations may change by at most one tier")

        if self.current_support_mode == "baseline_fixed":
            if not (
                self.decision.action == "maintain"
                and self.decision.rule_id == "FIXED_MODE_PRESERVE"
                and self.decision.recommended_difficulty_tier == self.current_difficulty_tier
                and not self.decision.support_adjustments
            ):
                raise ValueError("baseline_fixed snapshots must preserve the configured state")

        manually_controlled = (
            self.current_support_mode == "manual_override" or self.manual_override_locked
        )
        if manually_controlled and self.current_support_mode != "baseline_fixed":
            if not (
                self.decision.action == "maintain"
                and self.decision.blocked_by_manual_override
                and self.decision.recommended_difficulty_tier == self.current_difficulty_tier
                and not self.decision.support_adjustments
            ):
                raise ValueError("manual control must preserve settings and record the block")
        return self

    @classmethod
    def from_engine(
        cls,
        *,
        learner_id: UUID,
        evaluation_key: UUID,
        actor: SnapshotActor,
        task_type: TaskType,
        adaptation_input: AdaptationInput,
        thresholds: AdaptationThresholds,
        decision: AdaptationDecision,
        trigger_reading_session_id: UUID | None = None,
        purpose_context: PurposeContext | None = None,
        engagement_formula_version: str | None = None,
        source_window_digest: str | None = None,
    ) -> AdaptationDecisionSnapshot:
        """Build a strict snapshot from the existing trusted engine contracts."""
        return cls(
            learner_id=learner_id,
            evaluation_key=evaluation_key,
            trigger_reading_session_id=trigger_reading_session_id,
            actor=actor,
            purpose_context=purpose_context,
            task_type=task_type,
            current_difficulty_tier=adaptation_input.current_difficulty_tier,
            current_support_mode=adaptation_input.current_support_mode,
            manual_override_locked=adaptation_input.manual_override_locked,
            support_preferences=SupportPreferencesSnapshot.from_preferences(
                adaptation_input.support_preferences
            ),
            session_count=adaptation_input.session_count,
            evidence_window_sufficient=adaptation_input.evidence_window_sufficient,
            mean_accuracy=_optional_decimal(adaptation_input.mean_accuracy),
            mean_wpm=_optional_decimal(adaptation_input.mean_wpm),
            mean_hesitation_rate_per_word=_optional_decimal(
                adaptation_input.mean_hesitation_rate_per_word
            ),
            mean_engagement_score=_optional_decimal(adaptation_input.mean_engagement_score),
            analytics_versions=AnalyticsVersions(
                engagement_formula_version=engagement_formula_version
            ),
            source_window_digest=source_window_digest,
            adaptation_engine_version=ADAPTATION_ENGINE_VERSION,
            thresholds=AdaptationThresholdSnapshot.from_thresholds(thresholds),
            decision=AdaptationDecisionOutput.from_decision(decision),
        )


class RetryComparison(StrEnum):
    """Pure classification; callers must authorize before using persisted history."""

    MATCHING_RETRY = "matching_retry"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    SEPARATE_EVALUATION = "separate_evaluation"
    SEPARATE_LEARNER_SCOPE = "separate_learner_scope"


def build_canonical_snapshot_payload(snapshot: AdaptationDecisionSnapshot) -> dict[str, Any]:
    """Return the versioned canonical payload, excluding retry and persistence identity."""
    payload = snapshot.model_dump(mode="python", exclude={"evaluation_key"})
    payload["canonical_format"] = SNAPSHOT_SCHEMA_VERSION
    canonical = _canonicalize(payload)
    if not isinstance(canonical, dict):
        raise TypeError("canonical snapshot payload must be an object")
    return canonical


def canonical_snapshot_bytes(snapshot: AdaptationDecisionSnapshot) -> bytes:
    """Serialize a snapshot deterministically as compact UTF-8 JSON."""
    payload = build_canonical_snapshot_payload(snapshot)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_snapshot_fingerprint(snapshot: AdaptationDecisionSnapshot) -> str:
    """Hash canonical educational content; never use this digest as authorization."""
    return hashlib.sha256(canonical_snapshot_bytes(snapshot)).hexdigest()


def compare_snapshot_retry(
    existing: AdaptationDecisionSnapshot,
    candidate: AdaptationDecisionSnapshot,
) -> RetryComparison:
    """Classify learner-scoped retry identity without database or HTTP behavior."""
    if existing.learner_id != candidate.learner_id:
        return RetryComparison.SEPARATE_LEARNER_SCOPE
    if existing.evaluation_key != candidate.evaluation_key:
        return RetryComparison.SEPARATE_EVALUATION
    if compute_snapshot_fingerprint(existing) == compute_snapshot_fingerprint(candidate):
        return RetryComparison.MATCHING_RETRY
    return RetryComparison.IDEMPOTENCY_CONFLICT


def _decimal(value: Decimal | float | int) -> Decimal:
    """Convert a validated numeric value without importing binary float artifacts."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _optional_decimal(value: Decimal | float | int | None) -> Decimal | None:
    return _decimal(value) if value is not None else None


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("canonical decimals must be finite")
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _canonicalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, UUID):
        return str(value).lower()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical timestamps must be timezone-aware")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    raise TypeError(f"Unsupported canonical value type: {type(value).__name__}")


_UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def explanations_contain_uuid(snapshot: AdaptationDecisionSnapshot) -> bool:
    """Privacy check helper for accidental UUID interpolation in explanations."""
    text = " ".join(snapshot.decision.explanations)
    return _UUID_PATTERN.search(text) is not None
