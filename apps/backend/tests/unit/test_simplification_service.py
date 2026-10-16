"""Unit tests for the Component 2 service layer.

All tests run entirely offline (no database connection required).
External dependencies — sqlalchemy.orm.Session, learner authorization,
and repository functions — are replaced with unittest.mock objects.

What these tests verify:
- Authorization is called before any repository function.
- A denied authorization raises SecurityError before any DB write occurs.
- Session ownership is verified before vocabulary or feedback access.
- source_text is never stored (retention boundary always returns None).
- Feedback is append-only; the service commits on success and rolls back
  on any exception.
- explain_word checks session ownership when session_id is provided,
  and skips the ownership check when session_id is None.

What requires PostgreSQL (not covered here):
- Actual constraint enforcement (CHECK, FK, ARRAY columns).
- Commit/rollback durability.
- clock_timestamp() server default population on feedback.recorded_at.
- The AI execution boundary (NotImplementedError by design).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.simplification import service
from app.modules.simplification.models import (
    SimplificationFeedback,
    SimplificationSession,
    SimplificationVocabulary,
)
from app.modules.simplification.schemas import (
    FeedbackSignal,
    ReadingFeedbackRequest,
    WordExplanationRequest,
)

# ── Test fixtures ─────────────────────────────────────────────────────────────

LEARNER_ID = uuid4()
ACTOR_ID = uuid4()
SESSION_ID = uuid4()
NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _principal(user_id: uuid4 = ACTOR_ID) -> Principal:  # type: ignore[valid-type]
    return Principal(
        user_id=user_id,
        login_handle="synthetic_user",
        roles=frozenset({"learner"}),
        session_id=uuid4(),
        authenticated_at=NOW,
        token_id=uuid4(),
        issued_at=NOW,
        expires_at=NOW,
    )


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()
    return db


def _mock_session(learner_id: uuid4 = LEARNER_ID) -> MagicMock:  # type: ignore[valid-type]
    s = MagicMock(spec=SimplificationSession)
    s.id = SESSION_ID
    s.learner_id = learner_id
    s.simplified_text = "Simplified output."
    s.strategy_applied = "full_rewrite"
    s.target_reading_level = "beginner"
    s.output_difficulty = None
    s.adaptation_attempt = 1
    s.validation_warnings = []
    s.created_at = NOW
    return s


# ── _sha256_hex ───────────────────────────────────────────────────────────────


def test_sha256_hex_returns_64_char_hex():
    digest = service._sha256_hex("hello")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_sha256_hex_is_deterministic():
    assert service._sha256_hex("test") == service._sha256_hex("test")


def test_sha256_hex_differs_for_different_inputs():
    assert service._sha256_hex("a") != service._sha256_hex("b")


# ── _source_text_for_retention ────────────────────────────────────────────────


def test_source_text_for_retention_always_returns_none():
    """Consent framework not yet implemented: source_text must never be stored."""
    result = service._source_text_for_retention("Any source text content here.")
    assert result is None


def test_source_text_for_retention_none_for_empty_string():
    assert service._source_text_for_retention("") is None


def test_learner_authorization_does_not_evaluate_consent():
    """Learner authorization grants an action but explicitly sets consent_evaluated=False."""
    from app.modules.learners.service import LearnerAction, LearnerAuthorization

    auth = LearnerAuthorization(
        actor_id=ACTOR_ID,
        learner_id=LEARNER_ID,
        action=LearnerAction.PERFORM_LEARNING_INTERACTION,
        access_path="self",
        basic_profile_fields=frozenset(),
    )
    assert auth.consent_evaluated is False


# ── Authorization denial (shared across service functions) ────────────────────


@patch("app.modules.simplification.service.authorize_learner_action")
def test_authorization_denial_blocks_list_sessions(mock_auth):
    """Authorization must be evaluated before any repository call."""
    mock_auth.side_effect = SecurityError(404, "not_found", "Resource not found")
    db = _mock_db()
    with pytest.raises(SecurityError) as exc_info:
        service.list_simplification_sessions(db, _principal(), LEARNER_ID, limit=10)
    assert exc_info.value.status == 404
    db.commit.assert_not_called()


@patch("app.modules.simplification.service.authorize_learner_action")
def test_authorization_denial_blocks_get_session(mock_auth):
    mock_auth.side_effect = SecurityError(404, "not_found", "Resource not found")
    db = _mock_db()
    with pytest.raises(SecurityError):
        service.get_simplification_session(db, _principal(), LEARNER_ID, SESSION_ID)
    db.commit.assert_not_called()


@patch("app.modules.simplification.service.authorize_learner_action")
def test_authorization_denial_blocks_get_vocabulary(mock_auth):
    mock_auth.side_effect = SecurityError(404, "not_found", "Resource not found")
    db = _mock_db()
    with pytest.raises(SecurityError):
        service.get_vocabulary_for_session(db, _principal(), LEARNER_ID, SESSION_ID)
    db.commit.assert_not_called()


@patch("app.modules.simplification.service.authorize_learner_action")
def test_authorization_denial_blocks_record_feedback(mock_auth):
    mock_auth.side_effect = SecurityError(404, "not_found", "Resource not found")
    db = _mock_db()
    request = ReadingFeedbackRequest(feedback_signal=FeedbackSignal.JUST_RIGHT)
    with pytest.raises(SecurityError):
        service.record_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID, request)
    db.commit.assert_not_called()
    db.rollback.assert_not_called()  # Error raised before try block


@patch("app.modules.simplification.service.authorize_learner_action")
def test_authorization_denial_blocks_get_feedback(mock_auth):
    mock_auth.side_effect = SecurityError(404, "not_found", "Resource not found")
    db = _mock_db()
    with pytest.raises(SecurityError):
        service.get_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID)
    db.commit.assert_not_called()


# ── Session ownership enforcement ─────────────────────────────────────────────


@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_get_session_raises_404_when_not_owned(mock_auth, mock_get_session):
    """Session not belonging to the learner must yield 404, not expose existence."""
    mock_auth.return_value = None
    mock_get_session.return_value = None  # session not found / belongs to another learner
    db = _mock_db()
    with pytest.raises(SecurityError) as exc_info:
        service.get_simplification_session(db, _principal(), LEARNER_ID, SESSION_ID)
    assert exc_info.value.status == 404
    assert exc_info.value.code == "not_found"


@patch("app.modules.simplification.service.repo.get_vocabulary_for_session")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_get_vocabulary_raises_404_when_session_not_owned(
    mock_auth, mock_get_session, mock_get_vocab
):
    """Vocabulary must not be returned if the session does not belong to the learner."""
    mock_auth.return_value = None
    mock_get_session.return_value = None
    db = _mock_db()
    with pytest.raises(SecurityError) as exc_info:
        service.get_vocabulary_for_session(db, _principal(), LEARNER_ID, SESSION_ID)
    assert exc_info.value.status == 404
    mock_get_vocab.assert_not_called()  # Must not even attempt to fetch vocabulary


@patch("app.modules.simplification.service.repo.record_feedback")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_record_feedback_raises_404_when_session_not_owned(
    mock_auth, mock_get_session, mock_record
):
    """Feedback must not be recorded for a session the learner does not own."""
    mock_auth.return_value = None
    mock_get_session.return_value = None
    db = _mock_db()
    request = ReadingFeedbackRequest(feedback_signal=FeedbackSignal.TOO_HARD)
    with pytest.raises(SecurityError) as exc_info:
        service.record_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID, request)
    assert exc_info.value.status == 404
    mock_record.assert_not_called()


@patch("app.modules.simplification.service.repo.get_feedback_for_session")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_get_feedback_raises_404_when_session_not_owned(
    mock_auth, mock_get_session, mock_get_feedback
):
    """Feedback must not be returned for a session the learner does not own."""
    mock_auth.return_value = None
    mock_get_session.return_value = None
    db = _mock_db()
    with pytest.raises(SecurityError) as exc_info:
        service.get_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID)
    assert exc_info.value.status == 404
    mock_get_feedback.assert_not_called()


# ── list_simplification_sessions ──────────────────────────────────────────────


@patch("app.modules.simplification.service.repo.list_sessions_for_learner")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_list_sessions_calls_repo_with_correct_args(mock_auth, mock_list):
    mock_auth.return_value = None
    mock_list.return_value = []
    db = _mock_db()
    result = service.list_simplification_sessions(db, _principal(), LEARNER_ID, limit=5, offset=10)
    assert result == []
    mock_list.assert_called_once_with(db, learner_id=LEARNER_ID, limit=5, offset=10)


@patch("app.modules.simplification.service.repo.list_sessions_for_learner")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_list_sessions_returns_repo_rows(mock_auth, mock_list):
    mock_auth.return_value = None
    fake_rows = [MagicMock(spec=SimplificationSession) for _ in range(3)]
    mock_list.return_value = fake_rows
    db = _mock_db()
    result = service.list_simplification_sessions(db, _principal(), LEARNER_ID, limit=10)
    assert result == fake_rows
    db.commit.assert_not_called()  # Read-only: no commit


# ── get_simplification_session ────────────────────────────────────────────────


@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_get_session_returns_session_when_owned(mock_auth, mock_get_session):
    mock_auth.return_value = None
    fake_session = _mock_session()
    mock_get_session.return_value = fake_session
    db = _mock_db()
    result = service.get_simplification_session(db, _principal(), LEARNER_ID, SESSION_ID)
    assert result is fake_session
    db.commit.assert_not_called()  # Read-only: no commit


# ── get_vocabulary_for_session ────────────────────────────────────────────────


@patch("app.modules.simplification.service.repo.get_vocabulary_for_session")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_get_vocabulary_returns_rows_when_owned(mock_auth, mock_get_session, mock_get_vocab):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    fake_vocab = [MagicMock(spec=SimplificationVocabulary) for _ in range(2)]
    mock_get_vocab.return_value = fake_vocab
    db = _mock_db()
    result = service.get_vocabulary_for_session(db, _principal(), LEARNER_ID, SESSION_ID)
    assert result == fake_vocab
    mock_get_vocab.assert_called_once_with(db, session_id=SESSION_ID)
    db.commit.assert_not_called()  # Read-only: no commit


# ── record_reading_feedback ───────────────────────────────────────────────────


@patch("app.modules.simplification.service.repo.record_feedback")
@patch("app.modules.simplification.service.repo.current_time")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_record_feedback_uses_request_occurred_at_when_provided(
    mock_auth, mock_get_session, mock_time, mock_record
):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    explicit_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=UTC)
    request = ReadingFeedbackRequest(
        feedback_signal=FeedbackSignal.JUST_RIGHT,
        occurred_at=explicit_time,
    )
    fake_feedback = MagicMock(spec=SimplificationFeedback)
    fake_feedback.id = uuid4()
    fake_feedback.recorded_at = NOW
    mock_record.return_value = fake_feedback

    db = _mock_db()
    service.record_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID, request)

    # When occurred_at is supplied, current_time must not be called.
    mock_time.assert_not_called()
    mock_record.assert_called_once()
    call_kwargs = mock_record.call_args.kwargs
    assert call_kwargs["occurred_at"] == explicit_time


@patch("app.modules.simplification.service.repo.record_feedback")
@patch("app.modules.simplification.service.repo.current_time")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_record_feedback_uses_current_time_when_occurred_at_is_none(
    mock_auth, mock_get_session, mock_time, mock_record
):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    mock_time.return_value = NOW
    request = ReadingFeedbackRequest(feedback_signal=FeedbackSignal.SKIPPED)
    fake_feedback = MagicMock(spec=SimplificationFeedback)
    fake_feedback.id = uuid4()
    fake_feedback.recorded_at = NOW
    mock_record.return_value = fake_feedback

    db = _mock_db()
    service.record_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID, request)

    mock_time.assert_called_once_with(db)
    call_kwargs = mock_record.call_args.kwargs
    assert call_kwargs["occurred_at"] == NOW


@patch("app.modules.simplification.service.repo.record_feedback")
@patch("app.modules.simplification.service.repo.current_time")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_record_feedback_commits_on_success(mock_auth, mock_get_session, mock_time, mock_record):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    mock_time.return_value = NOW
    request = ReadingFeedbackRequest(feedback_signal=FeedbackSignal.TOO_EASY)
    fake_feedback = MagicMock(spec=SimplificationFeedback)
    fake_feedback.id = uuid4()
    fake_feedback.recorded_at = NOW
    mock_record.return_value = fake_feedback

    db = _mock_db()
    service.record_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID, request)

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@patch("app.modules.simplification.service.repo.record_feedback")
@patch("app.modules.simplification.service.repo.current_time")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_record_feedback_rolls_back_on_repo_error(
    mock_auth, mock_get_session, mock_time, mock_record
):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    mock_time.return_value = NOW
    mock_record.side_effect = RuntimeError("synthetic DB failure")
    request = ReadingFeedbackRequest(feedback_signal=FeedbackSignal.TOO_HARD)

    db = _mock_db()
    with pytest.raises(RuntimeError, match="synthetic DB failure"):
        service.record_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID, request)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


@patch("app.modules.simplification.service.repo.record_feedback")
@patch("app.modules.simplification.service.repo.current_time")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_record_feedback_stores_all_optional_fields(
    mock_auth, mock_get_session, mock_time, mock_record
):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    mock_time.return_value = NOW
    request = ReadingFeedbackRequest(
        feedback_signal=FeedbackSignal.JUST_RIGHT,
        time_spent_seconds=120,
        vocabulary_lookups_count=5,
        completed_reading=True,
    )
    fake_feedback = MagicMock(spec=SimplificationFeedback)
    fake_feedback.id = uuid4()
    fake_feedback.recorded_at = NOW
    mock_record.return_value = fake_feedback

    db = _mock_db()
    service.record_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID, request)

    call_kwargs = mock_record.call_args.kwargs
    assert call_kwargs["time_spent_seconds"] == 120
    assert call_kwargs["vocabulary_lookups_count"] == 5
    assert call_kwargs["completed_reading"] is True


@patch("app.modules.simplification.service.repo.record_feedback")
@patch("app.modules.simplification.service.repo.current_time")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_record_feedback_response_contains_correct_ids(
    mock_auth, mock_get_session, mock_time, mock_record
):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    mock_time.return_value = NOW
    feedback_id = uuid4()
    request = ReadingFeedbackRequest(feedback_signal=FeedbackSignal.JUST_RIGHT)
    fake_feedback = MagicMock(spec=SimplificationFeedback)
    fake_feedback.id = feedback_id
    fake_feedback.recorded_at = NOW
    mock_record.return_value = fake_feedback

    db = _mock_db()
    response = service.record_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID, request)

    assert response.feedback_id == feedback_id
    assert response.session_id == SESSION_ID
    assert response.feedback_recorded is True


# ── get_reading_feedback ──────────────────────────────────────────────────────


@patch("app.modules.simplification.service.repo.get_feedback_for_session")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_get_feedback_returns_rows_when_owned(mock_auth, mock_get_session, mock_get_feedback):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    fake_rows = [MagicMock(spec=SimplificationFeedback) for _ in range(2)]
    mock_get_feedback.return_value = fake_rows
    db = _mock_db()
    result = service.get_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID)
    assert result == fake_rows
    mock_get_feedback.assert_called_once_with(db, session_id=SESSION_ID, learner_id=LEARNER_ID)
    db.commit.assert_not_called()  # Read-only: no commit


@patch("app.modules.simplification.service.repo.get_feedback_for_session")
@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_get_feedback_returns_empty_list(mock_auth, mock_get_session, mock_get_feedback):
    mock_auth.return_value = None
    mock_get_session.return_value = _mock_session()
    mock_get_feedback.return_value = []
    db = _mock_db()
    result = service.get_reading_feedback(db, _principal(), LEARNER_ID, SESSION_ID)
    assert result == []


# ── explain_word: session_id ownership ───────────────────────────────────────


@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_explain_word_skips_ownership_check_when_no_session_id(mock_auth, mock_get_session):
    """When session_id is None, ownership check must not be called."""
    mock_auth.return_value = None
    request = WordExplanationRequest(term="photosynthesis", session_id=None)
    db = _mock_db()
    # AI boundary not implemented; NotImplementedError expected
    with pytest.raises(NotImplementedError):
        service.explain_word(db, _principal(), LEARNER_ID, request)
    mock_get_session.assert_not_called()


@patch("app.modules.simplification.service.repo.get_session")
@patch("app.modules.simplification.service.authorize_learner_action")
def test_explain_word_checks_ownership_when_session_id_provided(mock_auth, mock_get_session):
    """When session_id is provided, ownership must be verified before AI call."""
    mock_auth.return_value = None
    mock_get_session.return_value = None  # session not found → 404
    request = WordExplanationRequest(term="photosynthesis", session_id=SESSION_ID)
    db = _mock_db()
    with pytest.raises(SecurityError) as exc_info:
        service.explain_word(db, _principal(), LEARNER_ID, request)
    assert exc_info.value.status == 404
    mock_get_session.assert_called_once()


# ── simplify_text: AI boundary ────────────────────────────────────────────────


@patch("app.modules.simplification.service.authorize_learner_action")
def test_simplify_text_raises_not_implemented(mock_auth):
    """AI boundary not yet implemented; must raise NotImplementedError after auth."""
    from app.modules.simplification.schemas import SimplificationRequest

    mock_auth.return_value = None
    db = _mock_db()
    request = SimplificationRequest(source_text="The cat sat on the mat.")
    with pytest.raises(NotImplementedError):
        service.simplify_text(db, _principal(), LEARNER_ID, request)
    # Rollback must be called because NotImplementedError propagates
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


@patch("app.modules.simplification.service.authorize_learner_action")
def test_simplify_text_rolls_back_on_failure(mock_auth):
    """Any failure inside simplify_text's try block must trigger rollback."""
    from app.modules.simplification.schemas import SimplificationRequest

    mock_auth.return_value = None
    db = _mock_db()
    request = SimplificationRequest(source_text="Some source text.")
    with pytest.raises(NotImplementedError):
        service.simplify_text(db, _principal(), LEARNER_ID, request)
    db.rollback.assert_called_once()


# ── Source text retention boundary ────────────────────────────────────────────


def test_source_text_retention_boundary_is_not_bypassed():
    """Verify _source_text_for_retention is the only path to storing source text.

    The simplify_text function must call _source_text_for_retention and must not
    pass source_text directly to create_session.  Since the function raises
    NotImplementedError at the AI boundary before reaching create_session, we
    verify the retention function is used by inspecting the service module source.
    """
    import inspect

    source = inspect.getsource(service.simplify_text)
    assert "_source_text_for_retention" in source, (
        "simplify_text must route source text through _source_text_for_retention"
    )


# ── No update/delete feedback exposed ─────────────────────────────────────────


def test_service_has_no_update_feedback():
    assert not hasattr(service, "update_reading_feedback"), (
        "Feedback is append-only; update_reading_feedback must not exist"
    )


def test_service_has_no_delete_feedback():
    assert not hasattr(service, "delete_reading_feedback"), (
        "Feedback is append-only; delete_reading_feedback must not exist"
    )
