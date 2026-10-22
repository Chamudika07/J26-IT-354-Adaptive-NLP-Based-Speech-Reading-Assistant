"""Synthetic end-to-end tests for the inactive Component 4 reading flow.

The tests exercise real Component 4 validation, ingestion, longitudinal analytics,
role projections, completed-session selection, and advisory adaptation. Only the
repository and existing authorization/consent extension points are replaced with
test doubles; no database, HTTP route, or production security substitute is used.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

import app.modules.learner_modelling.repository as repository
import app.modules.learner_modelling.service as service
from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.learner_modelling.adaptation import (
    AdaptationDecision,
    SupportPreferences,
    recommend_adaptation,
)
from app.modules.learner_modelling.adaptation_mapping import (
    AdaptationMappingError,
    CompletedSessionEvidence,
    map_longitudinal_partition_to_adaptation_input,
    select_completed_session_evidence,
)
from app.modules.learner_modelling.analytics import PartitionKey
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    LearnerProgressProjection,
    project_educator_analytics,
    project_guardian_summary,
    project_learner_progress,
)
from app.modules.learner_modelling.historical import (
    HistoricalDataIntegrityError,
    HistoricalQueryBounds,
    HistoricalQueryValidationError,
    HistoricalResultLimitExceeded,
    HistoricalSessionQuery,
    HistoricalSessionRecord,
    historical_records_to_observations,
)
from app.modules.learner_modelling.longitudinal import LongitudinalProgressReport
from app.modules.learner_modelling.models import ReadingSession
from app.modules.learner_modelling.report_evidence import build_structured_report
from app.modules.learner_modelling.report_narrative import generate_progress_report
from app.modules.learner_modelling.schemas import ReadingSessionIngest
from app.modules.learners.service import LearnerAction, LearnerAuthorization

LEARNER_ID = UUID("40000000-0000-4000-8000-000000000001")
OTHER_LEARNER_ID = UUID("40000000-0000-4000-8000-000000000002")


def _principal(role: str, identity: UUID) -> Principal:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    return Principal(
        user_id=identity,
        login_handle=f"synthetic-{role}",
        roles=frozenset({role}),
        session_id=UUID(int=identity.int + 100),
        authenticated_at=now,
        token_id=UUID(int=identity.int + 200),
        issued_at=now,
        expires_at=now + timedelta(days=30),
    )


def _payload(
    day: int,
    *,
    completion_status: str = "completed",
    words_attempted: int = 100,
    words_correct: int = 96,
    active_duration_ms: int = 60_000,
    total_duration_ms: int = 70_000,
    hesitation_count: int | None = 2,
    client_session_id: UUID | None = None,
    task_type: str = "independent_reading",
    difficulty_tier: str = "intermediate",
    support_mode: str = "adaptive",
    session_start_time: datetime | None = None,
) -> ReadingSessionIngest:
    start = (
        session_start_time
        if session_start_time is not None
        else datetime(2026, 10, day, 9, tzinfo=UTC)
    )
    return ReadingSessionIngest.model_validate(
        {
            "learner_id": LEARNER_ID,
            "client_session_id": client_session_id or UUID(int=1_000 + day),
            "document_id": None,
            "session_start_time": start,
            "session_end_time": start + timedelta(minutes=5),
            "task_type": task_type,
            "difficulty_tier": difficulty_tier,
            "support_mode": support_mode,
            "completion_status": completion_status,
            "words_attempted": words_attempted,
            "words_correct": words_correct,
            "target_word_count": 100,
            "active_duration_ms": active_duration_ms,
            "total_duration_ms": total_duration_ms,
            "hesitation_count": hesitation_count,
            "total_pause_duration_ms": 5_000,
            "pause_count": 2,
            "replay_count": 0,
        }
    )


def _query(*, learner_id: UUID = LEARNER_ID, session_limit: int = 25) -> HistoricalSessionQuery:
    return HistoricalSessionQuery(
        learner_id=learner_id,
        start_at_utc=datetime(2026, 10, 1, 0, tzinfo=UTC),
        end_at_utc=datetime(2026, 10, 10, 0, tzinfo=UTC),
        session_limit=session_limit,
    )


def _approved_test_consent(_db: Session, learner_id: UUID, purpose: str) -> None:
    assert learner_id == LEARNER_ID
    assert purpose == service.CONSENT_PURPOSE_LEARNING_SUPPORT


class _SyntheticComponent4Store:
    """Test-only repository double preserving service ordering and learner scope."""

    def __init__(self, *, stored_ids: dict[UUID, UUID] | None = None) -> None:
        self.stored_ids = stored_ids or {}
        self.sessions: dict[tuple[UUID, UUID], ReadingSession] = {}
        self.history_calls = 0
        self.authorization_calls: list[tuple[UUID, LearnerAction, str]] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(service, "protect_principal_for_write", lambda _db, value: value)
        monkeypatch.setattr(
            service,
            "assert_protected_session_live",
            lambda _db, _principal: None,
        )
        monkeypatch.setattr(service, "authorize_learner_action", self.authorize)
        monkeypatch.setattr(repository, "get_session_by_client_id", self.get_session)
        monkeypatch.setattr(repository, "insert_reading_session", self.insert_session)
        monkeypatch.setattr(
            repository,
            "get_bounded_learner_session_history",
            self.get_history,
        )

    def authorize(
        self,
        _db: Session,
        principal: Principal,
        learner_id: UUID,
        action: LearnerAction,
    ) -> LearnerAuthorization:
        path: Literal["self", "guardian", "educator"]
        if learner_id != LEARNER_ID:
            raise SecurityError(404, "not_found", "Resource not found")
        if action == LearnerAction.PERFORM_LEARNING_INTERACTION and "learner" in principal.roles:
            path = "self"
        elif action == LearnerAction.READ_GUARDIAN_SUMMARY and "guardian" in principal.roles:
            path = "guardian"
        elif action == LearnerAction.READ_EDUCATIONAL_SUMMARY and "learner" in principal.roles:
            path = "self"
        elif action == LearnerAction.READ_EDUCATIONAL_SUMMARY and "educator" in principal.roles:
            path = "educator"
        else:
            raise SecurityError(404, "not_found", "Resource not found")
        self.authorization_calls.append((learner_id, action, path))
        return LearnerAuthorization(
            actor_id=principal.user_id,
            learner_id=learner_id,
            action=action,
            access_path=path,
            basic_profile_fields=frozenset(),
            consent_evaluated=False,
        )

    def get_session(
        self,
        _db: Session,
        learner_id: UUID,
        client_session_id: UUID,
        *,
        lock: bool = False,
    ) -> ReadingSession | None:
        del lock
        return self.sessions.get((learner_id, client_session_id))

    def insert_session(self, _db: Session, session: ReadingSession) -> ReadingSession:
        session.id = self.stored_ids.get(session.client_session_id, session.client_session_id)
        self.sessions[(session.learner_id, session.client_session_id)] = session
        return session

    def get_history(
        self,
        _db: Session,
        query: HistoricalSessionQuery,
    ) -> tuple[HistoricalSessionRecord, ...]:
        self.history_calls += 1
        selected = sorted(
            (
                session
                for session in self.sessions.values()
                if session.learner_id == query.learner_id
                and query.start_at_utc <= session.session_start_time < query.end_at_utc
            ),
            key=lambda session: (session.session_start_time, session.id),
        )
        if len(selected) > query.session_limit:
            raise HistoricalResultLimitExceeded(
                "Historical reading-session result exceeds the configured limit"
            )
        return tuple(
            HistoricalSessionRecord(
                id=session.id,
                session_start_time=session.session_start_time,
                task_type=session.task_type,
                difficulty_tier=session.difficulty_tier,
                support_mode=session.support_mode,
                completion_status=session.completion_status,
                words_attempted=session.words_attempted,
                words_correct=session.words_correct,
                target_word_count=session.target_word_count,
                active_duration_ms=session.active_duration_ms,
                total_duration_ms=session.total_duration_ms,
                hesitation_count=session.hesitation_count,
                total_pause_duration_ms=session.total_pause_duration_ms,
            )
            for session in selected
        )


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        return keys | set().union(*(_all_keys(item) for item in value.values()), set())
    if isinstance(value, (list, tuple)):
        return set().union(*(_all_keys(item) for item in value), set())
    return set()


def _ingest(
    db: Session,
    principal: Principal,
    payload: ReadingSessionIngest,
) -> tuple[ReadingSession, bool]:
    return service.ingest_reading_session(
        db,
        principal,
        payload,
        consent_checker=_approved_test_consent,
    )


def test_integrated_ingest_history_dashboards_and_advisory_adaptation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)

    completed = tuple(_payload(day) for day in range(1, 7))
    abandoned = _payload(
        7,
        completion_status="abandoned",
        words_attempted=0,
        words_correct=0,
        active_duration_ms=0,
        hesitation_count=None,
    )
    interrupted = _payload(
        8,
        completion_status="interrupted",
        words_attempted=50,
        words_correct=40,
        active_duration_ms=0,
        hesitation_count=None,
    )

    for payload in (*completed, abandoned, interrupted):
        stored, is_new = _ingest(db, learner, payload)
        assert is_new is True
        assert stored.completion_status == payload.completion_status
        if payload.completion_status == "completed":
            assert stored.calculated_accuracy == Decimal("0.9600")
            assert stored.calculated_wpm == Decimal("100.00")
            assert stored.calculated_hesitation_rate == Decimal("0.0200")

    exact_retry, is_new = _ingest(db, learner, completed[0])
    assert is_new is False
    assert exact_retry.client_session_id == completed[0].client_session_id

    conflicting_retry = _payload(1, words_correct=95)
    with pytest.raises(SecurityError) as conflict:
        _ingest(db, learner, conflicting_retry)
    assert (conflict.value.status, conflict.value.code) == (409, "digest_conflict")
    assert len(store.sessions) == 8

    query = _query()
    guardian = _principal("guardian", UUID("50000000-0000-4000-8000-000000000001"))
    educator = _principal("educator", UUID("60000000-0000-4000-8000-000000000001"))
    learner_projection = service.read_learner_progress(
        db, learner, query, consent_checker=_approved_test_consent
    )
    guardian_projection = service.read_guardian_summary(
        db, guardian, query, consent_checker=_approved_test_consent
    )
    educator_projection = service.read_educator_analytics(
        db, educator, query, consent_checker=_approved_test_consent
    )

    assert type(learner_projection) is LearnerProgressProjection
    assert type(guardian_projection) is GuardianSummaryProjection
    assert type(educator_projection) is EducatorAnalyticsProjection
    assert learner_projection.included_session_count == 8
    assert guardian_projection.included_session_count == 8
    assert educator_projection.included_session_count == 8
    assert store.history_calls == 3

    educator_metrics = {
        metric.metric_name: metric
        for partition in educator_projection.partitions
        for metric in partition.metrics
    }
    assert educator_metrics["reading_accuracy"].missing_observation_count == 1
    assert educator_metrics["reading_fluency_wpm"].missing_observation_count == 2
    assert educator_metrics["hesitation_rate_per_word"].missing_observation_count == 2

    forbidden = {
        "learner_id",
        "session_id",
        "client_session_id",
        "document_id",
        "request_digest",
        "calculated_engagement_score",
        "authorization",
        "consent",
    }
    learner_keys = _all_keys(learner_projection.model_dump(mode="json"))
    guardian_keys = _all_keys(guardian_projection.model_dump(mode="json"))
    educator_keys = _all_keys(educator_projection.model_dump(mode="json"))
    assert forbidden.isdisjoint(learner_keys | guardian_keys | educator_keys)
    assert "early_window_mean" not in learner_keys
    assert "early_window_mean" not in guardian_keys
    assert "early_window_mean" in educator_keys

    records = store.get_history(db, query)
    assert {record.completion_status for record in records} == {
        "completed",
        "abandoned",
        "interrupted",
    }
    evidence = select_completed_session_evidence(records, query)
    assert evidence.report.included_session_count == 6
    adaptation_input = map_longitudinal_partition_to_adaptation_input(
        evidence,
        PartitionKey("independent_reading", "intermediate", "adaptive"),
        support_preferences=SupportPreferences(),
        manual_override_locked=False,
    )
    decision = recommend_adaptation(adaptation_input)

    assert adaptation_input.session_count == 6
    assert adaptation_input.evidence_window_sufficient is True
    assert decision.action == "increase_difficulty"
    assert decision.is_advisory is True
    assert decision.safe_to_apply_automatically is False
    assert len(store.sessions) == 8
    db.commit.assert_not_called()


def test_integrated_security_ordering_and_sanitized_consent_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    consent = MagicMock()

    with pytest.raises(SecurityError) as isolated:
        service.read_learner_progress(
            db,
            learner,
            _query(learner_id=OTHER_LEARNER_ID),
            consent_checker=consent,
        )
    assert (isolated.value.status, isolated.value.code, str(isolated.value)) == (
        404,
        "not_found",
        "Resource not found",
    )
    consent.assert_not_called()
    assert store.history_calls == 0

    with pytest.raises(SecurityError) as missing_consent:
        service.read_learner_progress(db, learner, _query())
    assert (missing_consent.value.status, missing_consent.value.code) == (
        403,
        "consent_required",
    )
    assert str(LEARNER_ID) not in str(missing_consent.value)
    assert store.history_calls == 0

    def broken_consent(_db: Session, _learner_id: UUID, _purpose: str) -> None:
        raise RuntimeError(f"private consent internals for {LEARNER_ID}")

    with pytest.raises(SecurityError) as unavailable:
        service.read_learner_progress(
            db,
            learner,
            _query(),
            consent_checker=broken_consent,
        )
    assert (unavailable.value.status, unavailable.value.code, str(unavailable.value)) == (
        503,
        "service_unavailable",
        "Service unavailable",
    )
    assert str(LEARNER_ID) not in str(unavailable.value)
    assert store.history_calls == 0


def test_integrated_history_and_adaptation_evidence_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    for day in range(1, 4):
        _ingest(db, learner, _payload(day))

    limited_query = _query(session_limit=2)
    with pytest.raises(HistoricalResultLimitExceeded) as overflow:
        service.read_learner_progress(
            db,
            learner,
            limited_query,
            consent_checker=_approved_test_consent,
        )
    assert str(overflow.value) == "Historical reading-session result exceeds the configured limit"
    assert str(LEARNER_ID) not in str(overflow.value)

    records = store.get_history(db, _query())
    with pytest.raises(AdaptationMappingError, match="bounded result limit"):
        select_completed_session_evidence(records, limited_query)

    with pytest.raises(HistoricalQueryValidationError, match="configured.*maximum"):
        HistoricalSessionQuery(
            learner_id=LEARNER_ID,
            start_at_utc=datetime(2026, 10, 1, tzinfo=UTC),
            end_at_utc=datetime(2026, 10, 2, tzinfo=UTC),
            session_limit=3,
            bounds=HistoricalQueryBounds(maximum_sessions=2),
        )

    assert "learner_id" not in json.dumps(
        service.read_learner_progress(
            db,
            learner,
            _query(),
            consent_checker=_approved_test_consent,
        ).model_dump(mode="json")
    )


@pytest.mark.parametrize("role", ["learner", "guardian", "educator"])
def test_json_session_to_role_factual_report_keeps_ai_inactive(
    role: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise receiving contracts, not an unimplemented Speech producer or real auth."""
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    for day in range(1, 7):
        # A future producer's serialized request must survive the actual ingest schema.
        wire = _payload(
            day, words_correct=60 + day * 3, hesitation_count=None if day == 1 else 2
        ).model_dump_json()
        payload = ReadingSessionIngest.model_validate_json(wire)
        stored, is_new = _ingest(db, learner, payload)
        assert is_new is True
        assert stored.hesitation_count == payload.hesitation_count

    readers = {
        "learner": service.read_learner_progress,
        "guardian": service.read_guardian_summary,
        "educator": service.read_educator_analytics,
    }
    actor = learner if role == "learner" else _principal(role, UUID(int=9000))
    projection = readers[role](db, actor, _query(), consent_checker=_approved_test_consent)
    result = asyncio.run(generate_progress_report(projection))
    assert result.status == "unavailable"
    assert result.unavailable_reason == "disabled"
    assert result.narrative is None
    assert result.factual_report.role == role
    assert result.factual_report.projection == projection
    assert result.factual_report.projection.included_session_count == 6
    statements = [item.text for item in result.factual_report.narrative_request.approved_statements]
    assert any("insufficient comparable evidence" in text for text in statements)
    assert any("first 0.6300, latest 0.7800" in text for text in statements)
    assert any("Advisory only" in text for text in statements)
    serialized = result.factual_report.narrative_request.model_dump_json()
    for forbidden in (
        str(LEARNER_ID),
        str(actor.user_id),
        "learner_id",
        "client_session_id",
        "document_id",
        "login_handle",
        "calculated_engagement_score",
    ):
        assert forbidden not in serialized
    assert store.history_calls == 1
    assert len(store.sessions) == 6
    db.execute.assert_not_called()
    db.connection.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("arrival_order", [(6, 5, 4, 3, 2, 1), (3, 1, 6, 2, 5, 4)])
def test_shuffled_finalized_sessions_preserve_progress_recommendations_and_report_evidence(
    arrival_order: tuple[int, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compare chronological and shuffled arrival through the same real service chain."""

    def simulate(order: tuple[int, ...]) -> tuple[object, ...]:
        store = _SyntheticComponent4Store()
        store.install(monkeypatch)
        db = MagicMock(spec=Session)
        learner = _principal("learner", LEARNER_ID)
        for day in order:
            payload = _payload(
                day,
                words_correct=60 + day * 3,
                active_duration_ms=120_000 - day * 10_000,
                total_duration_ms=130_000,
                hesitation_count=8 - day,
            )
            stored, is_new = _ingest(
                db, learner, ReadingSessionIngest.model_validate_json(payload.model_dump_json())
            )
            assert is_new is True
            if day == 6:
                assert stored.calculated_accuracy == Decimal("0.7800")
                assert stored.calculated_wpm == Decimal("100.00")
                assert stored.calculated_hesitation_rate == Decimal("0.0200")

        records = store.get_history(db, _query())
        assert [row.id for row in records] == [UUID(int=1000 + day) for day in range(1, 7)]
        evidence = select_completed_session_evidence(records, _query())
        decision = recommend_adaptation(
            map_longitudinal_partition_to_adaptation_input(
                evidence,
                PartitionKey("independent_reading", "intermediate", "adaptive"),
                support_preferences=SupportPreferences(),
                manual_override_locked=False,
            )
        )
        assert decision.is_advisory is True
        assert decision.safe_to_apply_automatically is False
        projections = (
            service.read_learner_progress(
                db, learner, _query(), consent_checker=_approved_test_consent
            ),
            service.read_guardian_summary(
                db,
                _principal("guardian", UUID(int=9001)),
                _query(),
                consent_checker=_approved_test_consent,
            ),
            service.read_educator_analytics(
                db,
                _principal("educator", UUID(int=9002)),
                _query(),
                consent_checker=_approved_test_consent,
            ),
        )
        metrics = {metric.metric_name: metric for metric in projections[0].contexts[0].metrics}
        assert metrics["reading_accuracy"].first_value == Decimal("0.6300")
        assert metrics["reading_accuracy"].latest_value == Decimal("0.7800")
        assert (
            metrics["reading_fluency_wpm"].first_value
            != metrics["reading_fluency_wpm"].latest_value
        )
        assert metrics["hesitation_rate_per_word"].first_value == Decimal("0.0700")
        assert metrics["hesitation_rate_per_word"].latest_value == Decimal("0.0200")
        reports = tuple(
            build_structured_report(projection).narrative_request for projection in projections
        )
        assert len({report.report_fingerprint for report in reports}) == 3
        db.execute.assert_not_called()
        db.connection.assert_not_called()
        db.commit.assert_not_called()
        return (*projections, decision, *reports)

    chronological = simulate((1, 2, 3, 4, 5, 6))
    shuffled = simulate(arrival_order)
    assert shuffled == chronological


def test_completed_sessions_with_missing_measurements_do_not_manufacture_advice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    for day in range(1, 7):
        payload = _payload(
            day,
            active_duration_ms=0 if day == 3 else 60_000,
            hesitation_count=None if day == 3 else 2,
        )
        stored, _ = _ingest(db, learner, payload)
        if day == 3:
            assert stored.calculated_wpm is None
            assert stored.calculated_hesitation_rate is None
    projection = service.read_educator_analytics(
        db, _principal("educator", UUID(int=9002)), _query(), consent_checker=_approved_test_consent
    )
    metrics = {metric.metric_name: metric for metric in projection.partitions[0].metrics}
    assert metrics["reading_accuracy"].valid_observation_count == 6
    for name in ("reading_fluency_wpm", "hesitation_rate_per_word"):
        assert metrics[name].valid_observation_count == 5
        assert metrics[name].missing_observation_count == 1
        assert metrics[name].change_direction == "insufficient_evidence"
    evidence = select_completed_session_evidence(store.get_history(db, _query()), _query())
    adaptation = map_longitudinal_partition_to_adaptation_input(
        evidence,
        PartitionKey("independent_reading", "intermediate", "adaptive"),
        support_preferences=SupportPreferences(),
        manual_override_locked=False,
    )
    assert adaptation.session_count == 6
    assert adaptation.mean_wpm is None
    assert adaptation.mean_hesitation_rate_per_word is None
    assert adaptation.evidence_window_sufficient is False
    decision = recommend_adaptation(adaptation)
    assert decision.action == "insufficient_evidence"
    assert decision.safe_to_apply_automatically is False
    report = build_structured_report(projection)
    assert (
        sum(
            "insufficient comparable evidence" in item.text
            for item in report.narrative_request.approved_statements
        )
        == 2
    )
    assert any(
        "Missing values are not zero" in item.text
        for item in report.narrative_request.approved_statements
    )
    assert len(store.sessions) == 6
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"words_correct": 101},
        {"words_attempted": -1},
        {"active_duration_ms": 70_001},
        {"session_start_time": "2026-10-07T09:00:00"},
        {"session_end_time": "2026-10-06T09:00:00+00:00"},
        {"client_session_id": "not-a-uuid"},
        {"completion_status": "pending"},
        {"calculated_accuracy": 0.99},
    ],
)
def test_invalid_finalized_candidate_cannot_change_ingested_progress(
    changes: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    _ingest(db, learner, _payload(1))
    before = service.read_learner_progress(
        db, learner, _query(), consent_checker=_approved_test_consent
    )
    candidate = _payload(7).model_dump(mode="json")
    candidate.update(changes)
    with pytest.raises(ValidationError):
        _ingest(db, learner, ReadingSessionIngest.model_validate_json(json.dumps(candidate)))
    after = service.read_learner_progress(
        db, learner, _query(), consent_checker=_approved_test_consent
    )
    assert before == after
    assert len(store.sessions) == 1
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("missing_checker", [True, False])
def test_exact_retry_still_requires_current_consent_before_lookup(
    missing_checker: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    payload = _payload(1)
    original, _ = _ingest(db, learner, payload)
    lookup = MagicMock(wraps=store.get_session)
    monkeypatch.setattr(repository, "get_session_by_client_id", lookup)
    withdrawn = MagicMock(side_effect=SecurityError(403, "consent_required", "Consent required"))
    with pytest.raises(SecurityError) as denied:
        service.ingest_reading_session(
            db, learner, payload, consent_checker=None if missing_checker else withdrawn
        )
    assert (denied.value.status, denied.value.code) == (403, "consent_required")
    lookup.assert_not_called()
    assert list(store.sessions.values()) == [original]
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "other_context",
    [
        {"task_type": "guided_echo_reading"},
        {"difficulty_tier": "advanced"},
        {"support_mode": "baseline_fixed"},
    ],
)
@pytest.mark.parametrize("primary_count", [3, 6])
@pytest.mark.parametrize("reverse_arrival", [False, True])
def test_distinct_contexts_cannot_supply_each_others_progress_or_recommendation_evidence(
    other_context: dict[str, str],
    primary_count: int,
    reverse_arrival: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    primary = tuple(_payload(day) for day in range(1, primary_count + 1))
    for payload in reversed(primary) if reverse_arrival else primary:
        _ingest(db, learner, payload)

    def projections() -> tuple[
        LearnerProgressProjection, GuardianSummaryProjection, EducatorAnalyticsProjection
    ]:
        return (
            service.read_learner_progress(
                db, learner, _query(), consent_checker=_approved_test_consent
            ),
            service.read_guardian_summary(
                db,
                _principal("guardian", UUID(int=9001)),
                _query(),
                consent_checker=_approved_test_consent,
            ),
            service.read_educator_analytics(
                db,
                _principal("educator", UUID(int=9002)),
                _query(),
                consent_checker=_approved_test_consent,
            ),
        )

    key = PartitionKey("independent_reading", "intermediate", "adaptive")

    def primary_recommendation() -> AdaptationDecision:
        evidence = select_completed_session_evidence(store.get_history(db, _query()), _query())
        adaptation = map_longitudinal_partition_to_adaptation_input(
            evidence, key, support_preferences=SupportPreferences(), manual_override_locked=False
        )
        assert adaptation.session_count == primary_count
        assert adaptation.mean_accuracy == pytest.approx(0.96)
        assert adaptation.mean_wpm == pytest.approx(100)
        assert adaptation.mean_hesitation_rate_per_word == pytest.approx(0.02)
        return recommend_adaptation(adaptation)

    before = projections()
    before_decision = primary_recommendation()
    other = tuple(
        _payload(
            day,
            words_correct=10,
            active_duration_ms=180_000,
            total_duration_ms=190_000,
            hesitation_count=None,
            **other_context,
        )
        for day in (7, 8, 9)
    )
    for payload in reversed(other) if reverse_arrival else other:
        _ingest(db, learner, payload)
    count_before_retry = len(store.sessions)
    for payload in (*reversed(primary), *reversed(other)):
        _, is_new = _ingest(
            db, learner, ReadingSessionIngest.model_validate_json(payload.model_dump_json())
        )
        assert is_new is False
    assert len(store.sessions) == count_before_retry == primary_count + 3
    after = projections()
    assert before[0].contexts[0] in after[0].contexts
    assert before[1].contexts[0] in after[1].contexts
    assert before[2].partitions[0] in after[2].partitions
    assert primary_recommendation() == before_decision
    assert before_decision.is_advisory is True
    assert before_decision.safe_to_apply_automatically is False

    for projection in after:
        assert projection.included_session_count == primary_count + 3
        serialized = projection.model_dump(mode="json")
        keys = _all_keys(serialized)
        assert {
            "learner_id",
            "session_id",
            "client_session_id",
            "document_id",
            "request_digest",
            "calculated_engagement_score",
        }.isdisjoint(keys)
        if isinstance(projection, EducatorAnalyticsProjection):
            assert "early_window_mean" in keys
        else:
            assert "early_window_mean" not in keys
        if isinstance(projection, LearnerProgressProjection):
            assert "valid_observation_count" not in keys
        report = build_structured_report(projection)
        assert report.advisory_only is True
        assert any(
            "insufficient comparable evidence" in item.text
            for item in report.narrative_request.approved_statements
        )

    partitions = after[2].partitions
    assert len(partitions) == 2
    primary_partition = next(
        item
        for item in partitions
        if (item.task_type, item.difficulty_tier, item.support_mode)
        == (key.task_type, key.difficulty_tier, key.support_mode)
    )
    other_partition = next(item for item in partitions if item != primary_partition)
    assert primary_partition.session_count == primary_count
    assert other_partition.session_count == 3
    for metric in primary_partition.metrics:
        assert metric.valid_observation_count == primary_count
        assert metric.evidence_sufficient is (primary_count == 6)
    other_metrics = {item.metric_name: item for item in other_partition.metrics}
    assert other_metrics["reading_accuracy"].first_value == Decimal("0.1000")
    assert other_metrics["reading_accuracy"].evidence_sufficient is False
    missing = other_metrics["hesitation_rate_per_word"]
    assert missing.first_value is None and missing.latest_value is None
    assert missing.valid_observation_count == 0
    assert missing.missing_observation_count == 3
    db.execute.assert_not_called()
    db.connection.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "support_mode,locked",
    [
        ("adaptive", False),
        ("adaptive", True),
        ("manual_override", False),
        ("manual_override", True),
        ("baseline_fixed", False),
        ("baseline_fixed", True),
    ],
)
@pytest.mark.parametrize("limited", [False, True])
def test_ingested_context_manual_lock_precedence_preserves_support_preferences(
    support_mode: str,
    locked: bool,
    limited: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    for day in range(1, 2 if limited else 7):
        _ingest(
            db,
            learner,
            _payload(day, support_mode=support_mode, hesitation_count=None if limited else 2),
        )
    preferences = SupportPreferences(
        speech_rate_multiplier=0.8,
        enable_line_focus=True,
        enable_visual_pacing=True,
        visual_pacing_rate_wpm=70,
    )
    before_preferences = asdict(preferences)
    before_sessions = tuple(
        (row.client_session_id, row.support_mode) for row in store.sessions.values()
    )
    evidence = select_completed_session_evidence(store.get_history(db, _query()), _query())
    adaptation = map_longitudinal_partition_to_adaptation_input(
        evidence,
        PartitionKey("independent_reading", "intermediate", support_mode),
        support_preferences=preferences,
        manual_override_locked=locked,
    )
    assert adaptation.manual_override_locked is locked
    assert adaptation.support_preferences is preferences
    assert adaptation.evidence_window_sufficient is (not limited)
    decision = recommend_adaptation(adaptation)
    assert decision.is_advisory is True
    assert decision.safe_to_apply_automatically is False
    if support_mode == "baseline_fixed":
        assert decision.action == "maintain"
        assert decision.reason_codes == ("baseline_fixed_mode",)
        assert decision.blocked_by_manual_override is False
    elif support_mode == "manual_override" or locked:
        assert decision.action == "maintain"
        assert decision.reason_codes == (
            ("manual_override_locked" if locked else "manual_override_active"),
        )
        assert decision.blocked_by_manual_override is True
    elif limited:
        assert decision.action == "insufficient_evidence"
    else:
        assert decision.action == "increase_difficulty"
    if support_mode != "adaptive" or locked:
        assert decision.recommended_difficulty_tier == "intermediate"
        assert decision.recommended_support_mode == support_mode
        assert decision.support_adjustments == ()
    assert asdict(preferences) == before_preferences
    assert (
        tuple((row.client_session_id, row.support_mode) for row in store.sessions.values())
        == before_sessions
    )
    db.add.assert_not_called()
    db.execute.assert_not_called()
    db.connection.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("order", ["forward", "reverse", "shuffled"])
@pytest.mark.parametrize("offset_hours", [0, 5.5])
@pytest.mark.parametrize("missing_hesitation", [False, True])
def test_half_open_window_excludes_outside_measurements_from_every_downstream_output(
    order: str,
    offset_hours: float,
    missing_hesitation: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zone = timezone(timedelta(hours=offset_hours))
    start = datetime(2026, 10, 3, 9, tzinfo=UTC)
    end = datetime(2026, 10, 6, 9, tzinfo=UTC)
    query = HistoricalSessionQuery(
        learner_id=LEARNER_ID,
        start_at_utc=start.astimezone(zone),
        end_at_utc=end.astimezone(zone),
        session_limit=6,
    )
    assert query.start_at_utc.tzinfo is UTC and query.end_at_utc.tzinfo is UTC
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    times = (
        start,
        start + timedelta(seconds=1),
        start + timedelta(days=1),
        start + timedelta(days=1, seconds=1),
        start + timedelta(days=2),
        end - timedelta(microseconds=1),
    )
    payloads = tuple(
        _payload(
            1,
            client_session_id=UUID(int=2000 + index),
            session_start_time=instant.astimezone(zone),
            words_correct=63 + index * 3,
            hesitation_count=None if missing_hesitation and index == 2 else 2,
        )
        for index, instant in enumerate(times)
    )
    indices = (
        tuple(range(6))
        if order == "forward"
        else ((5, 4, 3, 2, 1, 0) if order == "reverse" else (3, 0, 5, 1, 4, 2))
    )
    for index in indices:
        _ingest(db, learner, payloads[index])

    def outputs() -> tuple[object, ...]:
        records = store.get_history(db, query)
        assert [row.id for row in records] == [payload.client_session_id for payload in payloads]
        evidence = select_completed_session_evidence(records, query)
        adaptation = map_longitudinal_partition_to_adaptation_input(
            evidence,
            PartitionKey("independent_reading", "intermediate", "adaptive"),
            support_preferences=SupportPreferences(),
            manual_override_locked=False,
        )
        assert adaptation.session_count == 6
        assert adaptation.mean_accuracy == pytest.approx(0.705)
        assert adaptation.mean_wpm == pytest.approx(100)
        if missing_hesitation:
            assert adaptation.mean_hesitation_rate_per_word is None
        else:
            assert adaptation.mean_hesitation_rate_per_word == pytest.approx(0.02)
        decision = recommend_adaptation(adaptation)
        assert decision.is_advisory is True and decision.safe_to_apply_automatically is False
        if missing_hesitation:
            assert decision.action == "insufficient_evidence"
        projections = (
            service.read_learner_progress(
                db, learner, query, consent_checker=_approved_test_consent
            ),
            service.read_guardian_summary(
                db,
                _principal("guardian", UUID(int=9001)),
                query,
                consent_checker=_approved_test_consent,
            ),
            service.read_educator_analytics(
                db,
                _principal("educator", UUID(int=9002)),
                query,
                consent_checker=_approved_test_consent,
            ),
        )
        metrics = {item.metric_name: item for item in projections[2].partitions[0].metrics}
        assert metrics["reading_accuracy"].first_value == Decimal("0.6300")
        assert metrics["reading_accuracy"].latest_value == Decimal("0.7800")
        assert metrics["reading_accuracy"].early_window_mean == Decimal("0.6600")
        assert metrics["reading_accuracy"].late_window_mean == Decimal("0.7500")
        assert metrics["hesitation_rate_per_word"].missing_observation_count == int(
            missing_hesitation
        )
        reports = tuple(build_structured_report(item).narrative_request for item in projections)
        for projection, report in zip(projections, reports, strict=True):
            assert projection.included_session_count == 6
            assert projection.reporting_period.start_at_utc == start
            assert projection.reporting_period.end_at_utc == end
            keys = _all_keys(projection.model_dump(mode="json"))
            assert {"learner_id", "session_id", "client_session_id", "document_id"}.isdisjoint(keys)
            assert ("early_window_mean" in keys) is isinstance(
                projection, EducatorAnalyticsProjection
            )
            assert "0.0100" not in report.model_dump_json()
            assert report.role in {"learner", "guardian", "educator"}
        return (*projections, decision, *reports)

    baseline = outputs()
    outside_times = (start - timedelta(microseconds=1), end, end + timedelta(microseconds=1))
    for index, instant in enumerate(outside_times):
        _ingest(
            db,
            learner,
            _payload(
                1,
                client_session_id=UUID(int=3000 + index),
                session_start_time=instant.astimezone(zone),
                words_correct=1,
                hesitation_count=99,
            ),
        )
    # Duplicate delivery with a different UTC offset is still the identical logical request.
    for payload in reversed(payloads):
        candidate = payload.model_dump()
        candidate.update(
            session_start_time=payload.session_start_time.astimezone(UTC),
            session_end_time=payload.session_end_time.astimezone(UTC),
        )
        _, is_new = _ingest(db, learner, ReadingSessionIngest.model_validate(candidate))
        assert is_new is False
    assert len(store.sessions) == 9
    assert outputs() == baseline
    # The mapper requires already-windowed history; it rejects, rather than silently drops,
    # out-of-window records if a caller violates that boundary.
    broad = HistoricalSessionQuery(
        learner_id=LEARNER_ID,
        start_at_utc=start - timedelta(days=1),
        end_at_utc=end + timedelta(days=1),
    )
    broad_records = store.get_history(db, broad)
    with pytest.raises(AdaptationMappingError, match="bounded result limit"):
        select_completed_session_evidence(broad_records, query)
    guard_query = HistoricalSessionQuery(
        learner_id=LEARNER_ID, start_at_utc=start, end_at_utc=end, session_limit=9
    )
    with pytest.raises(AdaptationMappingError, match="outside"):
        select_completed_session_evidence(broad_records, guard_query)
    db.execute.assert_not_called()
    db.connection.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("order", [(0, 1, 2, 3, 4, 5), (5, 4, 3, 2, 1, 0), (2, 5, 0, 4, 1, 3)])
def test_equal_time_order_uses_fixed_stored_row_ids_not_client_ids_or_arrival(
    order: tuple[int, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instant = datetime(2026, 10, 4, 9, tzinfo=UTC)
    client_ids = tuple(UUID(int=5000 + index) for index in range(6))
    row_ids = tuple(UUID(int=6005 - index) for index in range(6))
    store = _SyntheticComponent4Store(stored_ids=dict(zip(client_ids, row_ids, strict=True)))
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    for index in order:
        payload = _payload(
            1,
            session_start_time=instant,
            client_session_id=client_ids[index],
            words_correct=60 + index * 5,
        )
        _ingest(db, learner, payload)
        _, is_new = _ingest(
            db, learner, ReadingSessionIngest.model_validate_json(payload.model_dump_json())
        )
        assert is_new is False
    records = store.get_history(db, _query())
    assert [row.id for row in records] == sorted(row_ids)
    evidence = select_completed_session_evidence(records, _query())
    adaptation = map_longitudinal_partition_to_adaptation_input(
        evidence,
        PartitionKey("independent_reading", "intermediate", "adaptive"),
        support_preferences=SupportPreferences(),
        manual_override_locked=False,
    )
    assert adaptation.mean_accuracy == pytest.approx(0.725)
    projections = (
        service.read_learner_progress(
            db, learner, _query(), consent_checker=_approved_test_consent
        ),
        service.read_guardian_summary(
            db,
            _principal("guardian", UUID(int=9001)),
            _query(),
            consent_checker=_approved_test_consent,
        ),
        service.read_educator_analytics(
            db,
            _principal("educator", UUID(int=9002)),
            _query(),
            consent_checker=_approved_test_consent,
        ),
    )
    metrics = {item.metric_name: item for item in projections[2].partitions[0].metrics}
    accuracy = metrics["reading_accuracy"]
    assert accuracy.first_value == Decimal("0.8500")
    assert accuracy.latest_value == Decimal("0.6000")
    assert accuracy.early_window_mean == Decimal("0.8000")
    assert accuracy.late_window_mean == Decimal("0.6500")
    for projection in projections:
        report = build_structured_report(projection)
        assert any(
            "first 0.8500, latest 0.6000" in item.text
            for item in report.narrative_request.approved_statements
        )
        assert projection.included_session_count == 6
    decision = recommend_adaptation(adaptation)
    assert decision.is_advisory is True and decision.safe_to_apply_automatically is False
    reversed_evidence = select_completed_session_evidence(tuple(reversed(records)), _query())
    reversed_adaptation = map_longitudinal_partition_to_adaptation_input(
        reversed_evidence,
        PartitionKey("independent_reading", "intermediate", "adaptive"),
        support_preferences=SupportPreferences(),
        manual_override_locked=False,
    )
    assert recommend_adaptation(reversed_adaptation) == decision
    # Exercise the analytics sort independently of the repository double's sort.
    monkeypatch.setattr(
        repository,
        "get_bounded_learner_session_history",
        lambda _db, _query: tuple(reversed(records)),
    )
    reversed_projections = (
        service.read_learner_progress(
            db, learner, _query(), consent_checker=_approved_test_consent
        ),
        service.read_guardian_summary(
            db,
            _principal("guardian", UUID(int=9001)),
            _query(),
            consent_checker=_approved_test_consent,
        ),
        service.read_educator_analytics(
            db,
            _principal("educator", UUID(int=9002)),
            _query(),
            consent_checker=_approved_test_consent,
        ),
    )
    assert reversed_projections == projections
    assert tuple(
        build_structured_report(item).narrative_request for item in reversed_projections
    ) == tuple(build_structured_report(item).narrative_request for item in projections)
    assert len(store.sessions) == 6
    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_empty_reporting_window_has_no_context_no_measurements_and_no_invented_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    _ingest(db, learner, _payload(1, words_correct=1))
    start = datetime(2026, 10, 15, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    query = HistoricalSessionQuery(
        learner_id=LEARNER_ID, start_at_utc=start, end_at_utc=start + timedelta(days=1)
    )
    records = store.get_history(db, query)
    assert records == ()
    evidence = select_completed_session_evidence(records, query)
    assert evidence.report.included_session_count == 0
    with pytest.raises(AdaptationMappingError, match="exactly one matching partition"):
        map_longitudinal_partition_to_adaptation_input(
            evidence,
            PartitionKey("independent_reading", "intermediate", "adaptive"),
            support_preferences=SupportPreferences(),
            manual_override_locked=False,
        )
    projections = (
        service.read_learner_progress(db, learner, query, consent_checker=_approved_test_consent),
        service.read_guardian_summary(
            db,
            _principal("guardian", UUID(int=9001)),
            query,
            consent_checker=_approved_test_consent,
        ),
        service.read_educator_analytics(
            db,
            _principal("educator", UUID(int=9002)),
            query,
            consent_checker=_approved_test_consent,
        ),
    )
    for projection in projections:
        assert projection.included_session_count == 0
        contexts = (
            projection.partitions
            if isinstance(projection, EducatorAnalyticsProjection)
            else projection.contexts
        )
        assert contexts == ()
        report = build_structured_report(projection)
        statements = [item.text for item in report.narrative_request.approved_statements]
        assert "The reporting period contains 0 recorded sessions." in statements
        assert not any("first " in text or "latest " in text for text in statements)
        assert report.advisory_only is True
    assert len(store.sessions) == 1
    db.execute.assert_not_called()
    db.connection.assert_not_called()
    db.commit.assert_not_called()


def _integrity_history(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_SyntheticComponent4Store, MagicMock, Principal, tuple[HistoricalSessionRecord, ...]]:
    """Reuse finalized fixtures and the real ingest service; all persistence is mocked."""
    store = _SyntheticComponent4Store()
    store.install(monkeypatch)
    db = MagicMock(spec=Session)
    learner = _principal("learner", LEARNER_ID)
    for day in range(1, 7):
        _ingest(db, learner, _payload(day))
    return store, db, learner, store.get_history(db, _query())


@pytest.mark.parametrize("role", ["learner", "guardian", "educator"])
@pytest.mark.parametrize(
    "changes",
    [
        {"words_correct": 101},
        {"words_attempted": -1},
        {"words_correct": float("nan")},
        {"active_duration_ms": float("inf")},
        {"active_duration_ms": 70_001},
        {"target_word_count": None},
        {"words_attempted": True},
        {"hesitation_count": -1},
        {"total_pause_duration_ms": 70_001},
        {"task_type": None},
        {"difficulty_tier": ""},
        {"support_mode": "unsupported"},
        {"completion_status": "pending"},
        {"session_start_time": datetime(2026, 10, 2)},
    ],
)
def test_malformed_historical_batch_blocks_projection_report_and_recommendation(
    role: str,
    changes: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, db, learner, records = _integrity_history(monkeypatch)
    bad = replace(records[2], **changes)
    corrupted = (*records[:2], bad, *records[3:])
    monkeypatch.setattr(repository, "get_bounded_learner_session_history", lambda *_: corrupted)
    readers = {
        "learner": service.read_learner_progress,
        "guardian": service.read_guardian_summary,
        "educator": service.read_educator_analytics,
    }
    actor = learner if role == "learner" else _principal(role, UUID(int=9001))
    build = MagicMock(wraps=build_structured_report)
    with pytest.raises(HistoricalDataIntegrityError) as rejected:
        build(readers[role](db, actor, _query(), consent_checker=_approved_test_consent))
    assert str(rejected.value) == "Stored reading-session data is invalid"
    build.assert_not_called()
    recommendation = MagicMock(wraps=recommend_adaptation)
    with pytest.raises(AdaptationMappingError):
        recommendation(
            map_longitudinal_partition_to_adaptation_input(
                select_completed_session_evidence(corrupted, _query()),
                PartitionKey("independent_reading", "intermediate", "adaptive"),
                support_preferences=SupportPreferences(),
                manual_override_locked=False,
            )
        )
    recommendation.assert_not_called()
    assert len(store.sessions) == 6
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("role", ["learner", "guardian", "educator"])
@pytest.mark.parametrize("conflict", ["identical", "different_values", "different_completion"])
def test_duplicate_stored_identity_cannot_inflate_any_projection_or_completed_evidence(
    role: str,
    conflict: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, db, learner, records = _integrity_history(monkeypatch)
    duplicate = records[0]
    if conflict == "different_values":
        duplicate = replace(duplicate, words_correct=1)
    elif conflict == "different_completion":
        duplicate = replace(duplicate, completion_status="abandoned")
    corrupted = (*reversed(records), duplicate)
    monkeypatch.setattr(repository, "get_bounded_learner_session_history", lambda *_: corrupted)
    readers = {
        "learner": service.read_learner_progress,
        "guardian": service.read_guardian_summary,
        "educator": service.read_educator_analytics,
    }
    actor = learner if role == "learner" else _principal(role, UUID(int=9001))
    build = MagicMock(wraps=build_structured_report)
    with pytest.raises(ValueError, match="session_id values must be unique"):
        build(readers[role](db, actor, _query(), consent_checker=_approved_test_consent))
    build.assert_not_called()
    with pytest.raises(AdaptationMappingError, match="identities must be unique"):
        select_completed_session_evidence(corrupted, _query())
    assert len(store.sessions) == 6
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"words_correct": 95},
        {"completion_status": "abandoned"},
        {"task_type": "guided_echo_reading"},
        {"session_start_time": datetime(2026, 10, 1, 9, 1, tzinfo=UTC)},
    ],
)
def test_retry_identity_rejects_corrections_without_changing_factual_evidence(
    changes: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, db, learner, _ = _integrity_history(monkeypatch)
    before = service.read_learner_progress(
        db, learner, _query(), consent_checker=_approved_test_consent
    )
    request_before = build_structured_report(before).narrative_request
    for _ in range(3):
        for day in range(6, 0, -1):
            _, is_new = _ingest(db, learner, _payload(day))
            assert is_new is False
    candidate = _payload(1).model_dump()
    candidate.update(changes)
    with pytest.raises(SecurityError) as conflict:
        _ingest(db, learner, ReadingSessionIngest.model_validate(candidate))
    assert (conflict.value.status, conflict.value.code) == (409, "digest_conflict")
    after = service.read_learner_progress(
        db, learner, _query(), consent_checker=_approved_test_consent
    )
    assert after == before
    assert build_structured_report(after).narrative_request == request_before
    assert len(store.sessions) == 6
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("version", ["v0.1-early-late-3", "unsupported-v999", ""])
def test_existing_longitudinal_report_version_contract_at_historical_boundary(
    version: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, db, _, records = _integrity_history(monkeypatch)
    evidence = select_completed_session_evidence(records, _query())
    candidate = evidence.report.model_dump()
    candidate["longitudinal_calculation_version"] = version
    if version == "v0.1-early-late-3":
        report = LongitudinalProgressReport.model_validate(candidate)
        assert report == evidence.report
        for projector in (
            project_learner_progress,
            project_guardian_summary,
            project_educator_analytics,
        ):
            assert build_structured_report(projector(report)).advisory_only is True
    else:
        with pytest.raises(ValidationError):
            LongitudinalProgressReport.model_validate(candidate)
    db.execute.assert_not_called()


@pytest.mark.parametrize(
    "versions",
    [
        ("synthetic-formula-a",) * 6,
        ("synthetic-formula-a",) * 3 + ("synthetic-formula-b",) * 3,
    ],
)
def test_explicit_engagement_version_metadata_is_not_silently_combined_or_disclosed(
    versions: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, db, _, records = _integrity_history(monkeypatch)
    baseline = select_completed_session_evidence(records, _query())
    observations = historical_records_to_observations(records)
    # Version labels belong to the observation contract, NOT a nonexistent stored schema field.
    versioned = tuple(
        replace(item, engagement_score=Decimal("0.5"), engagement_formula_version=version)
        for item, version in zip(observations, versions, strict=True)
    )
    evidence = CompletedSessionEvidence.from_observations(versioned, baseline.report.window)
    metric = next(
        item
        for item in evidence.report.partitions[0].metrics
        if item.metric_name == "engagement_score"
    )
    mixed = len(set(versions)) > 1
    assert metric.evidence_sufficient is (not mixed)
    assert metric.comparison_blocker == ("mixed_metric_versions" if mixed else None)
    adaptation = map_longitudinal_partition_to_adaptation_input(
        evidence,
        PartitionKey("independent_reading", "intermediate", "adaptive"),
        support_preferences=SupportPreferences(),
        manual_override_locked=False,
    )
    assert adaptation.mean_engagement_score == (None if mixed else 0.5)
    assert (
        adaptation.evidence_window_sufficient is True
    )  # Core educational metrics remain complete.
    decision = recommend_adaptation(adaptation)
    assert decision.is_advisory is True and decision.safe_to_apply_automatically is False
    for projector in (
        project_learner_progress,
        project_guardian_summary,
        project_educator_analytics,
    ):
        projection = projector(evidence.report)
        report = build_structured_report(projection)
        assert (
            report.narrative_request
            == build_structured_report(projector(baseline.report)).narrative_request
        )
        serialized = projection.model_dump_json() + report.narrative_request.model_dump_json()
        assert "engagement_score" not in serialized
        assert "synthetic-formula" not in serialized
    db.execute.assert_not_called()


def test_incomplete_sessions_cannot_be_promoted_by_retry_or_completed_evidence_constructor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, db, learner, _ = _integrity_history(monkeypatch)
    abandoned = _payload(7, completion_status="abandoned", words_correct=1)
    _ingest(db, learner, abandoned)
    records = store.get_history(db, _query())
    assert len(records) == 7
    evidence = select_completed_session_evidence(records, _query())
    assert evidence.report.included_session_count == 6
    observations = historical_records_to_observations(records)
    with pytest.raises(AdaptationMappingError, match="only completed sessions"):
        CompletedSessionEvidence.from_observations(observations, evidence.report.window)
    changed = abandoned.model_dump()
    changed["completion_status"] = "completed"
    with pytest.raises(SecurityError) as conflict:
        _ingest(db, learner, ReadingSessionIngest.model_validate(changed))
    assert conflict.value.code == "digest_conflict"
    assert (
        store.sessions[(LEARNER_ID, abandoned.client_session_id)].completion_status == "abandoned"
    )
    assert len(store.sessions) == 7
    db.execute.assert_not_called()


def test_historical_reports_recompute_metrics_instead_of_trusting_corrupted_cached_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, db, learner, _ = _integrity_history(monkeypatch)
    before = service.read_learner_progress(
        db, learner, _query(), consent_checker=_approved_test_consent
    )
    for row in store.sessions.values():
        row.calculated_accuracy = Decimal("999")
        row.calculated_wpm = Decimal("Infinity")
        row.calculated_hesitation_rate = Decimal("NaN")
        row.engagement_formula_version = "unsupported-cached-formula"
    after = service.read_learner_progress(
        db, learner, _query(), consent_checker=_approved_test_consent
    )
    assert after == before
    assert (
        build_structured_report(after).narrative_request
        == build_structured_report(before).narrative_request
    )
    db.execute.assert_not_called()
    db.commit.assert_not_called()
