"""Pure unit tests for immutable, canonical adaptation decision snapshots.

All identifiers and educational measurements are synthetic.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

import app.modules.learner_modelling.decision_snapshots as snapshot_module
from app.modules.learner_modelling.adaptation import (
    AdaptationInput,
    AdaptationThresholds,
    SupportPreferences,
    recommend_adaptation,
)
from app.modules.learner_modelling.analytics import ENGAGEMENT_FORMULA_VERSION
from app.modules.learner_modelling.decision_snapshots import (
    MAX_EVIDENCE_RECORDS,
    MAX_EXPLANATIONS,
    MAX_REASON_CODES,
    SNAPSHOT_SCHEMA_VERSION,
    AdaptationDecisionSnapshot,
    PurposeContext,
    RetryComparison,
    SnapshotActor,
    build_canonical_snapshot_payload,
    canonical_snapshot_bytes,
    compare_snapshot_retry,
    compute_snapshot_fingerprint,
    explanations_contain_uuid,
)

LEARNER_ID = UUID("11111111-2222-4333-8444-555555555555")
OTHER_LEARNER_ID = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
EVALUATION_KEY = UUID("22222222-3333-4444-8555-666666666666")
OTHER_EVALUATION_KEY = UUID("33333333-4444-4555-8666-777777777777")
TRIGGER_SESSION_ID = UUID("44444444-5555-4666-8777-888888888888")
ACTOR_ID = UUID("55555555-6666-4777-8888-999999999999")
SOURCE_DIGEST = "a" * 64


def _preferences(**overrides: Any) -> SupportPreferences:
    values: dict[str, Any] = {
        "enable_speech_cues": False,
        "speech_rate_multiplier": 1.0,
        "enable_syllable_assistance": False,
        "enable_phoneme_breakdown": True,
        "enable_visual_pacing": False,
        "visual_pacing_rate_wpm": None,
        "enable_line_focus": False,
        "simplification_level": 2,
        "pause_threshold_ms": 2500,
    }
    values.update(overrides)
    return SupportPreferences(**values)


def _adaptation_input(**overrides: Any) -> AdaptationInput:
    values: dict[str, Any] = {
        "current_difficulty_tier": "intermediate",
        "current_support_mode": "adaptive",
        "manual_override_locked": False,
        "support_preferences": _preferences(),
        "mean_accuracy": 0.80,
        "mean_wpm": 40.0,
        "mean_hesitation_rate_per_word": 0.15,
        "mean_engagement_score": 0.75,
        "session_count": 5,
        "evidence_window_sufficient": True,
    }
    values.update(overrides)
    return AdaptationInput(**values)


def _snapshot(
    *,
    learner_id: UUID = LEARNER_ID,
    evaluation_key: UUID = EVALUATION_KEY,
    trigger_reading_session_id: UUID | None = TRIGGER_SESSION_ID,
    purpose_context: PurposeContext | None = None,
    adaptation_input: AdaptationInput | None = None,
    thresholds: AdaptationThresholds | None = None,
) -> AdaptationDecisionSnapshot:
    inp = adaptation_input or _adaptation_input()
    applied_thresholds = thresholds or AdaptationThresholds()
    decision = recommend_adaptation(inp, applied_thresholds)
    purpose = purpose_context or PurposeContext(
        purpose_code="learning_support",
        policy_version="policy-v1",
        evaluated_at=datetime(2026, 10, 17, 8, 30, tzinfo=UTC),
    )
    return AdaptationDecisionSnapshot.from_engine(
        learner_id=learner_id,
        evaluation_key=evaluation_key,
        trigger_reading_session_id=trigger_reading_session_id,
        actor=SnapshotActor(kind="authenticated_user", initiating_user_id=ACTOR_ID),
        purpose_context=purpose,
        task_type="independent_reading",
        adaptation_input=inp,
        thresholds=applied_thresholds,
        decision=decision,
        engagement_formula_version=ENGAGEMENT_FORMULA_VERSION,
        source_window_digest=SOURCE_DIGEST,
    )


def _data(snapshot: AdaptationDecisionSnapshot) -> dict[str, Any]:
    return snapshot.model_dump(mode="python")


def _replace_top(
    snapshot: AdaptationDecisionSnapshot, **changes: Any
) -> AdaptationDecisionSnapshot:
    values = _data(snapshot)
    values.update(changes)
    return AdaptationDecisionSnapshot.model_validate(values)


def test_valid_snapshot_creation_and_engine_compatibility() -> None:
    snapshot = _snapshot()

    assert snapshot.snapshot_schema_version == SNAPSHOT_SCHEMA_VERSION
    assert snapshot.learner_id == LEARNER_ID
    assert snapshot.decision.action == "increase_support"
    assert snapshot.decision.rule_id == "INCREASE_SUPPORT_LOW_ACC_OR_FLUENCY"
    assert snapshot.decision.is_advisory is True
    assert snapshot.decision.safe_to_apply_automatically is False
    assert snapshot.thresholds.version_label == snapshot.decision.rule_set_version
    assert len(snapshot.decision.support_adjustments) == 3


@pytest.mark.parametrize(
    "field",
    ["learner_id", "evaluation_key", "trigger_reading_session_id"],
)
def test_invalid_snapshot_identifiers_are_rejected(field: str) -> None:
    values = _data(_snapshot())
    values[field] = "not-a-uuid"
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


def test_invalid_actor_identifier_is_rejected() -> None:
    values = _data(_snapshot())
    values["actor"]["initiating_user_id"] = "not-a-uuid"
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("task_type",), "quiz"),
        (("current_difficulty_tier",), "expert"),
        (("current_support_mode",), "automatic"),
        (("decision", "action"), "diagnose"),
        (("decision", "recommended_difficulty_tier"), "expert"),
        (("decision", "recommended_support_mode"), "automatic"),
        (("decision", "rule_id"), "invalid rule"),
        (("actor", "kind"), "background_job"),
    ],
)
def test_invalid_enum_and_identifier_values_are_rejected(
    path: tuple[str, ...], value: object
) -> None:
    values = _data(_snapshot())
    target: dict[str, Any] = values
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


def test_unsupported_snapshot_schema_version_is_rejected() -> None:
    values = _data(_snapshot())
    values["snapshot_schema_version"] = "adaptation-evaluation-v2"
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("session_count", -1),
        ("mean_accuracy", Decimal("-0.0001")),
        ("mean_accuracy", Decimal("1.0001")),
        ("mean_wpm", Decimal("-0.01")),
        ("mean_hesitation_rate_per_word", Decimal("-0.0001")),
        ("mean_engagement_score", Decimal("1.1")),
    ],
)
def test_invalid_numeric_ranges_are_rejected(field: str, value: object) -> None:
    values = _data(_snapshot())
    values[field] = value
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    "field",
    [
        "mean_accuracy",
        "mean_wpm",
        "mean_hesitation_rate_per_word",
        "mean_engagement_score",
    ],
)
def test_non_finite_metrics_are_rejected(field: str, value: float) -> None:
    values = _data(_snapshot())
    values[field] = value
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


def test_missing_nullable_metrics_remain_explicit_nulls() -> None:
    snapshot = _snapshot(
        adaptation_input=_adaptation_input(
            mean_accuracy=None,
            mean_wpm=None,
            mean_hesitation_rate_per_word=None,
            mean_engagement_score=None,
        )
    )
    payload = build_canonical_snapshot_payload(snapshot)

    for field in (
        "mean_accuracy",
        "mean_wpm",
        "mean_hesitation_rate_per_word",
        "mean_engagement_score",
    ):
        assert field in payload
        assert payload[field] is None


def test_engagement_score_requires_formula_version() -> None:
    values = _data(_snapshot())
    values["analytics_versions"]["engagement_formula_version"] = None
    with pytest.raises(ValidationError, match="formula version"):
        AdaptationDecisionSnapshot.model_validate(values)


def test_naive_consent_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PurposeContext(
            purpose_code="learning_support",
            policy_version="policy-v1",
            evaluated_at=datetime(2026, 10, 17, 8, 30),
        )


def test_timestamps_are_normalized_to_utc() -> None:
    local = timezone(timedelta(hours=5, minutes=30))
    purpose = PurposeContext(
        purpose_code="learning_support",
        policy_version="policy-v1",
        evaluated_at=datetime(2026, 10, 17, 14, 0, tzinfo=local),
    )
    payload = build_canonical_snapshot_payload(_snapshot(purpose_context=purpose))
    assert payload["purpose_context"]["evaluated_at"] == "2026-10-17T08:30:00Z"


def test_equivalent_instants_with_different_offsets_have_same_fingerprint() -> None:
    utc_purpose = PurposeContext(
        purpose_code="learning_support",
        policy_version="policy-v1",
        evaluated_at=datetime(2026, 10, 17, 8, 30, tzinfo=UTC),
    )
    local_purpose = PurposeContext(
        purpose_code="learning_support",
        policy_version="policy-v1",
        evaluated_at=datetime(
            2026,
            10,
            17,
            14,
            0,
            tzinfo=timezone(timedelta(hours=5, minutes=30)),
        ),
    )
    assert compute_snapshot_fingerprint(
        _snapshot(purpose_context=utc_purpose)
    ) == compute_snapshot_fingerprint(_snapshot(purpose_context=local_purpose))


def test_input_dictionary_order_does_not_affect_canonical_bytes() -> None:
    snapshot = _snapshot()
    forward = _data(snapshot)
    reversed_values = dict(reversed(list(forward.items())))
    rebuilt = AdaptationDecisionSnapshot.model_validate(reversed_values)
    assert canonical_snapshot_bytes(snapshot) == canonical_snapshot_bytes(rebuilt)


def test_equivalent_decimal_scales_serialize_stably_without_rounding() -> None:
    snapshot = _snapshot()
    first = _replace_top(snapshot, mean_accuracy=Decimal("0.8000"))
    second = _replace_top(snapshot, mean_accuracy=Decimal("0.8"))

    assert build_canonical_snapshot_payload(first)["mean_accuracy"] == "0.8"
    assert compute_snapshot_fingerprint(first) == compute_snapshot_fingerprint(second)


def test_additional_valid_metric_precision_is_preserved_not_rounded() -> None:
    first = _snapshot(adaptation_input=_adaptation_input(mean_accuracy=0.80001))
    second = _snapshot(adaptation_input=_adaptation_input(mean_accuracy=0.80002))

    assert build_canonical_snapshot_payload(first)["mean_accuracy"] == "0.80001"
    assert build_canonical_snapshot_payload(second)["mean_accuracy"] == "0.80002"
    assert compute_snapshot_fingerprint(first) != compute_snapshot_fingerprint(second)


def _leaf_paths(value: object, prefix: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        paths: list[tuple[object, ...]] = []
        for key, item in value.items():
            paths.extend(_leaf_paths(item, (*prefix, key)))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_leaf_paths(item, (*prefix, index)))
        return paths
    return [prefix]


def _change_leaf(payload: dict[str, Any], path: tuple[object, ...]) -> None:
    target: Any = payload
    for part in path[:-1]:
        target = target[part]
    key = path[-1]
    current = target[key]
    if current is None:
        target[key] = "changed"
    elif isinstance(current, bool):
        target[key] = not current
    elif isinstance(current, int):
        target[key] = current + 1
    else:
        target[key] = f"{current}#"


def test_every_canonical_leaf_affects_the_payload_digest() -> None:
    payload = build_canonical_snapshot_payload(_snapshot())
    baseline = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()

    for path in _leaf_paths(payload):
        changed = deepcopy(payload)
        _change_leaf(changed, path)
        digest = hashlib.sha256(
            json.dumps(
                changed,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        assert digest != baseline, path


def test_evaluation_key_and_persistence_identity_are_excluded_from_fingerprint() -> None:
    original = _snapshot(evaluation_key=EVALUATION_KEY)
    repeated = _snapshot(evaluation_key=OTHER_EVALUATION_KEY)
    payload = build_canonical_snapshot_payload(original)

    assert compute_snapshot_fingerprint(original) == compute_snapshot_fingerprint(repeated)
    assert "evaluation_key" not in payload
    assert "id" not in payload
    assert "generated_at" not in payload


def test_same_key_and_payload_is_matching_retry() -> None:
    assert compare_snapshot_retry(_snapshot(), _snapshot()) is RetryComparison.MATCHING_RETRY


def test_same_key_and_different_payload_is_conflict() -> None:
    existing = _snapshot()
    candidate = _snapshot(adaptation_input=_adaptation_input(mean_accuracy=0.81))
    assert compare_snapshot_retry(existing, candidate) is RetryComparison.IDEMPOTENCY_CONFLICT


def test_different_evaluation_keys_are_separate_even_with_identical_evidence() -> None:
    first = _snapshot(evaluation_key=EVALUATION_KEY)
    second = _snapshot(evaluation_key=OTHER_EVALUATION_KEY)
    assert compute_snapshot_fingerprint(first) == compute_snapshot_fingerprint(second)
    assert compare_snapshot_retry(first, second) is RetryComparison.SEPARATE_EVALUATION


def test_same_evaluation_key_is_separately_scoped_for_different_learners() -> None:
    first = _snapshot(learner_id=LEARNER_ID)
    second = _snapshot(learner_id=OTHER_LEARNER_ID)
    assert compute_snapshot_fingerprint(first) != compute_snapshot_fingerprint(second)
    assert compare_snapshot_retry(first, second) is RetryComparison.SEPARATE_LEARNER_SCOPE


def test_reason_and_adjustment_order_is_stable_while_evidence_order_is_preserved() -> None:
    values = _data(_snapshot())
    values["decision"]["reason_codes"] = ("z_reason", "a_reason")
    values["decision"]["explanations"] = ("Zulu explanation.", "Alpha explanation.")
    values["decision"]["support_adjustments"] = tuple(
        reversed(values["decision"]["support_adjustments"])
    )
    values["decision"]["evidence"] = tuple(reversed(values["decision"]["evidence"]))
    expected_evidence_order = tuple(item["metric_name"] for item in values["decision"]["evidence"])

    rebuilt = AdaptationDecisionSnapshot.model_validate(values)

    assert rebuilt.decision.reason_codes == ("a_reason", "z_reason")
    assert rebuilt.decision.explanations == ("Alpha explanation.", "Zulu explanation.")
    assert tuple(item.preference_field for item in rebuilt.decision.support_adjustments) == tuple(
        sorted(item.preference_field for item in rebuilt.decision.support_adjustments)
    )
    assert tuple(item.metric_name for item in rebuilt.decision.evidence) == expected_evidence_order


def test_snapshot_and_nested_contracts_are_immutable() -> None:
    snapshot = _snapshot()
    with pytest.raises(ValidationError):
        snapshot.session_count = 99  # type: ignore[misc]
    with pytest.raises(ValidationError):
        snapshot.decision.action = "maintain"  # type: ignore[misc]


def test_strict_extra_field_rejection_at_all_levels() -> None:
    values = _data(_snapshot())
    values["learner_name"] = "Synthetic Name"
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)

    values = _data(_snapshot())
    values["decision"]["ai_conclusion"] = "Unsupported"
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


@pytest.mark.parametrize(
    ("field", "value"),
    [("is_advisory", False), ("safe_to_apply_automatically", True)],
)
def test_advisory_only_output_literals_are_enforced(field: str, value: bool) -> None:
    values = _data(_snapshot())
    values["decision"][field] = value
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


def test_manual_override_provenance_preserves_state() -> None:
    snapshot = _snapshot(
        adaptation_input=_adaptation_input(
            current_support_mode="manual_override",
            manual_override_locked=True,
        )
    )
    assert snapshot.current_support_mode == "manual_override"
    assert snapshot.manual_override_locked is True
    assert snapshot.decision.action == "maintain"
    assert snapshot.decision.blocked_by_manual_override is True
    assert snapshot.decision.recommended_difficulty_tier == snapshot.current_difficulty_tier
    assert snapshot.decision.support_adjustments == ()


def test_fixed_mode_recommendation_is_preserved() -> None:
    snapshot = _snapshot(adaptation_input=_adaptation_input(current_support_mode="baseline_fixed"))
    assert snapshot.decision.rule_id == "FIXED_MODE_PRESERVE"
    assert snapshot.decision.action == "maintain"
    assert snapshot.decision.recommended_difficulty_tier == snapshot.current_difficulty_tier
    assert snapshot.decision.recommended_support_mode == "baseline_fixed"


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("reason_codes", MAX_REASON_CODES),
        ("explanations", MAX_EXPLANATIONS),
        ("evidence", MAX_EVIDENCE_RECORDS),
    ],
)
def test_nested_collection_maximums_are_enforced(field: str, limit: int) -> None:
    values = _data(_snapshot())
    if field == "reason_codes":
        values["decision"][field] = tuple(f"reason_{index}" for index in range(limit + 1))
    elif field == "explanations":
        values["decision"][field] = tuple(
            f"Synthetic explanation {index}." for index in range(limit + 1)
        )
    else:
        template = values["decision"]["evidence"][0]
        values["decision"][field] = tuple(deepcopy(template) for _ in range(limit + 1))
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


def test_uuid_identifiers_are_rejected_from_explanations() -> None:
    values = _data(_snapshot())
    values["decision"]["explanations"] = (f"Learner {LEARNER_ID} should change level.",)
    with pytest.raises(ValidationError, match="UUID"):
        AdaptationDecisionSnapshot.model_validate(values)
    assert explanations_contain_uuid(_snapshot()) is False


def test_snapshot_has_no_personal_research_assignment_or_application_fields() -> None:
    field_names = set(AdaptationDecisionSnapshot.model_fields)
    serialized = canonical_snapshot_bytes(_snapshot()).decode("utf-8").lower()

    assert (
        not {
            "learner_name",
            "document_text",
            "raw_audio",
            "diagnosis",
            "dyslexia_severity",
            "ip_address",
            "token",
            "research_arm",
            "research_assignment",
            "applied",
        }
        & field_names
    )
    for forbidden in (
        "learner_name",
        "document_text",
        "raw_audio",
        "dyslexia_severity",
        "ip_address",
        "research_arm",
        "research_assignment",
    ):
        assert forbidden not in serialized
    explanations = " ".join(_snapshot().decision.explanations).lower()
    assert "diagnosis" not in explanations
    assert "dyslexia" not in explanations


def test_trigger_session_and_purpose_context_can_be_absent_without_manufacturing_data() -> None:
    snapshot = _replace_top(_snapshot(trigger_reading_session_id=None), purpose_context=None)
    payload = build_canonical_snapshot_payload(snapshot)
    assert payload["trigger_reading_session_id"] is None
    assert payload["purpose_context"] is None


def test_source_digest_must_be_lowercase_sha256() -> None:
    values = _data(_snapshot())
    values["source_window_digest"] = "A" * 64
    with pytest.raises(ValidationError):
        AdaptationDecisionSnapshot.model_validate(values)


def test_repeated_fingerprints_are_deterministic_and_lowercase_sha256() -> None:
    snapshot = _snapshot()
    results = {compute_snapshot_fingerprint(snapshot) for _ in range(20)}
    assert len(results) == 1
    digest = results.pop()
    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)


def test_module_has_no_database_network_or_side_effect_imports() -> None:
    tree = ast.parse(inspect.getsource(snapshot_module))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".")[0])

    assert imported_roots.isdisjoint(
        {"sqlalchemy", "psycopg", "fastapi", "httpx", "requests", "socket"}
    )
