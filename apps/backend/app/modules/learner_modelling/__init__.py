"""Learner modelling and adaptive analytics module."""

from app.modules.learner_modelling.analytics import (
    ENGAGEMENT_FORMULA_VERSION,
    CompletionStatistics,
    EngagementIndicator,
    EngagementWeights,
    HesitationStatistics,
    PartitionKey,
    PartitionProgress,
    SessionTelemetry,
    calculate_completion_statistics,
    calculate_experimental_engagement,
    calculate_hesitation_frequency,
    calculate_partitioned_progress,
    calculate_reading_accuracy,
    calculate_words_per_minute,
)

__all__ = [
    "ENGAGEMENT_FORMULA_VERSION",
    "CompletionStatistics",
    "EngagementIndicator",
    "EngagementWeights",
    "HesitationStatistics",
    "PartitionKey",
    "PartitionProgress",
    "SessionTelemetry",
    "calculate_completion_statistics",
    "calculate_experimental_engagement",
    "calculate_hesitation_frequency",
    "calculate_partitioned_progress",
    "calculate_reading_accuracy",
    "calculate_words_per_minute",
]
