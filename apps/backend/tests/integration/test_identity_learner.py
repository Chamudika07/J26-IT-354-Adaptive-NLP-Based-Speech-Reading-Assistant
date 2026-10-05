"""PostgreSQL behavioral tests. All rows are synthetic and rolled back per test."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.modules.auth.models import Role, User, UserRole
from app.modules.learners.models import (
    ConsentNoticeVersion,
    ConsentRecord,
    EducatorLearnerRelationship,
    GuardianLearnerRelationship,
    LearnerPreferences,
    LearnerProfile,
)

pytestmark = pytest.mark.integration


def add(session, model, **values):
    row = model(**values)
    session.add(row)
    session.flush()
    return row


def actor(session):
    return add(session, User, login_handle="synthetic_" + uuid4().hex[:16])


def payload(session, model, *, owner=None, learner=None):
    owner = owner or actor(session)
    if model is User:
        return {"login_handle": "synthetic_" + uuid4().hex[:16]}
    if model is LearnerProfile:
        return {"created_by_user_id": owner.id, "display_name": "Synthetic learner"}
    if model is UserRole:
        role = session.scalar(select(Role).where(Role.code == "guardian"))
        return {"user_id": owner.id, "role_id": role.id, "granted_by_user_id": owner.id}
    if model is ConsentNoticeVersion:
        wording = "Synthetic test notice; not approved consent wording."
        return {
            "purpose_code": "learning_support",
            "record_kind": "learner_assent",
            "version_label": "test-v1",
            "language_tag": "en-x-" + uuid4().hex[:8],
            "notice_text": wording,
            "content_sha256": hashlib.sha256(wording.encode()).hexdigest(),
            "published_at": datetime.now(UTC) - timedelta(seconds=1),
            "published_by_user_id": owner.id,
        }
    learner = learner or add(
        session, LearnerProfile, **payload(session, LearnerProfile, owner=owner)
    )
    if model is GuardianLearnerRelationship:
        return {
            "guardian_user_id": owner.id,
            "learner_id": learner.id,
            "access_level": "viewer",
            "granted_by_user_id": owner.id,
        }
    if model is EducatorLearnerRelationship:
        return {
            "educator_user_id": owner.id,
            "learner_id": learner.id,
            "access_level": "viewer",
            "granted_by_user_id": owner.id,
            "expires_at": datetime.now(UTC) + timedelta(days=30),
        }
    if model is LearnerPreferences:
        return {"learner_id": learner.id, "updated_by_user_id": owner.id}
    if model is ConsentRecord:
        notice = add(
            session, ConsentNoticeVersion, **payload(session, ConsentNoticeVersion, owner=owner)
        )
        return {
            "learner_id": learner.id,
            "notice_version_id": notice.id,
            "purpose_code": notice.purpose_code,
            "record_kind": notice.record_kind,
            "decision": "granted",
            "sequence_no": 1,
            # Capture the event on the same clock as recorded_at. Host/container clocks
            # can differ by milliseconds even when both report UTC.
            "occurred_at": session.scalar(select(func.clock_timestamp())),
            "recorded_by_user_id": owner.id,
            "capture_method": "assisted_in_person",
        }
    raise AssertionError(model)


def rejects(session, operation, state="23514"):
    with pytest.raises(IntegrityError) as error, session.begin_nested():
        operation()
        session.flush()
    assert error.value.orig.sqlstate == state
    return error.value.orig


MODELS = [
    User,
    UserRole,
    LearnerProfile,
    GuardianLearnerRelationship,
    EducatorLearnerRelationship,
    LearnerPreferences,
    ConsentNoticeVersion,
    ConsentRecord,
]


@pytest.mark.parametrize("model", MODELS)
def test_uuid_keys_and_utc_timestamps(db_session, model):
    row = add(db_session, model, **payload(db_session, model))
    assert isinstance(row.id, UUID) and row.id.version == 4
    stamp = row.recorded_at if model is ConsentRecord else row.created_at
    assert stamp.utcoffset() == timedelta(0)
    if model is not ConsentRecord:
        assert row.row_version == 1


def test_roles_seeded_only(db_session):
    roles = db_session.scalars(select(Role)).all()
    assert {role.code for role in roles} == {"guardian", "educator", "learner", "administrator"}
    assert all(role.id.version == 4 and role.is_active for role in roles)


def test_role_integrity_and_immutable_code(db_session):
    rejects(db_session, lambda: add(db_session, Role, code="unknown", description="Synthetic"))
    rejects(db_session, lambda: add(db_session, Role, code="guardian", description=" "))
    rejects(
        db_session, lambda: add(db_session, Role, code="guardian", description="Synthetic"), "23505"
    )
    role = db_session.scalar(select(Role).where(Role.code == "guardian"))
    rejects(
        db_session,
        lambda: db_session.execute(update(Role).where(Role.id == role.id).values(code="educator")),
    )


@pytest.mark.parametrize(
    "values",
    [
        {"login_handle": "UPPER"},
        {"login_handle": None},
        {"login_handle": "a"},
        {"email": " Mixed@Example.test "},
        {"email": "   "},
        {"email_verified_at": datetime.now(UTC)},
        {"status": "unknown"},
        {"status": "active"},
        {"password_hash": " "},
        {"status": "anonymized"},
        {"row_version": 0},
    ],
)
def test_user_checks(db_session, values):
    data = payload(db_session, User) | values
    # Core insert deliberately checks server constraints, not ORM version initialization.
    rejects(
        db_session, lambda: db_session.execute(User.__table__.insert().values(id=uuid4(), **data))
    )


@pytest.mark.parametrize("field", ["login_handle", "email"])
def test_unique_account_identifiers(db_session, field):
    first = add(
        db_session, User, **(payload(db_session, User) | {"email": "synthetic@example.test"})
    )
    data = payload(db_session, User) | {field: getattr(first, field)}
    rejects(db_session, lambda: add(db_session, User, **data), "23505")


def test_multiple_accounts_without_email_and_anonymization(db_session):
    first, second = actor(db_session), actor(db_session)
    assert first.email is None and second.email is None
    first.status = "anonymized"
    first.login_handle = None
    first.deleted_at = datetime.now(UTC)
    db_session.flush()
    assert first.row_version == 2


@pytest.mark.parametrize("age,grade", [(None, None), (9, 3), (12, 8), (10, None), (None, 5)])
def test_optional_login_age_and_grade(db_session, age, grade):
    for _ in range(2):
        learner = add(
            db_session,
            LearnerProfile,
            **(payload(db_session, LearnerProfile) | {"age_band": age, "grade_level": grade}),
        )
        assert learner.learner_user_id is None
        assert (learner.age_band, learner.grade_level) == (age, grade)


@pytest.mark.parametrize(
    "field,value",
    [
        ("age_band", 8),
        ("age_band", 13),
        ("grade_level", 2),
        ("grade_level", 9),
        ("display_name", " "),
    ],
)
def test_profile_constraints(db_session, field, value):
    data = payload(db_session, LearnerProfile) | {field: value}
    rejects(db_session, lambda: add(db_session, LearnerProfile, **data))


def test_personal_login_is_unique_and_delete_sets_null(db_session):
    login = actor(db_session)
    profile = add(
        db_session,
        LearnerProfile,
        **(payload(db_session, LearnerProfile) | {"learner_user_id": login.id}),
    )
    data = payload(db_session, LearnerProfile) | {"learner_user_id": login.id}
    rejects(db_session, lambda: add(db_session, LearnerProfile, **data), "23505")
    db_session.execute(delete(User).where(User.id == login.id))
    db_session.expire(profile)
    assert profile.learner_user_id is None


GRANTS = [UserRole, GuardianLearnerRelationship, EducatorLearnerRelationship]


@pytest.mark.parametrize("model", GRANTS)
def test_grant_history_and_duplicate_open_prevention(db_session, model):
    data = payload(db_session, model)
    row = add(db_session, model, **data)
    rejects(db_session, lambda: add(db_session, model, **data), "23505")
    row.revoked_at = datetime.now(UTC)
    row.revoked_by_user_id = row.granted_by_user_id
    db_session.flush()
    assert row.row_version == 2
    replacement = add(db_session, model, **data)
    assert replacement.id != row.id
    rejects(
        db_session,
        lambda: db_session.execute(
            update(model).where(model.id == row.id).values(revoked_at=None, revoked_by_user_id=None)
        ),
    )


@pytest.mark.parametrize("model", GRANTS)
def test_revocation_pair_and_chronology(db_session, model):
    data = payload(db_session, model)
    rejects(
        db_session, lambda: add(db_session, model, **(data | {"revoked_at": datetime.now(UTC)}))
    )
    rejects(
        db_session,
        lambda: add(
            db_session,
            model,
            **(
                data
                | {
                    "revoked_at": datetime.now(UTC) - timedelta(days=1),
                    "revoked_by_user_id": data["granted_by_user_id"],
                }
            ),
        ),
    )


@pytest.mark.parametrize(
    "model,field,value",
    [
        (UserRole, "user_id", uuid4()),
        (GuardianLearnerRelationship, "access_level", "manager"),
        (EducatorLearnerRelationship, "expires_at", datetime.now(UTC) + timedelta(days=60)),
    ],
)
def test_grant_payload_cannot_be_rewritten(db_session, model, field, value):
    row = add(db_session, model, **payload(db_session, model))
    rejects(
        db_session,
        lambda: db_session.execute(update(model).where(model.id == row.id).values({field: value})),
    )


def test_guardian_consent_authority_requires_verified_actor_and_time(db_session):
    data = payload(db_session, GuardianLearnerRelationship)
    rejects(
        db_session,
        lambda: add(
            db_session, GuardianLearnerRelationship, **(data | {"can_provide_consent": True})
        ),
    )
    rejects(
        db_session,
        lambda: add(
            db_session,
            GuardianLearnerRelationship,
            **(data | {"authority_verified_at": datetime.now(UTC)}),
        ),
    )
    row = add(
        db_session,
        GuardianLearnerRelationship,
        **(
            data
            | {
                "can_provide_consent": True,
                "authority_verified_at": datetime.now(UTC),
                "authority_verified_by_user_id": data["granted_by_user_id"],
            }
        ),
    )
    assert row.can_provide_consent


def test_many_guardians_and_educators_per_learner_and_many_learners_per_adult(db_session):
    owner = actor(db_session)
    learner = add(db_session, LearnerProfile, **payload(db_session, LearnerProfile, owner=owner))
    for model in (GuardianLearnerRelationship, EducatorLearnerRelationship):
        add(db_session, model, **payload(db_session, model, owner=owner, learner=learner))
        add(db_session, model, **payload(db_session, model, learner=learner))
        add(db_session, model, **payload(db_session, model, owner=owner))
        assert db_session.scalar(select(func.count()).select_from(model)) == 3


def test_educator_expiry_is_static_constraint_and_expired_grant_needs_closure(db_session):
    data = payload(db_session, EducatorLearnerRelationship)
    rejects(
        db_session,
        lambda: add(
            db_session,
            EducatorLearnerRelationship,
            **(data | {"expires_at": datetime.now(UTC) - timedelta(days=1)}),
        ),
    )
    data |= {
        "created_at": datetime.now(UTC) - timedelta(days=10),
        "expires_at": datetime.now(UTC) - timedelta(days=1),
    }
    expired = add(db_session, EducatorLearnerRelationship, **data)
    assert (
        db_session.scalar(
            select(EducatorLearnerRelationship.id).where(
                EducatorLearnerRelationship.id == expired.id,
                EducatorLearnerRelationship.revoked_at.is_(None),
                EducatorLearnerRelationship.expires_at > func.now(),
            )
        )
        is None
    )
    rejects(
        db_session,
        lambda: add(
            db_session,
            EducatorLearnerRelationship,
            **(data | {"expires_at": datetime.now(UTC) + timedelta(days=1)}),
        ),
        "23505",
    )


@pytest.mark.parametrize(
    "values",
    [
        {"text_scale": 0.74},
        {"text_scale": 3.01},
        {"line_spacing": 0.99},
        {"line_spacing": 3.01},
        {"theme": "unknown"},
        {"preferred_language_tag": " "},
    ],
)
def test_preference_checks(db_session, values):
    data = payload(db_session, LearnerPreferences) | values
    rejects(db_session, lambda: add(db_session, LearnerPreferences, **data))


def test_preferences_one_to_one_and_cascade(db_session):
    data = payload(db_session, LearnerPreferences)
    row = add(db_session, LearnerPreferences, **data)
    assert row.text_scale is None and row.reduce_motion is None
    rejects(db_session, lambda: add(db_session, LearnerPreferences, **data), "23505")
    db_session.execute(delete(LearnerProfile).where(LearnerProfile.id == row.learner_id))
    assert (
        db_session.scalar(select(LearnerPreferences.id).where(LearnerPreferences.id == row.id))
        is None
    )


USER_RESTRICT_FKS = [
    (UserRole, "user_id"),
    (UserRole, "granted_by_user_id"),
    (UserRole, "revoked_by_user_id"),
    (LearnerProfile, "created_by_user_id"),
    (GuardianLearnerRelationship, "guardian_user_id"),
    (GuardianLearnerRelationship, "granted_by_user_id"),
    (GuardianLearnerRelationship, "authority_verified_by_user_id"),
    (GuardianLearnerRelationship, "revoked_by_user_id"),
    (EducatorLearnerRelationship, "educator_user_id"),
    (EducatorLearnerRelationship, "granted_by_user_id"),
    (EducatorLearnerRelationship, "revoked_by_user_id"),
    (LearnerPreferences, "updated_by_user_id"),
    (ConsentNoticeVersion, "published_by_user_id"),
    (ConsentNoticeVersion, "retired_by_user_id"),
    (ConsentRecord, "recorded_by_user_id"),
]


@pytest.mark.parametrize("model,field", USER_RESTRICT_FKS)
def test_each_historical_user_fk_restricts_deletion(db_session, model, field):
    target = actor(db_session)
    data = payload(db_session, model) | {field: target.id}
    pairs = {
        "revoked_by_user_id": "revoked_at",
        "retired_by_user_id": "retired_at",
        "authority_verified_by_user_id": "authority_verified_at",
    }
    if field in pairs:
        data[pairs[field]] = datetime.now(UTC)
    add(db_session, model, **data)
    error = rejects(
        db_session, lambda: db_session.execute(delete(User).where(User.id == target.id)), "23503"
    )
    assert error.diag.table_name == model.__tablename__


@pytest.mark.parametrize(
    "model", [GuardianLearnerRelationship, EducatorLearnerRelationship, ConsentRecord]
)
def test_historical_learner_fk_restricts_deletion(db_session, model):
    data = payload(db_session, model)
    add(db_session, model, **data)
    rejects(
        db_session,
        lambda: db_session.execute(
            delete(LearnerProfile).where(LearnerProfile.id == data["learner_id"])
        ),
        "23503",
    )


def test_role_fk_restricts_deletion(db_session):
    row = add(db_session, UserRole, **payload(db_session, UserRole))
    rejects(
        db_session, lambda: db_session.execute(delete(Role).where(Role.id == row.role_id)), "23503"
    )


@pytest.mark.parametrize(
    "values",
    [
        {"content_sha256": "a" * 64},
        {"content_sha256": "NOT_A_HASH"},
        {"notice_text": " "},
        {"purpose_code": "unknown"},
        {"record_kind": "unknown"},
        {"version_label": " "},
        {"language_tag": " "},
        {"retired_at": datetime.now(UTC)},
    ],
)
def test_notice_integrity_checks(db_session, values):
    data = payload(db_session, ConsentNoticeVersion) | values
    rejects(db_session, lambda: add(db_session, ConsentNoticeVersion, **data))


def test_notice_unique_current_version_and_immutable_wording(db_session):
    data = payload(db_session, ConsentNoticeVersion)
    row = add(db_session, ConsentNoticeVersion, **data)
    rejects(db_session, lambda: add(db_session, ConsentNoticeVersion, **data), "23505")
    rejects(
        db_session,
        lambda: add(db_session, ConsentNoticeVersion, **(data | {"version_label": "v2"})),
        "23505",
    )
    new_text = "Changed synthetic text"
    rejects(
        db_session,
        lambda: db_session.execute(
            update(ConsentNoticeVersion)
            .where(ConsentNoticeVersion.id == row.id)
            .values(
                notice_text=new_text, content_sha256=hashlib.sha256(new_text.encode()).hexdigest()
            )
        ),
    )
    row.retired_at = datetime.now(UTC)
    row.retired_by_user_id = row.published_by_user_id
    db_session.flush()
    add(db_session, ConsentNoticeVersion, **(data | {"version_label": "v2"}))
    rejects(
        db_session,
        lambda: db_session.execute(
            update(ConsentNoticeVersion)
            .where(ConsentNoticeVersion.id == row.id)
            .values(retired_at=None, retired_by_user_id=None)
        ),
    )


@pytest.mark.parametrize(
    "values,state",
    [
        ({"purpose_code": "research_participation"}, "23503"),
        ({"record_kind": "unknown"}, "23514"),
        ({"guardian_relationship_id": uuid4()}, "23514"),
        ({"decision": "unknown"}, "23514"),
        ({"sequence_no": 0}, "23514"),
        ({"capture_method": "unknown"}, "23514"),
        ({"occurred_at": datetime.now(UTC) + timedelta(days=2)}, "23514"),
        ({"notice_version_id": uuid4()}, "23503"),
    ],
)
def test_consent_record_scope_and_value_checks(db_session, values, state):
    data = payload(db_session, ConsentRecord) | values
    rejects(db_session, lambda: add(db_session, ConsentRecord, **data), state)


def guardian_consent_payload(session):
    data = payload(session, ConsentRecord)
    guardian = add(
        session,
        GuardianLearnerRelationship,
        guardian_user_id=data["recorded_by_user_id"],
        learner_id=data["learner_id"],
        access_level="manager",
        granted_by_user_id=data["recorded_by_user_id"],
    )
    notice_data = payload(session, ConsentNoticeVersion) | {"record_kind": "guardian_consent"}
    notice = add(session, ConsentNoticeVersion, **notice_data)
    return data | {
        "guardian_relationship_id": guardian.id,
        "record_kind": notice.record_kind,
        "notice_version_id": notice.id,
    }


def test_guardian_consent_matches_the_same_learner_and_notice_kind(db_session):
    data = guardian_consent_payload(db_session)
    other = add(db_session, LearnerProfile, **payload(db_session, LearnerProfile))
    rejects(
        db_session,
        lambda: add(db_session, ConsentRecord, **(data | {"learner_id": other.id})),
        "23503",
    )
    rejects(
        db_session,
        lambda: add(db_session, ConsentRecord, **(data | {"guardian_relationship_id": None})),
    )
    assent_notice = add(
        db_session, ConsentNoticeVersion, **payload(db_session, ConsentNoticeVersion)
    )
    rejects(
        db_session,
        lambda: add(db_session, ConsentRecord, **(data | {"notice_version_id": assent_notice.id})),
        "23503",
    )
    add(db_session, ConsentRecord, **data)
    rejects(
        db_session,
        lambda: db_session.execute(
            delete(GuardianLearnerRelationship).where(
                GuardianLearnerRelationship.id == data["guardian_relationship_id"]
            )
        ),
        "23503",
    )


@pytest.mark.parametrize("kind", ["learner_assent", "guardian_consent"])
def test_consent_sequence_unique_with_null_guardian_and_append_only(db_session, kind):
    data = (
        guardian_consent_payload(db_session)
        if kind == "guardian_consent"
        else payload(db_session, ConsentRecord)
    )
    row = add(db_session, ConsentRecord, **data)
    rejects(db_session, lambda: add(db_session, ConsentRecord, **data), "23505")
    withdrawal = add(
        db_session, ConsentRecord, **(data | {"sequence_no": 2, "decision": "withdrawn"})
    )
    assert withdrawal.id != row.id
    rejects(
        db_session,
        lambda: db_session.execute(
            update(ConsentRecord).where(ConsentRecord.id == row.id).values(decision="declined")
        ),
    )
    rejects(
        db_session,
        lambda: db_session.execute(delete(ConsentRecord).where(ConsentRecord.id == row.id)),
    )
    rejects(db_session, lambda: db_session.execute(text("TRUNCATE consent_records")))
    rejects(
        db_session,
        lambda: db_session.execute(
            delete(ConsentNoticeVersion).where(ConsentNoticeVersion.id == row.notice_version_id)
        ),
        "23503",
    )


def test_optimistic_version_rejects_stale_write(db_session):
    row = add(db_session, LearnerProfile, **payload(db_session, LearnerProfile))
    # Simulate a competing committed writer in SQL while retaining the stale ORM instance.
    db_session.execute(
        update(LearnerProfile)
        .where(LearnerProfile.id == row.id)
        .values(display_name="Newer synthetic value", row_version=2)
        .execution_options(synchronize_session=False)
    )
    with pytest.raises(StaleDataError), db_session.begin_nested():
        row.display_name = "Stale synthetic value"
        db_session.flush()
    db_session.refresh(row)
    assert row.display_name == "Newer synthetic value"


def test_independent_sessions_detect_committed_version_conflict(postgres_engine):
    user_id = uuid4()
    with postgres_engine.begin() as connection:
        connection.execute(
            User.__table__.insert().values(
                id=user_id, login_handle="concurrency_" + user_id.hex[:16]
            )
        )
    try:
        with Session(postgres_engine) as first, Session(postgres_engine) as second:
            first_user = first.get(User, user_id)
            stale_user = second.get(User, user_id)
            assert first_user.row_version == stale_user.row_version == 1
            first_user.email = "first@example.test"
            first.commit()
            stale_user.email = "second@example.test"
            with pytest.raises(StaleDataError):
                second.commit()
            second.rollback()
            second.refresh(stale_user)
            assert stale_user.email == "first@example.test"
            assert stale_user.row_version == 2
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(delete(User).where(User.id == user_id))
