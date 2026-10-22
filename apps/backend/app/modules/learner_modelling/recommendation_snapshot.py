"""Opt-in, offline synthetic export. Never imported by production consumers."""

import argparse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.learner_modelling.adaptation import ADAPTATION_ENGINE_VERSION
from app.modules.learner_modelling.adaptation_mapping import CompletedSessionEvidence
from app.modules.learner_modelling.analytics import PartitionKey, SessionTelemetry
from app.modules.learner_modelling.longitudinal import LongitudinalObservation, LongitudinalWindow
from app.modules.learner_modelling.recommendation_composition import _compose_recommendation
from app.modules.learner_modelling.recommendation_mobile import (
    MobileRecommendation,
    _mobile_recommendation,
)
from app.modules.learner_modelling.schemas import SupportSettingsRead


class RecommendationSnapshot(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    schema_version: Literal["synthetic-recommendation-v1"] = "synthetic-recommendation-v1"
    synthetic: Literal[True] = True
    source: Literal["backend-recommendation-engine"] = "backend-recommendation-engine"
    engine_version: str
    role: Literal["learner"] = "learner"
    context: Literal["independent_reading/intermediate/adaptive"] = (
        "independent_reading/intermediate/adaptive"
    )
    reporting_start: Literal["2026-01-01T00:00:00+00:00"] = "2026-01-01T00:00:00+00:00"
    reporting_end: Literal["2026-01-31T00:00:00+00:00"] = "2026-01-31T00:00:00+00:00"
    presentation: MobileRecommendation


def _synthetic_inputs() -> tuple[SupportSettingsRead, CompletedSessionEvidence, PartitionKey]:
    # Same six-session January fixture pattern as report_synthetic and adaptation tests.
    # These explicit settings belong only to this simulator, never a missing-row default.
    settings = SupportSettingsRead(
        row_version=2,
        support_mode="adaptive",
        default_difficulty_tier="intermediate",
        enable_speech_cues=True,
        speech_rate_multiplier=Decimal("0.80"),
        enable_syllable_assistance=False,
        enable_phoneme_breakdown=True,
        enable_visual_pacing=True,
        visual_pacing_rate_wpm=70,
        enable_line_focus=True,
        simplification_level=2,
        pause_threshold_ms=3000,
        manual_override_locked=False,
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    key = PartitionKey(
        task_type="independent_reading", difficulty_tier="intermediate", support_mode="adaptive"
    )
    observations = [
        LongitudinalObservation.from_telemetry(
            SessionTelemetry(
                session_start_time=start + timedelta(days=index),
                session_id=f"synthetic-recommendation-{index}",
                words_attempted=100,
                words_correct=96,
                target_word_count=100,
                active_duration_ms=60000,
                total_duration_ms=70000,
                hesitation_count=2,
                total_pause_duration_ms=10000,
                completion_status="completed",
                task_type=key.task_type,
                difficulty_tier=key.difficulty_tier,
                support_mode=key.support_mode,
            )
        )
        for index in range(6)
    ]
    return (
        settings,
        CompletedSessionEvidence.from_observations(
            observations,
            LongitudinalWindow(start_at_utc=start, end_at_utc=start + timedelta(days=30)),
        ),
        key,
    )


def _build_snapshot() -> RecommendationSnapshot:
    settings, evidence, key = _synthetic_inputs()
    decision = _compose_recommendation(settings, evidence, key)
    result = RecommendationSnapshot(
        engine_version=ADAPTATION_ENGINE_VERSION,
        presentation=_mobile_recommendation(settings, decision, evidence=evidence, partition=key),
    )
    return RecommendationSnapshot.model_validate_json(result.model_dump_json())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline synthetic recommendation export; no database or network"
    )
    parser.add_argument("--development-synthetic-only", action="store_true", required=True)
    args = parser.parse_args()
    if not args.development_synthetic_only:
        parser.error("Development synthetic opt-in required")
    # Fixed Component 4 artifact; cannot export supplied learner data or arbitrary files.
    target = (
        Path(__file__).resolve().parents[4]
        / "mobile/src/features/learnerModelling/preview/backendRecommendationSnapshot.json"
    )
    target.write_text(_build_snapshot().model_dump_json(indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
