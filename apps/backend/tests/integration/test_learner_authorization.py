"""Database-backed policy matrix; no content endpoints or consent execution."""

import hashlib
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import SecurityError
from app.modules.auth import repository as auth_repo
from app.modules.auth import service as auth_service
from app.modules.auth.contracts import Principal
from app.modules.auth.models import Role, UserRole
from app.modules.learners import repository as repo
from app.modules.learners.models import (
    ConsentNoticeVersion,
    ConsentRecord,
    EducatorLearnerRelationship,
    GuardianLearnerRelationship,
    LearnerProfile,
)
from app.modules.learners.service import LearnerAction as Action
from app.modules.learners.service import authorize_learner_action

pytestmark = pytest.mark.integration


@pytest.fixture
def learner(db_session, active_user):
    row = LearnerProfile(display_name="Synthetic learner", created_by_user_id=active_user.id)
    db_session.add(row)
    db_session.flush()
    return row


def principal(db, user, roles):
    now = auth_repo.now(db)
    return Principal(
        user.id,
        user.login_handle,
        frozenset(roles),
        uuid4(),
        now,
        uuid4(),
        now,
        now + timedelta(minutes=5),
    )


def guardian(db, user, learner, level="viewer"):
    row = GuardianLearnerRelationship(
        guardian_user_id=user.id,
        learner_id=learner.id,
        access_level=level,
        granted_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


def educator(db, user, learner, level="viewer"):
    row = EducatorLearnerRelationship(
        educator_user_id=user.id,
        learner_id=learner.id,
        access_level=level,
        granted_by_user_id=user.id,
        expires_at=auth_repo.now(db) + timedelta(days=1),
    )
    db.add(row)
    db.flush()
    return row


PERMISSIONS = {
    "self": {
        Action.READ_BASIC_PROFILE,
        Action.READ_EDUCATIONAL_SUMMARY,
        Action.READ_PREFERENCES,
        Action.UPDATE_PREFERENCES,
        Action.PERFORM_LEARNING_INTERACTION,
    },
    "guardian_viewer": {
        Action.READ_BASIC_PROFILE,
        Action.READ_GUARDIAN_SUMMARY,
        Action.READ_PREFERENCES,
    },
    "guardian_manager": {
        Action.READ_BASIC_PROFILE,
        Action.READ_GUARDIAN_SUMMARY,
        Action.READ_PREFERENCES,
        Action.UPDATE_PREFERENCES,
    },
    "educator_viewer": {Action.READ_BASIC_PROFILE, Action.READ_EDUCATIONAL_SUMMARY},
    "educator_instructor": {
        Action.READ_BASIC_PROFILE,
        Action.READ_EDUCATIONAL_SUMMARY,
        Action.PERFORM_LEARNING_INTERACTION,
    },
    "administrator": set(),
}


@pytest.mark.parametrize("kind", PERMISSIONS)
@pytest.mark.parametrize("action", list(Action))
def test_complete_policy_matrix(db_session, active_user, learner, kind, action):
    role = kind.split("_")[0]
    if kind == "self":
        learner.learner_user_id = active_user.id
        db_session.flush()
        role = "learner"
    elif kind.startswith("guardian"):
        guardian(db_session, active_user, learner, kind.split("_")[1])
    elif kind.startswith("educator"):
        educator(db_session, active_user, learner, kind.split("_")[1])
    actor = principal(db_session, active_user, {role})
    if action in PERMISSIONS[kind]:
        grant = authorize_learner_action(db_session, actor, learner.id, action)
        assert grant.learner_id == learner.id and grant.action == action
        assert grant.consent_evaluated is False
        if role == "educator":
            assert grant.basic_profile_fields == frozenset({"id", "display_name"})
    else:
        with pytest.raises(SecurityError) as error:
            authorize_learner_action(db_session, actor, learner.id, action)
        assert (error.value.status, error.value.code, error.value.message) == (
            404,
            "not_found",
            "Resource not found",
        )


@pytest.mark.parametrize("role", ["learner", "guardian", "educator", "administrator"])
def test_unrelated_creator_and_cross_learner_denied(db_session, active_user, learner, role):
    # Being the creator does not confer access. Grants to a different learner don't either.
    other = LearnerProfile(
        display_name="Other synthetic",
        created_by_user_id=active_user.id,
        learner_user_id=active_user.id,
    )
    db_session.add(other)
    db_session.flush()
    guardian(db_session, active_user, other, "manager")
    educator(db_session, active_user, other, "instructor")
    actor = principal(db_session, active_user, {role})
    for target in (learner.id, uuid4()):
        with pytest.raises(SecurityError) as error:
            authorize_learner_action(db_session, actor, target, Action.READ_BASIC_PROFILE)
        assert error.value.code == "not_found"


@pytest.mark.parametrize(
    "role,relationship",
    [("guardian", educator), ("educator", guardian), ("administrator", guardian)],
)
def test_mixed_role_relationship_attack(db_session, active_user, learner, role, relationship):
    relationship(db_session, active_user, learner)
    with pytest.raises(SecurityError):
        authorize_learner_action(
            db_session,
            principal(db_session, active_user, {role}),
            learner.id,
            Action.READ_BASIC_PROFILE,
        )


@pytest.mark.parametrize("kind", ["guardian", "educator"])
def test_revoked_relationship(db_session, active_user, learner, kind):
    relation = (guardian if kind == "guardian" else educator)(db_session, active_user, learner)
    relation.revoked_at = auth_repo.now(db_session)
    relation.revoked_by_user_id = active_user.id
    db_session.flush()
    with pytest.raises(SecurityError):
        authorize_learner_action(
            db_session,
            principal(db_session, active_user, {kind}),
            learner.id,
            Action.READ_BASIC_PROFILE,
        )


@pytest.mark.parametrize("delta", [0, 1])
def test_educator_expiry_boundary(db_session, active_user, learner, monkeypatch, delta):
    relation = educator(db_session, active_user, learner)
    monkeypatch.setattr(
        repo, "current_time", lambda db: relation.expires_at + timedelta(seconds=delta)
    )
    with pytest.raises(SecurityError):
        authorize_learner_action(
            db_session,
            principal(db_session, active_user, {"educator"}),
            learner.id,
            Action.READ_BASIC_PROFILE,
        )


@pytest.mark.parametrize("role", ["guardian", "educator", "learner"])
def test_archived_profile_denies_every_path(db_session, active_user, learner, role):
    guardian(db_session, active_user, learner, "manager")
    educator(db_session, active_user, learner, "instructor")
    learner.learner_user_id = active_user.id
    learner.archived_at = auth_repo.now(db_session)
    db_session.flush()
    with pytest.raises(SecurityError):
        authorize_learner_action(
            db_session,
            principal(db_session, active_user, {role}),
            learner.id,
            Action.READ_BASIC_PROFILE,
        )


def test_no_implicit_unknown_action_or_inactive_actor(db_session, active_user, learner):
    guardian(db_session, active_user, learner, "manager")
    actor = principal(db_session, active_user, {"guardian", "administrator"})
    for action in (
        "documents.read",
        "consent.grant",
        "recordings.read",
        "research.read",
        "profile.read_basic",
    ):
        with pytest.raises(SecurityError):
            authorize_learner_action(db_session, actor, learner.id, action)
    with pytest.raises(SecurityError):
        authorize_learner_action(
            db_session, replace(actor, status="disabled"), learner.id, Action.READ_BASIC_PROFILE
        )


def test_role_revocation_removes_learner_access(db_session, active_user, learner, settings):
    guardian(db_session, active_user, learner)
    role = db_session.scalar(select(Role).where(Role.code == "guardian"))
    assignment = UserRole(
        user_id=active_user.id, role_id=role.id, granted_by_user_id=active_user.id
    )
    db_session.add(assignment)
    db_session.flush()
    pair = auth_service.login(
        db_session, settings, active_user.login_handle, "Synthetic accessible passphrase 42"
    )
    actor = auth_service.resolve_principal(db_session, settings, pair.access_token)
    authorize_learner_action(db_session, actor, learner.id, Action.READ_BASIC_PROFILE)
    assignment.revoked_at = auth_repo.now(db_session)
    assignment.revoked_by_user_id = active_user.id
    db_session.commit()
    actor = auth_service.resolve_principal(db_session, settings, pair.access_token)
    with pytest.raises(SecurityError):
        authorize_learner_action(db_session, actor, learner.id, Action.READ_BASIC_PROFILE)


def test_consent_evidence_does_not_authorize(db_session, active_user, learner):
    text = "Synthetic assent evidence, not approved wording"
    now = auth_repo.now(db_session)
    notice = ConsentNoticeVersion(
        purpose_code="learning_support",
        record_kind="learner_assent",
        version_label="synthetic",
        language_tag="en-x-test",
        notice_text=text,
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        published_at=now,
        published_by_user_id=active_user.id,
    )
    db_session.add(notice)
    db_session.flush()
    db_session.add(
        ConsentRecord(
            learner_id=learner.id,
            notice_version_id=notice.id,
            purpose_code="learning_support",
            record_kind="learner_assent",
            decision="granted",
            sequence_no=1,
            occurred_at=now,
            recorded_by_user_id=active_user.id,
            capture_method="assisted_in_person",
        )
    )
    db_session.flush()
    with pytest.raises(SecurityError):
        authorize_learner_action(
            db_session,
            principal(db_session, active_user, {"guardian"}),
            learner.id,
            Action.READ_BASIC_PROFILE,
        )
