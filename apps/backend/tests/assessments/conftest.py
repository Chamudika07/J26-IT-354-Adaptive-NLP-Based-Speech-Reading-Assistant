"""Synthetic original passages and actors; never load real learner content."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.assessments.models import (
    ReadingAssessmentMaterial as Material,
)
from app.modules.assessments.models import (
    ReadingAssessmentSession as Assessment,
)
from app.modules.assessments.scoring import PROTOCOL_VERSION
from app.modules.auth import repository as auth_repo
from app.modules.auth.models import Role, UserRole
from app.modules.learners.models import (
    EducatorLearnerRelationship,
    GuardianLearnerRelationship,
    LearnerProfile,
)


@pytest.fixture
def observations():
    return dict(
        row_version=1,
        reading_duration_ms=30000,
        attempted_word_count=8,
        correct_word_count=6,
        omission_count=1,
        substitution_count=3,
        insertion_count=2,
        repetition_count=4,
        self_correction_count=1,
        unfamiliar_word_count=None,
        comprehension_correct=None,
        comprehension_total=None,
    )


@pytest.fixture
def material_factory(db_session):
    def make(**overrides):
        values = dict(
            code="synthetic_" + uuid4().hex,
            version=1,
            title="Synthetic original passage",
            language_tag="en",
            passage_text="A small bird rests beside a bright blue garden gate.",
            word_count=11,
            tokenization_version="synthetic-whitespace-v1",
            administration_instructions="Read the passage once. Time only the reading.",
            comprehension_question_count=0,
        )
        values.update(overrides)
        row = Material(**values)
        db_session.add(row)
        db_session.flush()
        return row

    return make


@pytest.fixture
def assessment_setup(db_session, auth_client, active_user, material_factory):
    def make(kind="educator_instructor", **material_values):
        learner = LearnerProfile(
            created_by_user_id=active_user.id,
            display_name="Synthetic reading learner",
            learner_user_id=active_user.id if kind == "self" else None,
        )
        db_session.add(learner)
        db_session.flush()
        role_code = "learner" if kind == "self" else kind.split("_")[0]
        role = db_session.scalar(select(Role).where(Role.code == role_code))
        db_session.add(
            UserRole(user_id=active_user.id, role_id=role.id, granted_by_user_id=active_user.id)
        )
        relation = None
        if kind.startswith("guardian"):
            relation = GuardianLearnerRelationship(
                guardian_user_id=active_user.id,
                learner_id=learner.id,
                access_level=kind.split("_")[1],
                granted_by_user_id=active_user.id,
            )
        elif kind.startswith("educator"):
            relation = EducatorLearnerRelationship(
                educator_user_id=active_user.id,
                learner_id=learner.id,
                access_level=kind.split("_")[1],
                granted_by_user_id=active_user.id,
                created_at=auth_repo.now(db_session) - timedelta(days=2),
                expires_at=auth_repo.now(db_session) + timedelta(days=1),
            )
        if relation:
            db_session.add(relation)
        db_session.flush()
        token = auth_client.post(
            "/api/v1/auth/login",
            json={
                "login_handle": active_user.login_handle,
                "password": "Synthetic accessible passphrase 42",
            },
        )
        assert token.status_code == 200
        headers = {"Authorization": "Bearer " + token.json()["access_token"]}
        return {
            "learner": learner,
            "relation": relation,
            "headers": headers,
            "material": material_factory(**material_values),
            "base": f"/api/v1/learners/{learner.id}/reading-assessments",
        }

    return make


@pytest.fixture
def stored_session(db_session, active_user):
    def make(context, **overrides):
        now = auth_repo.now(db_session)
        values = dict(
            learner_id=context["learner"].id,
            material_id=context["material"].id,
            administered_by_user_id=active_user.id,
            status="started",
            collection_mode="instructor_observed",
            protocol_version=PROTOCOL_VERSION,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        values.update(overrides)
        row = Assessment(**values)
        db_session.add(row)
        db_session.flush()
        return row

    return make
