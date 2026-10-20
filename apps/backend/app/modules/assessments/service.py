"""Short atomic lifecycle transactions with explicit public authorization contracts."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import SecurityError
from app.modules.assessments import repository as repo
from app.modules.assessments.models import (
    ReadingAssessmentMaterial as Material,
)
from app.modules.assessments.models import (
    ReadingAssessmentResult as Result,
)
from app.modules.assessments.models import (
    ReadingAssessmentSession as Assessment,
)
from app.modules.assessments.schemas import (
    AssessmentAbandonRequest,
    AssessmentCompletionRequest,
    AssessmentHistoryItem,
    AssessmentHistoryPage,
    AssessmentMaterialDetail,
    AssessmentMaterialPage,
    AssessmentMaterialSummary,
    AssessmentResultSummary,
    AssessmentSessionResponse,
    AssessmentStartRequest,
    AssessmentStartResponse,
    Observations,
)
from app.modules.assessments.scoring import PROTOCOL_VERSION, SCORING_VERSION, calculate_metrics
from app.modules.auth.contracts import Principal
from app.modules.auth.service import assert_protected_session_live, protect_principal_for_write
from app.modules.learners.service import (
    LearnerAction as Action,
)
from app.modules.learners.service import (
    assert_protected_learner_action_live,
    authorize_learner_action,
    authorize_learner_action_for_write,
    authorize_reading_material_catalog,
)


def not_found() -> SecurityError:
    return SecurityError(404, "not_found", "Resource not found")


def conflict(code: str) -> SecurityError:
    return SecurityError(409, code, "Assessment changed. Reload and try again.")


def invalid() -> SecurityError:
    return SecurityError(422, "validation_error", "Invalid request")


def material_summary(row: Material) -> AssessmentMaterialSummary:
    return AssessmentMaterialSummary(
        **{name: getattr(row, name) for name in AssessmentMaterialSummary.model_fields}
    )


def material_detail(row: Material) -> AssessmentMaterialDetail:
    return AssessmentMaterialDetail(
        **{name: getattr(row, name) for name in AssessmentMaterialDetail.model_fields}
    )


def result_summary(row: Result | None) -> AssessmentResultSummary | None:
    if row is None:
        return None
    try:
        metrics = calculate_metrics(
            reading_duration_ms=row.reading_duration_ms,
            attempted_word_count=row.attempted_word_count,
            correct_word_count=row.correct_word_count,
            comprehension_correct=row.comprehension_correct,
            comprehension_total=row.comprehension_total,
            scoring_version=row.scoring_version,
        )
    except ValueError as exc:
        # Unknown historical versions must never silently use the newest calculator.
        raise SecurityError(503, "service_unavailable", "Service unavailable") from exc
    return AssessmentResultSummary(
        **{name: getattr(row, name) for name in Observations.model_fields},
        scoring_version=row.scoring_version,
        **asdict(metrics),
    )


def response(
    row: Assessment, material: Material, result: Result | None, *, administration: bool = False
) -> AssessmentSessionResponse:
    model = AssessmentStartResponse if administration else AssessmentSessionResponse
    return model(
        id=row.id,
        material=material_detail(material) if administration else material_summary(material),
        collection_mode="instructor_observed",
        protocol_version=row.protocol_version,
        status=cast(Literal["started", "completed", "abandoned"], row.status),
        started_at=row.started_at,
        completed_at=row.completed_at,
        abandoned_at=row.abandoned_at,
        row_version=row.row_version,
        result=result_summary(result),
    )


def list_materials(
    db: Session, principal: Principal, cursor: UUID | None, limit: int
) -> AssessmentMaterialPage:
    authorize_reading_material_catalog(db, principal)
    rows = repo.materials(db, cursor, limit)
    return AssessmentMaterialPage(
        items=[material_summary(row) for row in rows[:limit]],
        next_cursor=rows[limit - 1].id if len(rows) > limit else None,
    )


def decode_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if value is None:
        return None
    try:
        timestamp, identity = value.split("|")
        instant = datetime.fromisoformat(timestamp)
        if instant.tzinfo is None:
            raise ValueError("Timezone required")
        return instant.astimezone(UTC), UUID(identity)
    except (ValueError, OverflowError) as exc:
        raise invalid() from exc


def list_history(
    db: Session, principal: Principal, learner_id: UUID, cursor: str | None, limit: int
) -> AssessmentHistoryPage:
    authorize_learner_action(db, principal, learner_id, Action.READ_READING_ASSESSMENT)
    rows = repo.history(db, learner_id, decode_cursor(cursor), limit)
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1][0]
        next_cursor = f"{last.started_at.astimezone(UTC).isoformat()}|{last.id}"
    return AssessmentHistoryPage(
        items=[AssessmentHistoryItem(**response(s, m, r).model_dump()) for s, m, r in rows[:limit]],
        next_cursor=next_cursor,
    )


def read_assessment(
    db: Session, principal: Principal, learner_id: UUID, assessment_id: UUID
) -> AssessmentSessionResponse:
    authorize_learner_action(db, principal, learner_id, Action.READ_READING_ASSESSMENT)
    row = repo.assessment(db, learner_id, assessment_id)
    if row is None:
        raise not_found()
    material = repo.material(db, row.material_id)
    if material is None:
        raise not_found()
    administration = False
    if row.administered_by_user_id == principal.user_id:
        try:
            authorize_learner_action(db, principal, learner_id, Action.SUBMIT_READING_ASSESSMENT)
            administration = True
        except SecurityError as exc:
            if exc.status != 404:
                raise
    return response(row, material, repo.result(db, row.id), administration=administration)


def protect(db: Session, principal: Principal, learner_id: UUID, action: Action) -> Principal:
    principal = protect_principal_for_write(db, principal)
    authorize_learner_action_for_write(db, principal, learner_id, action)
    return principal


def recheck(db: Session, principal: Principal, learner_id: UUID, action: Action) -> None:
    assert_protected_session_live(db, principal)
    assert_protected_learner_action_live(db, principal, learner_id, action)


def start(
    db: Session, principal: Principal, learner_id: UUID, payload: AssessmentStartRequest
) -> AssessmentStartResponse:
    try:
        principal = protect(db, principal, learner_id, Action.START_READING_ASSESSMENT)
        material = repo.material(db, payload.material_id, lock=True)
        recheck(db, principal, learner_id, Action.START_READING_ASSESSMENT)
        if material is None or not material.is_active:
            raise not_found()
        if repo.active_session(db, learner_id, principal.user_id):
            raise conflict("assessment_start_conflict")
        now = repo.now(db)
        row = Assessment(
            learner_id=learner_id,
            material_id=material.id,
            administered_by_user_id=principal.user_id,
            collection_mode="instructor_observed",
            protocol_version=PROTOCOL_VERSION,
            status="started",
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        repo.insert_session(db, row)
        result = cast(AssessmentStartResponse, response(row, material, None, administration=True))
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        if (
            getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == "uq_reading_session_started"
        ):
            raise conflict("assessment_start_conflict") from exc
        raise
    except Exception:
        db.rollback()
        raise


def validate_material(payload: AssessmentCompletionRequest, material: Material) -> None:
    if payload.attempted_word_count + payload.omission_count > material.word_count:
        raise invalid()
    count = material.comprehension_question_count
    if count == 0:
        if payload.comprehension_correct is not None or payload.comprehension_total is not None:
            raise invalid()
    elif payload.comprehension_correct is None or payload.comprehension_total != count:
        raise invalid()


def finish(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    assessment_id: UUID,
    payload: AssessmentCompletionRequest | AssessmentAbandonRequest,
) -> AssessmentSessionResponse:
    complete = isinstance(payload, AssessmentCompletionRequest)
    action = Action.SUBMIT_READING_ASSESSMENT if complete else Action.ABANDON_READING_ASSESSMENT
    try:
        principal = protect(db, principal, learner_id, action)
        row = repo.assessment(db, learner_id, assessment_id, lock=True)
        recheck(db, principal, learner_id, action)
        if row is None or row.administered_by_user_id != principal.user_id:
            raise not_found()
        if row.status != "started":
            raise conflict("assessment_state_conflict")
        if row.row_version != payload.row_version:
            raise conflict("version_conflict")
        material = repo.material(db, row.material_id)
        if material is None:
            raise not_found()
        result = None
        now = repo.now(db)
        if isinstance(payload, AssessmentCompletionRequest):
            validate_material(payload, material)
            result = Result(
                session_id=row.id,
                submitted_by_user_id=principal.user_id,
                submitted_at=now,
                scoring_version=SCORING_VERSION,
                **payload.model_dump(exclude={"row_version"}),
            )
            repo.insert_result(db, result)
            row.status, row.completed_at = "completed", now
        else:
            row.status, row.abandoned_at = "abandoned", now
        row.updated_at = now
        db.flush()
        public = response(row, material, result)
        db.commit()
        return public
    except StaleDataError as exc:
        db.rollback()
        raise conflict("version_conflict") from exc
    except Exception:
        db.rollback()
        raise
