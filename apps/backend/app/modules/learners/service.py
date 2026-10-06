"""Learner authorization, public projections, and preference transactions."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.auth.service import assert_protected_session_live, protect_principal_for_write
from app.modules.learners import repository as repo
from app.modules.learners.models import LearnerPreferences, LearnerProfile
from app.modules.learners.schemas import (
    LearnerDetailEducator,
    LearnerDetailSelfGuardian,
    LearnerListItem,
    LearnerListResponse,
    LearnerPreferenceResponse,
    LearnerPreferenceUpdate,
)


class LearnerAction(StrEnum):
    READ_BASIC_PROFILE = "profile.read_basic"
    READ_GUARDIAN_SUMMARY = "summary.read_guardian"
    READ_EDUCATIONAL_SUMMARY = "summary.read_educational"
    READ_PREFERENCES = "preferences.read"
    UPDATE_PREFERENCES = "preferences.update"
    PERFORM_LEARNING_INTERACTION = "learning.interact"


_SELF = frozenset(
    {
        LearnerAction.READ_BASIC_PROFILE,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
        LearnerAction.READ_PREFERENCES,
        LearnerAction.UPDATE_PREFERENCES,
        LearnerAction.PERFORM_LEARNING_INTERACTION,
    }
)
_GUARDIAN_VIEWER = frozenset(
    {
        LearnerAction.READ_BASIC_PROFILE,
        LearnerAction.READ_GUARDIAN_SUMMARY,
        LearnerAction.READ_PREFERENCES,
    }
)
_EDUCATOR_VIEWER = frozenset(
    {
        LearnerAction.READ_BASIC_PROFILE,
        LearnerAction.READ_EDUCATIONAL_SUMMARY,
    }
)

# Preference writes enforce this allowlist independently of role.
ACCESSIBILITY_PREFERENCE_FIELDS = frozenset(
    {
        "preferred_language_tag",
        "text_scale",
        "line_spacing",
        "theme",
        "reduce_motion",
    }
)


@dataclass(frozen=True)
class LearnerAuthorization:
    """Action-scoped grant, not a learner DTO or permission to perform processing.

    No consent decision is represented. Future processing must evaluate consent
    separately even after this check succeeds. Do not cache across requests.
    """

    actor_id: UUID
    learner_id: UUID
    action: LearnerAction
    access_path: Literal["self", "guardian", "educator"]
    basic_profile_fields: frozenset[str]
    consent_evaluated: Literal[False] = False


def authorize_learner_action(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    action: LearnerAction,
) -> LearnerAuthorization:
    """Existing policy contract. Accept only a principal from current auth resolution."""
    return _authorized_profile(db, principal, learner_id, action)[1]


def _authorized_profile(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    action: LearnerAction,
    *,
    for_write: bool = False,
) -> tuple[LearnerProfile, LearnerAuthorization]:
    denied = SecurityError(404, "not_found", "Resource not found")
    if principal.status != "active" or not isinstance(action, LearnerAction):
        raise denied
    learner = repo.accessible_profile(db, learner_id, lock=for_write)
    if learner is None:
        raise denied
    path: Literal["self", "guardian", "educator"] | None = None
    if (
        "learner" in principal.roles
        and learner.learner_user_id == principal.user_id
        and action in _SELF
    ):
        path = "self"
    if path is None and "guardian" in principal.roles:
        level = repo.guardian_level(db, principal.user_id, learner_id, lock=for_write)
        if level in {"viewer", "manager"} and (
            action in _GUARDIAN_VIEWER
            or (level == "manager" and action == LearnerAction.UPDATE_PREFERENCES)
        ):
            path = "guardian"
    if path is None and "educator" in principal.roles:
        level = repo.educator_level(db, principal.user_id, learner_id, repo.current_time(db))
        if level in {"viewer", "instructor"} and (
            action in _EDUCATOR_VIEWER
            or (level == "instructor" and action == LearnerAction.PERFORM_LEARNING_INTERACTION)
        ):
            path = "educator"
    if path is None:
        raise denied
    profile_fields = frozenset({"id", "display_name"})
    if path != "educator":
        profile_fields |= {"age_band", "grade_level"}
    return learner, LearnerAuthorization(
        actor_id=principal.user_id,
        learner_id=learner_id,
        action=action,
        access_path=path,
        basic_profile_fields=profile_fields,
    )


def list_learners(
    db: Session,
    principal: Principal,
    cursor: UUID | None,
    limit: int,
) -> LearnerListResponse:
    if not principal.roles & {"learner", "guardian", "educator"}:
        raise SecurityError(403, "forbidden", "Access denied")
    rows = repo.accessible_page(db, principal.user_id, principal.roles, cursor, limit)
    return LearnerListResponse(
        items=[LearnerListItem(id=identity, display_name=name) for identity, name in rows[:limit]],
        next_cursor=rows[limit - 1][0] if len(rows) > limit else None,
    )


def read_profile(
    db: Session,
    principal: Principal,
    learner_id: UUID,
) -> LearnerDetailSelfGuardian | LearnerDetailEducator:
    learner, grant = _authorized_profile(
        db, principal, learner_id, LearnerAction.READ_BASIC_PROFILE
    )
    if grant.access_path == "educator":
        return LearnerDetailEducator(id=learner.id, display_name=learner.display_name)
    return LearnerDetailSelfGuardian(
        id=learner.id,
        display_name=learner.display_name,
        age_band=learner.age_band,
        grade_level=learner.grade_level,
    )


def _preference_response(
    learner_id: UUID, row: LearnerPreferences | None
) -> LearnerPreferenceResponse:
    if row is None:
        return LearnerPreferenceResponse(learner_id=learner_id, row_version=0)
    return LearnerPreferenceResponse(
        learner_id=learner_id,
        row_version=row.row_version,
        preferred_language_tag=row.preferred_language_tag,
        text_scale=row.text_scale,
        line_spacing=row.line_spacing,
        theme=row.theme,
        reduce_motion=row.reduce_motion,
    )


def read_preferences(
    db: Session, principal: Principal, learner_id: UUID
) -> LearnerPreferenceResponse:
    authorize_learner_action(db, principal, learner_id, LearnerAction.READ_PREFERENCES)
    return _preference_response(learner_id, repo.preferences(db, learner_id))


def _version_conflict() -> SecurityError:
    return SecurityError(409, "version_conflict", "Preferences changed. Reload and try again.")


def update_preferences(
    db: Session,
    principal: Principal,
    learner_id: UUID,
    payload: LearnerPreferenceUpdate,
) -> LearnerPreferenceResponse:
    """One transaction; auth -> learner -> grant -> preferences lock order.

    Version zero is API-only absent-row state. Authorization always precedes version
    disclosure. Ordinary ORM flushes maintain versions; no bulk writes or retries.
    """
    try:
        principal = protect_principal_for_write(db, principal)
        _authorized_profile(
            db, principal, learner_id, LearnerAction.UPDATE_PREFERENCES, for_write=True
        )
        row = repo.preferences(db, learner_id, lock=True)
        assert_protected_session_live(db, principal)
        if payload.row_version != (row.row_version if row is not None else 0):
            raise _version_conflict()
        values = payload.model_dump(
            exclude_unset=True, include=set(ACCESSIBILITY_PREFERENCE_FIELDS)
        )
        row = repo.save_preferences(
            db, row, learner_id, principal.user_id, values, repo.current_time(db)
        )
        response = _preference_response(learner_id, row)
        db.commit()
        return response
    except StaleDataError as exc:
        db.rollback()
        raise _version_conflict() from exc
    except IntegrityError as exc:
        db.rollback()
        # Defensive handling for an external creator that bypasses the parent lock.
        # Other integrity failures must retain the generic sanitized 503 behavior.
        diagnostic = getattr(exc.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) == "uq_learner_preferences_learner_id":
            raise _version_conflict() from exc
        raise
    except Exception:
        db.rollback()
        raise
