"""Direct SQL cannot rewrite evidence or leave an inconsistent completion."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.modules.assessments.models import ReadingAssessmentResult as Result
from app.modules.auth import repository as auth_repo

pytestmark = pytest.mark.integration


def insert_result(db, row, actor, observations, **overrides):
    values = {k: v for k, v in observations.items() if k != "row_version"}
    values.update(overrides)
    result = Result(
        session_id=row.id,
        submitted_by_user_id=actor.id,
        submitted_at=auth_repo.now(db),
        scoring_version="reading-scoring-v1",
        **values,
    )
    db.add(result)
    db.flush()
    return result


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE reading_assessment_materials SET passage_text = 'changed' WHERE id = :id",
        "UPDATE reading_assessment_materials SET word_count = 12 WHERE id = :id",
        "UPDATE reading_assessment_materials SET version = 2 WHERE id = :id",
        "DELETE FROM reading_assessment_materials WHERE id = :id",
    ],
)
def test_material_evidence_immutable(db_session, material_factory, statement):
    material = material_factory()
    identity = material.id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(text(statement), {"id": identity})


@pytest.mark.parametrize(
    "values",
    [
        {"version": 0},
        {"word_count": 0},
        {"code": " "},
        {"title": ""},
        {"language_tag": " "},
        {"tokenization_version": ""},
        {"administration_instructions": ""},
        {"comprehension_question_count": -1},
        {"comprehension_question_count": 1},
        {"comprehension_prompt_text": "Unexpected prompt"},
    ],
)
def test_material_constraints(db_session, material_factory, values):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        material_factory(**values)


@pytest.mark.parametrize(
    "field, value",
    [
        ("protocol_version", "changed"),
        ("collection_mode", "self_reported"),
        ("learner_id", "00000000-0000-0000-0000-000000000001"),
        ("material_id", "00000000-0000-0000-0000-000000000001"),
        ("administered_by_user_id", "00000000-0000-0000-0000-000000000001"),
    ],
)
def test_session_identity_immutable(db_session, assessment_setup, stored_session, field, value):
    row = stored_session(assessment_setup())
    identity = row.id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        # field comes only from the fixed parametrization above.
        db_session.execute(
            text(f"UPDATE reading_assessment_sessions SET {field} = :value WHERE id = :id"),
            {"value": value, "id": identity},
        )


@pytest.mark.parametrize(
    "values",
    [
        {"reading_duration_ms": 0},
        {"correct_word_count": 9},
        {"attempted_word_count": 12},
        {"omission_count": 4},
        {"substitution_count": -1},
        {"insertion_count": -1},
        {"repetition_count": -1},
        {"self_correction_count": -1},
        {"unfamiliar_word_count": 9},
        {"comprehension_correct": 1, "comprehension_total": 1},
    ],
)
def test_raw_result_constraints(
    db_session, assessment_setup, stored_session, active_user, observations, values
):
    row = stored_session(assessment_setup())
    with pytest.raises(IntegrityError), db_session.begin_nested():
        insert_result(db_session, row, active_user, observations, **values)


@pytest.mark.parametrize(
    "invalid_state", ["result_without_completion", "completion_without_result"]
)
def test_deferred_state_integrity(
    db_session, assessment_setup, stored_session, active_user, observations, invalid_state
):
    row = stored_session(assessment_setup())
    with pytest.raises(IntegrityError), db_session.begin_nested():
        if invalid_state == "result_without_completion":
            insert_result(db_session, row, active_user, observations)
        else:
            db_session.execute(
                text(
                    "UPDATE reading_assessment_sessions SET status='completed', "
                    "completed_at=clock_timestamp() WHERE id=:id"
                ),
                {"id": row.id},
            )
        db_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE reading_assessment_results SET correct_word_count = 5 WHERE session_id=:id",
        "DELETE FROM reading_assessment_results WHERE session_id=:id",
        "UPDATE reading_assessment_sessions SET status='started', completed_at=NULL WHERE id=:id",
        "UPDATE reading_assessment_sessions SET row_version=row_version+1 WHERE id=:id",
        "DELETE FROM reading_assessment_sessions WHERE id=:id",
    ],
)
def test_completed_evidence_cannot_be_mutated(
    db_session, assessment_setup, stored_session, active_user, observations, statement
):
    row = stored_session(assessment_setup())
    insert_result(db_session, row, active_user, observations)
    row.status, row.completed_at = "completed", auth_repo.now(db_session)
    db_session.flush()
    db_session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    identity = row.id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(text(statement), {"id": identity})


def test_abandoned_session_cannot_reopen(db_session, assessment_setup, stored_session):
    row = stored_session(assessment_setup())
    row.status, row.abandoned_at = "abandoned", auth_repo.now(db_session)
    db_session.flush()
    identity = row.id
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "UPDATE reading_assessment_sessions SET status='started', "
                "abandoned_at=NULL WHERE id=:id"
            ),
            {"id": identity},
        )


def test_material_unique_and_session_unique(
    db_session, assessment_setup, stored_session, material_factory
):
    c = assessment_setup()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        material_factory(code=c["material"].code)
    stored_session(c)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        stored_session(c)


@pytest.mark.parametrize(
    "field",
    [
        "reading_duration_ms",
        "attempted_word_count",
        "correct_word_count",
        "omission_count",
        "substitution_count",
        "insertion_count",
        "repetition_count",
        "self_correction_count",
    ],
)
def test_required_counts_cannot_be_null(
    db_session, assessment_setup, stored_session, active_user, observations, field
):
    row = stored_session(assessment_setup())
    with pytest.raises(IntegrityError), db_session.begin_nested():
        insert_result(db_session, row, active_user, observations, **{field: None})


@pytest.mark.parametrize("total,correct", [(None, None), (1, 1), (2, 3), (2, None)])
def test_database_requires_exact_question_set(
    db_session, assessment_setup, stored_session, active_user, observations, total, correct
):
    c = assessment_setup(
        comprehension_question_count=2,
        comprehension_prompt_text="Synthetic prompts",
        comprehension_rubric_text="Synthetic rubric",
    )
    row = stored_session(c)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        insert_result(
            db_session,
            row,
            active_user,
            observations,
            comprehension_total=total,
            comprehension_correct=correct,
        )


def test_duplicate_result_rejected(
    db_session, assessment_setup, stored_session, active_user, observations
):
    row = stored_session(assessment_setup())
    insert_result(db_session, row, active_user, observations)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        insert_result(db_session, row, active_user, observations)


@pytest.mark.parametrize(
    "values",
    [
        {"status": "completed"},
        {"status": "abandoned"},
        {"collection_mode": "self_reported"},
    ],
)
def test_invalid_initial_session_state(db_session, assessment_setup, stored_session, values):
    c = assessment_setup()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        stored_session(c, **values)
