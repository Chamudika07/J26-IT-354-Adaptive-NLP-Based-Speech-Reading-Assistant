"""Service transactions and business rules for learner_modelling.

Enforces authentication verification, action-scoped learner authorization,
fail-closed consent gating, race-safe idempotency resolution, and deterministic
educational analytics calculation before session persistence.
"""

from collections.abc import Callable
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.auth.service import assert_protected_session_live, protect_principal_for_write
from app.modules.learner_modelling import repository as repo
from app.modules.learner_modelling.analytics import (
    calculate_experimental_engagement,
    calculate_hesitation_frequency,
    calculate_reading_accuracy,
    calculate_words_per_minute,
)
from app.modules.learner_modelling.models import ReadingSession
from app.modules.learner_modelling.schemas import (
    ReadingSessionIngest,
    compute_canonical_session_digest,
)
from app.modules.learners.service import LearnerAction, authorize_learner_action

CONSENT_PURPOSE_LEARNING_SUPPORT: str = "learning_support"

# Type of a public consent checker function: (db, learner_id, purpose_code) -> None
ConsentChecker = Callable[[Session, UUID, str], None]


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
