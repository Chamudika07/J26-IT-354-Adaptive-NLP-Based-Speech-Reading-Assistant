"""Fixed synthetic report fixture shared by isolated developer smoke harnesses only."""

from datetime import UTC, datetime, timedelta

from app.modules.learner_modelling.analytics import SessionTelemetry
from app.modules.learner_modelling.dashboard_projections import (
    LearnerProgressProjection,
    project_learner_progress,
)
from app.modules.learner_modelling.longitudinal import (
    LongitudinalObservation,
    LongitudinalWindow,
    calculate_longitudinal_progress,
)


def build_synthetic_projection() -> LearnerProgressProjection:
    """Construct a fixed fixture without accepting external observations or identifiers."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observations = [
        LongitudinalObservation.from_telemetry(
            SessionTelemetry(
                session_start_time=start + timedelta(days=index),
                session_id=f"synthetic-openai-smoke-{index}",
                words_attempted=100,
                words_correct=65 + index * 4,
                target_word_count=100,
                active_duration_ms=60000,
                total_duration_ms=70000,
                hesitation_count=None if index == 0 else 10 - index,
                total_pause_duration_ms=10000,
            )
        )
        for index in range(6)
    ]
    report = calculate_longitudinal_progress(
        observations,
        LongitudinalWindow(start_at_utc=start, end_at_utc=start + timedelta(days=30)),
    )
    return project_learner_progress(report)
