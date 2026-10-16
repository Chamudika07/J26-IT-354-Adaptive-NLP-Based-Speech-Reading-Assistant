"""Unit tests for Component 2 SQLAlchemy ORM models without database connection."""

from sqlalchemy import ARRAY, DateTime, Integer, Numeric, SmallInteger, String, Text, Uuid
from sqlalchemy.dialects import postgresql

from app.modules.simplification.models import (
    SimplificationFeedback,
    SimplificationSession,
    SimplificationVocabulary,
)


def test_simplification_session_table_conventions():
    table = SimplificationSession.__table__
    assert table.name == "simplification_sessions"

    # Primary key
    assert list(table.primary_key.columns.keys()) == ["id"]
    id_col = table.c.id
    assert isinstance(id_col.type, Uuid)
    assert id_col.type.compile(dialect=postgresql.dialect()) == "UUID"

    # Mixins
    for name in ("created_at", "updated_at"):
        col = table.c[name]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone
        assert not col.nullable

    assert not table.c.row_version.nullable
    assert isinstance(table.c.row_version.type, Integer)

    # Foreign keys
    learner_fk = next(iter(table.c.learner_id.foreign_keys))
    assert learner_fk.target_fullname == "learner_profiles.id"
    assert learner_fk.ondelete == "RESTRICT"

    actor_fk = next(iter(table.c.actor_user_id.foreign_keys))
    assert actor_fk.target_fullname == "users.id"
    assert actor_fk.ondelete == "RESTRICT"

    # Loose document correlation - must NOT have a foreign key
    assert table.c.document_id.nullable
    assert len(table.c.document_id.foreign_keys) == 0

    # Data minimization: source_text must be nullable
    assert table.c.source_text.nullable
    assert isinstance(table.c.source_text.type, Text)
    assert not table.c.source_text_sha256.nullable
    assert isinstance(table.c.source_text_sha256.type, String)
    assert table.c.source_text_sha256.type.length == 64

    # Output and difficulty types
    assert isinstance(table.c.source_difficulty.type, Numeric)
    assert table.c.source_difficulty.type.precision == 4
    assert table.c.source_difficulty.type.scale == 2
    assert table.c.source_difficulty.nullable

    assert isinstance(table.c.output_difficulty.type, Numeric)
    assert table.c.output_difficulty.type.precision == 4
    assert table.c.output_difficulty.type.scale == 2
    assert table.c.output_difficulty.nullable

    assert isinstance(table.c.validation_warnings.type, ARRAY)
    assert isinstance(table.c.adaptation_attempt.type, SmallInteger)

    # Constraints
    constraint_names = {c.name for c in table.constraints if c.name is not None}
    assert "ck_simplification_sessions_row_version_positive" in constraint_names
    assert "ck_simplification_sessions_source_length_positive" in constraint_names
    assert "ck_simplification_sessions_output_length_positive" in constraint_names
    assert "ck_simplification_sessions_source_difficulty_range" in constraint_names
    assert "ck_simplification_sessions_output_difficulty_range" in constraint_names
    assert "ck_simplification_sessions_adaptation_attempt_range" in constraint_names
    assert "ck_simplification_sessions_source_text_sha256_length" in constraint_names
    assert "ck_simplification_sessions_strategy_applied_values" in constraint_names
    assert "ck_simplification_sessions_target_reading_level_values" in constraint_names

    # Indexes
    index_names = {idx.name for idx in table.indexes}
    assert "ix_simplification_sessions_learner_history" in index_names
    assert "ix_simplification_sessions_document_id" in index_names


def test_simplification_vocabulary_table_conventions():
    table = SimplificationVocabulary.__table__
    assert table.name == "simplification_vocabulary"

    # Primary key
    assert list(table.primary_key.columns.keys()) == ["id"]
    assert isinstance(table.c.id.type, Uuid)

    # Mixins
    for name in ("created_at", "updated_at"):
        assert isinstance(table.c[name].type, DateTime)
        assert table.c[name].type.timezone

    assert not table.c.row_version.nullable

    # Cascade foreign key to simplification_sessions
    session_fk = next(iter(table.c.session_id.foreign_keys))
    assert session_fk.target_fullname == "simplification_sessions.id"
    assert session_fk.ondelete == "CASCADE"
    assert table.c.session_id.nullable

    # Columns
    assert isinstance(table.c.term.type, String)
    assert table.c.term.type.length == 200
    assert isinstance(table.c.simplified_definition.type, Text)
    assert isinstance(table.c.example_sentence.type, Text)
    assert table.c.example_sentence.nullable
    assert isinstance(table.c.synonyms.type, ARRAY)
    assert isinstance(table.c.source.type, String)
    assert isinstance(table.c.language_tag.type, String)

    # Constraints
    constraint_names = {c.name for c in table.constraints if c.name is not None}
    assert "ck_simplification_vocabulary_row_version_positive" in constraint_names
    assert "ck_simplification_vocabulary_term_nonblank" in constraint_names
    assert "ck_simplification_vocabulary_source_values" in constraint_names
    assert "ck_simplification_vocabulary_language_tag_nonblank" in constraint_names

    # Indexes
    index_names = {idx.name for idx in table.indexes}
    assert "ix_simplification_vocabulary_session_id" in index_names


def test_simplification_feedback_table_conventions():
    table = SimplificationFeedback.__table__
    assert table.name == "simplification_feedback"

    # Primary key
    assert list(table.primary_key.columns.keys()) == ["id"]
    assert isinstance(table.c.id.type, Uuid)

    # Append-only: must NOT have row_version or updated_at
    assert "row_version" not in table.c
    assert "updated_at" not in table.c

    # Timestamps
    assert isinstance(table.c.occurred_at.type, DateTime)
    assert table.c.occurred_at.type.timezone
    assert not table.c.occurred_at.nullable

    assert isinstance(table.c.recorded_at.type, DateTime)
    assert table.c.recorded_at.type.timezone
    assert not table.c.recorded_at.nullable
    assert table.c.recorded_at.server_default is not None

    # Foreign keys (all RESTRICT)
    session_fk = next(iter(table.c.session_id.foreign_keys))
    assert session_fk.target_fullname == "simplification_sessions.id"
    assert session_fk.ondelete == "RESTRICT"

    learner_fk = next(iter(table.c.learner_id.foreign_keys))
    assert learner_fk.target_fullname == "learner_profiles.id"
    assert learner_fk.ondelete == "RESTRICT"

    recorder_fk = next(iter(table.c.recorded_by_user_id.foreign_keys))
    assert recorder_fk.target_fullname == "users.id"
    assert recorder_fk.ondelete == "RESTRICT"

    # Constraints
    constraint_names = {c.name for c in table.constraints if c.name is not None}
    assert "ck_simplification_feedback_feedback_signal_values" in constraint_names
    assert "ck_simplification_feedback_time_spent_seconds_range" in constraint_names
    assert "ck_simplification_feedback_vocabulary_lookups_count_range" in constraint_names
    assert "ck_simplification_feedback_recording_order" in constraint_names

    # Indexes
    index_names = {idx.name for idx in table.indexes}
    assert "ix_simplification_feedback_session_id" in index_names
    assert "ix_simplification_feedback_learner_history" in index_names
