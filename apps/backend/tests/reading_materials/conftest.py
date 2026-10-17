"""Synthetic English fixtures, isolated by the existing disposable database fixture."""

import hashlib
from dataclasses import asdict
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.modules.auth import repository as auth_repo
from app.modules.auth.models import Role, UserRole
from app.modules.learners.models import (
    EducatorLearnerRelationship,
    GuardianLearnerRelationship,
    LearnerProfile,
)
from app.modules.reading_materials import pipeline
from app.modules.reading_materials.models import (
    ReadingMaterial as Material,
)
from app.modules.reading_materials.models import (
    ReadingMaterialProcessingRun as Run,
)
from app.modules.reading_materials.models import (
    ReadingMaterialRevision as Revision,
)
from app.modules.reading_materials.models import (
    ReadingMaterialSentenceFeature as Sentence,
)

TEXT = "A cat rests. A dog runs!"


@pytest.fixture
def setup_material(db_session, active_user, auth_client):
    def make(kind="educator_instructor", source=TEXT, expired=False):
        now = auth_repo.now(db_session)
        learner = LearnerProfile(
            display_name="Synthetic reader",
            created_by_user_id=active_user.id,
            learner_user_id=active_user.id if kind == "self" else None,
        )
        db_session.add(learner)
        db_session.flush()
        code = "learner" if kind == "self" else kind.split("_")[0]
        role = db_session.scalar(select(Role).where(Role.code == code))
        db_session.add(
            UserRole(user_id=active_user.id, role_id=role.id, granted_by_user_id=active_user.id)
        )
        relation = None
        if code == "educator":
            relation = EducatorLearnerRelationship(
                educator_user_id=active_user.id,
                learner_id=learner.id,
                access_level=kind.split("_")[1],
                granted_by_user_id=active_user.id,
                created_at=now - timedelta(days=2),
                expires_at=now + timedelta(days=-1 if expired else 1),
            )
        elif code == "guardian":
            relation = GuardianLearnerRelationship(
                guardian_user_id=active_user.id,
                learner_id=learner.id,
                access_level=kind.split("_")[1],
                granted_by_user_id=active_user.id,
            )
        if relation:
            db_session.add(relation)
        material = Material(
            learner_id=learner.id, created_by_user_id=active_user.id, created_at=now, updated_at=now
        )
        db_session.add(material)
        db_session.flush()
        revision = Revision(
            material_id=material.id,
            revision_number=1,
            title="Synthetic passage",
            language_tag="en",
            source_kind="plain_text",
            original_text=source,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            created_by_user_id=active_user.id,
            created_at=now,
        )
        db_session.add(revision)
        db_session.commit()
        login = auth_client.post(
            "/api/v1/auth/login",
            json={
                "login_handle": active_user.login_handle,
                "password": "Synthetic accessible passphrase 42",
            },
        )
        assert login.status_code == 200
        base = f"/api/v1/learners/{learner.id}/reading-materials"
        return dict(
            learner=learner,
            material=material,
            revision=revision,
            relation=relation,
            headers={"Authorization": "Bearer " + login.json()["access_token"]},
            base=base,
            detail=f"{base}/{material.id}",
            revisions=f"{base}/{material.id}/revisions",
            runs=f"{base}/{material.id}/revisions/{revision.id}/processing-runs",
        )

    return make


@pytest.fixture
def stored_run(db_session, active_user):
    def make(context, status="succeeded", attempt=1, expired=False, fingerprint=None):
        now = auth_repo.now(db_session)
        provenance = pipeline.provenance()
        if fingerprint:
            provenance["pipeline_fingerprint"] = fingerprint
        row = Run(
            revision_id=context["revision"].id,
            attempt_number=attempt,
            requested_by_user_id=active_user.id,
            status="running",
            started_at=now - timedelta(minutes=2),
            lease_expires_at=now + timedelta(seconds=-1 if expired else 60),
            **provenance,
        )
        db_session.add(row)
        db_session.flush()
        if status == "succeeded":
            output = pipeline.process(context["revision"].original_text)
            db_session.add_all([Sentence(run_id=row.id, **asdict(s)) for s in output.sentences])
            db_session.flush()
            for name, value in asdict(output.document).items():
                setattr(row, name, value)
            row.normalized_text, row.normalized_sha256 = (
                output.normalized_text,
                output.normalized_sha256,
            )
        if status != "running":
            row.status, row.finished_at = status, now
            if status == "failed":
                row.failure_code = "pipeline_failed"
        db_session.commit()
        return row

    return make
