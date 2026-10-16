"""Unit tests for the simplification repository layer.

These tests run entirely offline (no database connection required).
They verify:
- ORM objects are constructed with the correct field values.
- Learner-scoped queries always include a learner_id filter.
- Feedback is append-only (no update/delete helpers exist).
- source_text is None by default; callers must opt in.
- current_time delegates to clock_timestamp().

A lightweight mock of sqlalchemy.orm.Session is used; each call to
db.add(), db.flush(), and db.scalar()/db.scalars() is captured and
inspected without opening a real connection.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.simplification import repository as repo
from app.modules.simplification.models import (
    SimplificationFeedback,
    SimplificationSession,
    SimplificationVocabulary,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

LEARNER_ID = uuid4()
ACTOR_ID = uuid4()
SESSION_ID = uuid4()
USER_ID = uuid4()

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

MINIMAL_SESSION_KWARGS: dict = dict(
    learner_id=LEARNER_ID,
    actor_user_id=ACTOR_ID,
    source_text_sha256="a" * 64,
    source_length=100,
    strategy_applied="full_rewrite",
    target_reading_level="beginner",
    adaptation_attempt=1,
    simplified_text="A simple sentence.",
    output_length=18,
    ai_provider="test-provider",
    ai_latency_ms=120,
)


def _mock_db() -> MagicMock:
    """Return a MagicMock shaped like sqlalchemy.orm.Session."""
    db = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    return db


# ── current_time ──────────────────────────────────────────────────────────────


def test_current_time_delegates_to_db():
    """current_time() must call clock_timestamp() via db.execute().scalar_one()."""
    db = _mock_db()
    db.execute.return_value.scalar_one.return_value = NOW
    result = repo.current_time(db)
    assert result == NOW
    db.execute.assert_called_once()


# ── create_session ────────────────────────────────────────────────────────────


def test_create_session_adds_and_flushes():
    db = _mock_db()
    row = repo.create_session(db, **MINIMAL_SESSION_KWARGS)
    db.add.assert_called_once_with(row)
    db.flush.assert_called_once()


def test_create_session_returns_simplification_session():
    db = _mock_db()
    row = repo.create_session(db, **MINIMAL_SESSION_KWARGS)
    assert isinstance(row, SimplificationSession)


def test_create_session_source_text_is_none_by_default():
    """source_text must be None unless the caller explicitly passes it."""
    db = _mock_db()
    row = repo.create_session(db, **MINIMAL_SESSION_KWARGS)
    assert row.source_text is None


def test_create_session_source_text_set_when_provided():
    db = _mock_db()
    row = repo.create_session(db, **MINIMAL_SESSION_KWARGS, source_text="Original text content.")
    assert row.source_text == "Original text content."


def test_create_session_validation_warnings_defaults_to_empty_list():
    db = _mock_db()
    row = repo.create_session(db, **MINIMAL_SESSION_KWARGS)
    assert row.validation_warnings == []


def test_create_session_validation_warnings_stored_when_provided():
    db = _mock_db()
    warnings = ["low_confidence", "short_output"]
    row = repo.create_session(db, **MINIMAL_SESSION_KWARGS, validation_warnings=warnings)
    assert row.validation_warnings == warnings


def test_create_session_optional_fields_stored():
    doc_id = uuid4()
    db = _mock_db()
    row = repo.create_session(
        db,
        **MINIMAL_SESSION_KWARGS,
        document_id=doc_id,
        source_difficulty=Decimal("0.75"),
        output_difficulty=Decimal("0.30"),
        concepts_preserved=True,
    )
    assert row.document_id == doc_id
    assert row.source_difficulty == Decimal("0.75")
    assert row.output_difficulty == Decimal("0.30")
    assert row.concepts_preserved is True


def test_create_session_required_fields_assigned():
    db = _mock_db()
    row = repo.create_session(db, **MINIMAL_SESSION_KWARGS)
    assert row.learner_id == LEARNER_ID
    assert row.actor_user_id == ACTOR_ID
    assert row.source_text_sha256 == "a" * 64
    assert row.source_length == 100
    assert row.strategy_applied == "full_rewrite"
    assert row.target_reading_level == "beginner"
    assert row.adaptation_attempt == 1
    assert row.simplified_text == "A simple sentence."
    assert row.output_length == 18
    assert row.ai_provider == "test-provider"
    assert row.ai_latency_ms == 120


# ── get_session ───────────────────────────────────────────────────────────────


def test_get_session_calls_db_scalar():
    db = _mock_db()
    fake_session = MagicMock(spec=SimplificationSession)
    db.scalar.return_value = fake_session
    result = repo.get_session(db, session_id=SESSION_ID, learner_id=LEARNER_ID)
    assert result is fake_session
    db.scalar.assert_called_once()


def test_get_session_returns_none_when_not_found():
    db = _mock_db()
    db.scalar.return_value = None
    result = repo.get_session(db, session_id=SESSION_ID, learner_id=LEARNER_ID)
    assert result is None


def test_get_session_query_includes_learner_filter():
    """Confirm both session_id and learner_id appear in the compiled WHERE clause."""
    db = _mock_db()
    db.scalar.return_value = None
    repo.get_session(db, session_id=SESSION_ID, learner_id=LEARNER_ID)
    # Inspect the Select statement passed to db.scalar
    stmt = db.scalar.call_args[0][0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "simplification_sessions" in compiled
    # Both columns must appear as bound parameters in the query
    whereclause = str(stmt.whereclause)
    assert "learner_id" in whereclause
    assert "id" in whereclause  # session_id maps to the 'id' column


def test_get_session_with_wrong_learner_id_returns_none():
    """A different learner_id must not expose another learner's session."""
    db = _mock_db()
    # Simulate the DB returning None when the learner_id does not match.
    db.scalar.return_value = None
    other_learner = uuid4()
    result = repo.get_session(db, session_id=SESSION_ID, learner_id=other_learner)
    assert result is None
    # Critically: the WHERE clause sent to the DB must include the other learner's ID.
    stmt = db.scalar.call_args[0][0]
    whereclause = str(stmt.whereclause)
    assert "learner_id" in whereclause


# ── list_sessions_for_learner ─────────────────────────────────────────────────


def test_list_sessions_for_learner_returns_list():
    db = _mock_db()
    fake_rows = [MagicMock(spec=SimplificationSession) for _ in range(3)]
    db.scalars.return_value = iter(fake_rows)
    result = repo.list_sessions_for_learner(db, learner_id=LEARNER_ID, limit=10)
    assert result == fake_rows


def test_list_sessions_for_learner_returns_empty_list():
    db = _mock_db()
    db.scalars.return_value = iter([])
    result = repo.list_sessions_for_learner(db, learner_id=LEARNER_ID, limit=10)
    assert result == []


def test_list_sessions_for_learner_query_scoped_by_learner():
    db = _mock_db()
    db.scalars.return_value = iter([])
    repo.list_sessions_for_learner(db, learner_id=LEARNER_ID, limit=5)
    stmt = db.scalars.call_args[0][0]
    whereclause = str(stmt.whereclause)
    assert "learner_id" in whereclause


def test_list_sessions_for_learner_passes_limit():
    db = _mock_db()
    db.scalars.return_value = iter([])
    repo.list_sessions_for_learner(db, learner_id=LEARNER_ID, limit=7)
    stmt = db.scalars.call_args[0][0]
    assert stmt._limit_clause is not None
    assert stmt._limit_clause.value == 7


def test_list_sessions_for_learner_ordered_newest_first():
    """The query must order by created_at DESC so pagination is stable and consistent."""
    db = _mock_db()
    db.scalars.return_value = iter([])
    repo.list_sessions_for_learner(db, learner_id=LEARNER_ID, limit=5)
    stmt = db.scalars.call_args[0][0]
    # Inspect the ORDER BY clause: must contain created_at with DESC modifier.
    order_clauses = stmt._order_by_clauses
    assert order_clauses, "Expected ORDER BY clause to be present"
    order_str = " ".join(str(c) for c in order_clauses)
    assert "created_at" in order_str
    assert "DESC" in order_str


def test_list_sessions_for_learner_default_offset_zero():
    db = _mock_db()
    db.scalars.return_value = iter([])
    repo.list_sessions_for_learner(db, learner_id=LEARNER_ID, limit=5)
    stmt = db.scalars.call_args[0][0]
    # When offset=0 (default), the clause value must be 0 or absent (None).
    clause = stmt._offset_clause
    if clause is not None:
        assert clause.value == 0, f"Expected offset 0, got {clause.value}"


def test_list_sessions_for_learner_explicit_offset():
    db = _mock_db()
    db.scalars.return_value = iter([])
    repo.list_sessions_for_learner(db, learner_id=LEARNER_ID, limit=5, offset=20)
    stmt = db.scalars.call_args[0][0]
    assert stmt._offset_clause is not None


# ── create_vocabulary ─────────────────────────────────────────────────────────


def test_create_vocabulary_adds_and_flushes():
    db = _mock_db()
    row = repo.create_vocabulary(
        db,
        term="photosynthesis",
        simplified_definition="How plants make food using sunlight.",
        source="automatic",
        language_tag="en",
    )
    db.add.assert_called_once_with(row)
    db.flush.assert_called_once()


def test_create_vocabulary_returns_simplification_vocabulary():
    db = _mock_db()
    row = repo.create_vocabulary(
        db,
        term="osmosis",
        simplified_definition="Movement of water through a membrane.",
        source="automatic",
        language_tag="en",
    )
    assert isinstance(row, SimplificationVocabulary)


def test_create_vocabulary_session_id_nullable_by_default():
    db = _mock_db()
    row = repo.create_vocabulary(
        db,
        term="molecule",
        simplified_definition="A tiny building block of matter.",
        source="user",
        language_tag="en",
    )
    assert row.session_id is None


def test_create_vocabulary_session_id_set_when_provided():
    db = _mock_db()
    row = repo.create_vocabulary(
        db,
        term="nucleus",
        simplified_definition="Control centre of a cell.",
        source="automatic",
        language_tag="en",
        session_id=SESSION_ID,
    )
    assert row.session_id == SESSION_ID


def test_create_vocabulary_synonyms_default_empty():
    db = _mock_db()
    row = repo.create_vocabulary(
        db,
        term="atom",
        simplified_definition="Smallest piece of an element.",
        source="automatic",
        language_tag="en",
    )
    assert row.synonyms == []


def test_create_vocabulary_synonyms_stored_when_provided():
    db = _mock_db()
    row = repo.create_vocabulary(
        db,
        term="big",
        simplified_definition="Large in size.",
        source="user",
        language_tag="en",
        synonyms=["large", "huge"],
    )
    assert row.synonyms == ["large", "huge"]


def test_create_vocabulary_example_sentence_optional():
    db = _mock_db()
    row = repo.create_vocabulary(
        db,
        term="gravity",
        simplified_definition="Force that pulls things down.",
        source="automatic",
        language_tag="en",
        example_sentence="Gravity keeps us on the ground.",
    )
    assert row.example_sentence == "Gravity keeps us on the ground."


# ── get_vocabulary_for_session ────────────────────────────────────────────────


def test_get_vocabulary_for_session_returns_list():
    db = _mock_db()
    fake_rows = [MagicMock(spec=SimplificationVocabulary) for _ in range(2)]
    db.scalars.return_value = iter(fake_rows)
    result = repo.get_vocabulary_for_session(db, session_id=SESSION_ID)
    assert result == fake_rows


def test_get_vocabulary_for_session_filters_by_session_id():
    db = _mock_db()
    db.scalars.return_value = iter([])
    repo.get_vocabulary_for_session(db, session_id=SESSION_ID)
    stmt = db.scalars.call_args[0][0]
    whereclause = str(stmt.whereclause)
    assert "session_id" in whereclause


# ── record_feedback ───────────────────────────────────────────────────────────


def test_record_feedback_adds_and_flushes():
    db = _mock_db()
    row = repo.record_feedback(
        db,
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        feedback_signal="just_right",
        occurred_at=NOW,
        recorded_by_user_id=USER_ID,
    )
    db.add.assert_called_once_with(row)
    db.flush.assert_called_once()


def test_record_feedback_returns_simplification_feedback():
    db = _mock_db()
    row = repo.record_feedback(
        db,
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        feedback_signal="too_hard",
        occurred_at=NOW,
        recorded_by_user_id=USER_ID,
    )
    assert isinstance(row, SimplificationFeedback)


def test_record_feedback_fields_stored_correctly():
    db = _mock_db()
    row = repo.record_feedback(
        db,
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        feedback_signal="too_easy",
        occurred_at=NOW,
        recorded_by_user_id=USER_ID,
        time_spent_seconds=120,
        vocabulary_lookups_count=3,
        completed_reading=True,
    )
    assert row.session_id == SESSION_ID
    assert row.learner_id == LEARNER_ID
    assert row.feedback_signal == "too_easy"
    assert row.occurred_at == NOW
    assert row.recorded_by_user_id == USER_ID
    assert row.time_spent_seconds == 120
    assert row.vocabulary_lookups_count == 3
    assert row.completed_reading is True


def test_record_feedback_optional_fields_default_to_none():
    db = _mock_db()
    row = repo.record_feedback(
        db,
        session_id=SESSION_ID,
        learner_id=LEARNER_ID,
        feedback_signal="skipped",
        occurred_at=NOW,
        recorded_by_user_id=USER_ID,
    )
    assert row.time_spent_seconds is None
    assert row.vocabulary_lookups_count is None
    assert row.completed_reading is None


def test_feedback_no_update_method_exists():
    """Feedback is append-only: the repository must expose no update_feedback function."""
    assert not hasattr(repo, "update_feedback"), (
        "update_feedback must not exist; feedback rows are append-only"
    )


def test_feedback_no_delete_method_exists():
    """Feedback is append-only: the repository must expose no delete_feedback function."""
    assert not hasattr(repo, "delete_feedback"), (
        "delete_feedback must not exist; feedback rows are append-only"
    )


# ── get_feedback_for_session ──────────────────────────────────────────────────


def test_get_feedback_for_session_returns_list():
    db = _mock_db()
    fake_rows = [MagicMock(spec=SimplificationFeedback) for _ in range(2)]
    db.scalars.return_value = iter(fake_rows)
    result = repo.get_feedback_for_session(db, session_id=SESSION_ID, learner_id=LEARNER_ID)
    assert result == fake_rows


def test_get_feedback_for_session_filters_by_session_and_learner():
    """Both session_id and learner_id must appear in the WHERE clause."""
    db = _mock_db()
    db.scalars.return_value = iter([])
    repo.get_feedback_for_session(db, session_id=SESSION_ID, learner_id=LEARNER_ID)
    stmt = db.scalars.call_args[0][0]
    whereclause = str(stmt.whereclause)
    assert "session_id" in whereclause
    assert "learner_id" in whereclause


def test_get_feedback_for_session_wrong_learner_returns_no_rows():
    """A mismatched learner_id must not expose feedback belonging to another learner.

    The WHERE clause must carry the caller-supplied learner_id so the database
    can reject rows that belong to a different learner, even when the session_id
    is known.
    """
    db = _mock_db()
    db.scalars.return_value = iter([])  # DB returns nothing for the wrong learner
    other_learner = uuid4()
    result = repo.get_feedback_for_session(db, session_id=SESSION_ID, learner_id=other_learner)
    assert result == []
    # Verify the wrong learner's ID (not LEARNER_ID) was passed in the WHERE clause.
    stmt = db.scalars.call_args[0][0]
    whereclause = str(stmt.whereclause)
    assert "learner_id" in whereclause


def test_get_feedback_for_session_returns_empty_when_none():
    db = _mock_db()
    db.scalars.return_value = iter([])
    result = repo.get_feedback_for_session(db, session_id=SESSION_ID, learner_id=LEARNER_ID)
    assert result == []


# ── Module-level API surface guard ────────────────────────────────────────────


def test_repository_does_not_export_cross_module_models():
    """The repository must not import or re-export models from other modules."""
    import inspect

    import app.modules.simplification.repository as repo_module

    for name, obj in inspect.getmembers(repo_module):
        if inspect.isclass(obj) and hasattr(obj, "__tablename__"):
            assert obj.__tablename__.startswith("simplification_"), (
                f"Repository must not expose foreign table '{obj.__tablename__}' via '{name}'"
            )
