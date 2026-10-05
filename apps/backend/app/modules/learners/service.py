"""Learner authorization only. Consent evaluation and processing remain separate."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import SecurityError
from app.modules.auth.contracts import Principal
from app.modules.learners import repository as repo


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

# Future preference write endpoints MUST enforce this allowlist independently of role.
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
    """Accept ONLY a principal from auth resolution; callers cannot supply role claims.

    HTTP composition must use get_current_principal on the same request. Future
    writes must check again within their transaction and coordinate grant locks.
    Creator identity, consent evidence, and administrator role never grant access.
    """
    denied = SecurityError(404, "not_found", "Resource not found")
    if principal.status != "active" or not isinstance(action, LearnerAction):
        raise denied
    learner = repo.accessible_profile(db, learner_id)
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
        level = repo.guardian_level(db, principal.user_id, learner_id)
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
    return LearnerAuthorization(
        actor_id=principal.user_id,
        learner_id=learner_id,
        action=action,
        access_path=path,
        basic_profile_fields=profile_fields,
    )
