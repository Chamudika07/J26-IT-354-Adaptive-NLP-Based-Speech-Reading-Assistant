"""Service transactions and business rules for learner_modelling.

Enforces authentication verification, action-scoped learner authorization,
fail-closed consent gating, race-safe idempotency resolution, and deterministic
educational analytics calculation before session persistence.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError, authentication_required
from app.modules.auth.contracts import Principal
from app.modules.auth.service import assert_protected_session_live, protect_principal_for_write
from app.modules.learner_modelling import repository as repo
from app.modules.learner_modelling.analytics import (
    calculate_experimental_engagement,
    calculate_hesitation_frequency,
    calculate_reading_accuracy,
    calculate_words_per_minute,
)
from app.modules.learner_modelling.dashboard_projections import (
    EducatorAnalyticsProjection,
    GuardianSummaryProjection,
    LearnerProgressProjection,
    project_educator_analytics,
    project_guardian_summary,
    project_learner_progress,
)
from app.modules.learner_modelling.historical import (
    HistoricalSessionQuery,
    historical_records_to_observations,
)
from app.modules.learner_modelling.longitudinal import (
    LongitudinalProgressReport,
    LongitudinalWindow,
    calculate_longitudinal_progress,
)
from app.modules.learner_modelling.models import ReadingSession
from app.modules.learner_modelling.schemas import (
    ReadingSessionIngest,
    compute_canonical_session_digest,
)
from app.modules.learners.service import (
    LearnerAction,
    LearnerAuthorization,
    authorize_learner_action,
)

CONSENT_PURPOSE_LEARNING_SUPPORT: str = "learning_support"

# Type of a public consent checker function: (db, learner_id, purpose_code) -> None
ConsentChecker = Callable[[Session, UUID, str], None]

DashboardAccessPath = Literal["self", "guardian", "educator"]


@dataclass(frozen=True, slots=True)
class _DashboardPolicy[DashboardProjectionT]:
    """Fixed internal authorization and disclosure mapping; not product policy approval."""

    action: LearnerAction
    access_path: DashboardAccessPath
    projector: Callable[[LongitudinalProgressReport], DashboardProjectionT]


_LEARNER_DASHBOARD_POLICY = _DashboardPolicy(
    action=LearnerAction.READ_EDUCATIONAL_SUMMARY,
    access_path="self",
    projector=project_learner_progress,
)
_GUARDIAN_DASHBOARD_POLICY = _DashboardPolicy(
    action=LearnerAction.READ_GUARDIAN_SUMMARY,
    access_path="guardian",
    projector=project_guardian_summary,
)
_EDUCATOR_DASHBOARD_POLICY = _DashboardPolicy(
    action=LearnerAction.READ_EDUCATIONAL_SUMMARY,
    access_path="educator",
    projector=project_educator_analytics,
)


def _fail_closed_consent_checker(
    db: Session,
    learner_id: UUID,
    purpose_code: str,
) -> None:
    """Default fail-closed consent gate.

    The approved public consent verification interface from the learners module
    has not yet been integrated into the codebase. All ingestion attempts fail closed
    until an approved public consent verification interface is wired.
    """
    raise SecurityError(
        403,
        "consent_required",
        "Active consent verification interface is not yet available; session ingestion denied.",
    )


def read_learner_progress(
    db: Session,
    principal: Principal,
    query: HistoricalSessionQuery,
    *,
    consent_checker: ConsentChecker | None = None,
) -> LearnerProgressProjection:
    """Return the fixed learner projection after independent authorization and consent."""
    return _read_dashboard_projection(
        db,
        principal,
        query,
        policy=_LEARNER_DASHBOARD_POLICY,
        consent_checker=consent_checker,
    )


def read_guardian_summary(
    db: Session,
    principal: Principal,
    query: HistoricalSessionQuery,
    *,
    consent_checker: ConsentChecker | None = None,
) -> GuardianSummaryProjection:
    """Return the fixed guardian projection after independent authorization and consent."""
    return _read_dashboard_projection(
        db,
        principal,
        query,
        policy=_GUARDIAN_DASHBOARD_POLICY,
        consent_checker=consent_checker,
    )


def read_educator_analytics(
    db: Session,
    principal: Principal,
    query: HistoricalSessionQuery,
    *,
    consent_checker: ConsentChecker | None = None,
) -> EducatorAnalyticsProjection:
    """Return the fixed educator projection after independent authorization and consent."""
    return _read_dashboard_projection(
        db,
        principal,
        query,
        policy=_EDUCATOR_DASHBOARD_POLICY,
        consent_checker=consent_checker,
    )


def _read_dashboard_projection[DashboardProjectionT](
    db: Session,
    principal: Principal,
    query: HistoricalSessionQuery,
    *,
    policy: _DashboardPolicy[DashboardProjectionT],
    consent_checker: ConsentChecker | None,
) -> DashboardProjectionT:
    """Run one complete read-only dashboard pipeline without owning the transaction.

    The candidate access-path mappings and disclosure policies still require team
    approval. Consent withdrawal locking/version semantics are also unresolved, so
    these private entry points must remain unreachable from production routes.
    """
    if not isinstance(principal, Principal) or principal.status != "active":
        raise authentication_required()

    grant = authorize_learner_action(db, principal, query.learner_id, policy.action)
    _verify_dashboard_grant(grant, principal, query, policy)
    _evaluate_dashboard_consent(db, query.learner_id, consent_checker)

    records = repo.get_bounded_learner_session_history(db, query)
    observations = historical_records_to_observations(records)
    window = LongitudinalWindow(
        start_at_utc=query.start_at_utc,
        end_at_utc=query.end_at_utc,
    )
    report = calculate_longitudinal_progress(observations, window)
    return policy.projector(report)


def _verify_dashboard_grant[DashboardProjectionT](
    grant: LearnerAuthorization,
    principal: Principal,
    query: HistoricalSessionQuery,
    policy: _DashboardPolicy[DashboardProjectionT],
) -> None:
    """Reject mismatched or malformed grants without disclosing learner context."""
    if (
        not isinstance(grant, LearnerAuthorization)
        or grant.actor_id != principal.user_id
        or grant.learner_id != query.learner_id
        or grant.action != policy.action
        or grant.access_path != policy.access_path
        or grant.consent_evaluated is not False
    ):
        raise SecurityError(404, "not_found", "Resource not found")


def _evaluate_dashboard_consent(
    db: Session,
    learner_id: UUID,
    consent_checker: ConsentChecker | None,
) -> None:
    """Evaluate injected consent and sanitize unexpected callback failures."""
    checker = consent_checker if consent_checker is not None else _fail_closed_consent_checker
    try:
        checker(db, learner_id, CONSENT_PURPOSE_LEARNING_SUPPORT)
    except SecurityError:
        raise
    except Exception as exc:
        raise SecurityError(503, "service_unavailable", "Service unavailable") from exc


def ingest_reading_session(
    db: Session,
    principal: Principal,
    payload: ReadingSessionIngest,
    *,
    consent_checker: ConsentChecker | None = None,
) -> tuple[ReadingSession, bool]:
    """Ingest a reading session with authorization, consent verification, and idempotency.

    Returns:
        tuple[ReadingSession, bool]: (session_instance, is_newly_persisted)
        - If an identical session was already persisted: returns (existing_session, False)
        - If newly persisted: returns (new_session, True)

    Raises:
        SecurityError(401): if principal is inactive or session not live
        SecurityError(404 / 403): if principal lacks PERFORM_LEARNING_INTERACTION on learner
        SecurityError(403): if active consent for 'learning_support' is missing or unverified
        SecurityError(409): if client_session_id exists but request_digest conflicts
    """
    if principal.status != "active":
        raise SecurityError(401, "authentication_required", "Authentication required")

    # 1. Lock auth identity/session/roles according to established protected-write conventions
    principal = protect_principal_for_write(db, principal)

    # 2. Authorize learner interaction action
    authorize_learner_action(
        db,
        principal,
        payload.learner_id,
        LearnerAction.PERFORM_LEARNING_INTERACTION,
    )

    # 3. Verify consent before checking or returning existing session data or persisting new session
    checker = consent_checker if consent_checker is not None else _fail_closed_consent_checker
    checker(db, payload.learner_id, CONSENT_PURPOSE_LEARNING_SUPPORT)

    # 4. Compute backend-owned canonical request digest
    canonical_digest = compute_canonical_session_digest(payload)

    # 5. Confirm protected session remains live after domain authorization waits
    assert_protected_session_live(db, principal)

    # 6. Idempotency check: see if session already exists
    existing = repo.get_session_by_client_id(
        db, payload.learner_id, payload.client_session_id, lock=True
    )
    if existing is not None:
        if existing.request_digest == canonical_digest:
            return existing, False
        raise SecurityError(
            409,
            "digest_conflict",
            "Session payload does not match existing record for client_session_id.",
        )

    # 7. Calculate deterministic metrics for new session
    telemetry = payload.to_session_telemetry()
    acc = calculate_reading_accuracy(telemetry.words_attempted, telemetry.words_correct)
    wpm = calculate_words_per_minute(telemetry.words_attempted, telemetry.active_duration_ms)
    hes = calculate_hesitation_frequency(
        telemetry.hesitation_count,
        telemetry.words_attempted,
        telemetry.active_duration_ms,
    )
    eng = calculate_experimental_engagement(telemetry)

    accuracy_dec = Decimal(f"{acc:.4f}") if acc is not None else None
    wpm_dec = Decimal(f"{wpm:.2f}") if wpm is not None else None
    hesitation_dec = (
        Decimal(f"{hes.rate_per_word:.4f}")
        if hes is not None and hes.rate_per_word is not None
        else None
    )
    engagement_dec = Decimal(f"{eng.score:.4f}") if eng.score is not None else None
    formula_version = eng.formula_version

    orm_session = payload.to_orm_model(
        request_digest=canonical_digest,
        calculated_accuracy=accuracy_dec,
        calculated_wpm=wpm_dec,
        calculated_hesitation_rate=hesitation_dec,
        calculated_engagement_score=engagement_dec,
        engagement_formula_version=formula_version,
    )

    # 8. Persist atomically using nested savepoint to isolate concurrent insert races
    try:
        with db.begin_nested():
            repo.insert_reading_session(db, orm_session)
        return orm_session, True
    except IntegrityError as exc:
        diag = getattr(exc.orig, "diag", None)
        constraint = getattr(diag, "constraint_name", None)
        if constraint == "uq_reading_sessions_client_session" or (
            constraint is None and "uq_reading_sessions_client_session" in str(exc)
        ):
            # Concurrent race resolution: another request inserted this
            # (learner_id, client_session_id) row while we were processing.
            existing = repo.get_session_by_client_id(
                db, payload.learner_id, payload.client_session_id, lock=True
            )
            if existing is not None:
                if existing.request_digest == canonical_digest:
                    return existing, False
                raise SecurityError(
                    409,
                    "digest_conflict",
                    "Session payload does not match existing record for client_session_id.",
                ) from exc
        raise
