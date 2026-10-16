"""Immutable instructor-observed reading assessments.

Revision ID: 0006_reading_assessments
Revises: 0005_auth_sessions
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_reading_assessments"
down_revision = "0005_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reading_assessment_materials",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("language_tag", sa.String(length=35), nullable=False),
        sa.Column("passage_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("tokenization_version", sa.String(length=80), nullable=False),
        sa.Column("administration_instructions", sa.Text(), nullable=False),
        sa.Column("comprehension_prompt_text", sa.Text(), nullable=True),
        sa.Column("comprehension_rubric_text", sa.Text(), nullable=True),
        sa.Column("comprehension_question_count", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "(comprehension_question_count = 0 AND comprehension_prompt_text IS "
            "NULL AND comprehension_rubric_text IS NULL) OR "
            "(comprehension_question_count > 0 AND comprehension_prompt_text IS "
            "NOT NULL AND comprehension_rubric_text IS NOT NULL AND "
            "length(btrim(comprehension_prompt_text)) > 0 AND "
            "length(btrim(comprehension_rubric_text)) > 0)",
            name=op.f("ck_reading_assessment_materials_comprehension_material"),
        ),
        sa.CheckConstraint(
            "comprehension_question_count >= 0",
            name=op.f("ck_reading_assessment_materials_questions_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(btrim(administration_instructions)) > 0",
            name=op.f("ck_reading_assessment_materials_administration_instructions_nonblank"),
        ),
        sa.CheckConstraint(
            "length(btrim(code)) > 0", name=op.f("ck_reading_assessment_materials_code_nonblank")
        ),
        sa.CheckConstraint(
            "length(btrim(language_tag)) > 0",
            name=op.f("ck_reading_assessment_materials_language_tag_nonblank"),
        ),
        sa.CheckConstraint(
            "length(btrim(passage_text)) > 0",
            name=op.f("ck_reading_assessment_materials_passage_text_nonblank"),
        ),
        sa.CheckConstraint(
            "length(btrim(title)) > 0", name=op.f("ck_reading_assessment_materials_title_nonblank")
        ),
        sa.CheckConstraint(
            "length(btrim(tokenization_version)) > 0",
            name=op.f("ck_reading_assessment_materials_tokenization_version_nonblank"),
        ),
        sa.CheckConstraint(
            "row_version > 0", name=op.f("ck_reading_assessment_materials_row_version_positive")
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_reading_assessment_materials_version_positive")
        ),
        sa.CheckConstraint(
            "word_count > 0", name=op.f("ck_reading_assessment_materials_word_count_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reading_assessment_materials")),
        sa.UniqueConstraint("code", "version", name="uq_reading_material_code_version"),
    )
    op.create_index(
        "ix_reading_material_active",
        "reading_assessment_materials",
        ["id"],
        unique=False,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "reading_assessment_sessions",
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("administered_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("collection_mode", sa.String(length=24), nullable=False),
        sa.Column("protocol_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "(status = 'started' AND completed_at IS NULL AND abandoned_at IS "
            "NULL) OR (status = 'completed' AND completed_at IS NOT NULL AND "
            "abandoned_at IS NULL) OR (status = 'abandoned' AND abandoned_at IS "
            "NOT NULL AND completed_at IS NULL)",
            name=op.f("ck_reading_assessment_sessions_state_timestamps"),
        ),
        sa.CheckConstraint(
            "collection_mode = 'instructor_observed'",
            name=op.f("ck_reading_assessment_sessions_mode_values"),
        ),
        sa.CheckConstraint(
            "abandoned_at IS NULL OR abandoned_at >= started_at",
            name=op.f("ck_reading_assessment_sessions_abandon_order"),
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name=op.f("ck_reading_assessment_sessions_complete_order"),
        ),
        sa.CheckConstraint(
            "length(btrim(protocol_version)) > 0",
            name=op.f("ck_reading_assessment_sessions_protocol_nonblank"),
        ),
        sa.CheckConstraint(
            "row_version > 0", name=op.f("ck_reading_assessment_sessions_row_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["administered_by_user_id"],
            ["users.id"],
            name=op.f("fk_reading_assessment_sessions_administered_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learner_profiles.id"],
            name=op.f("fk_reading_assessment_sessions_learner_id_learner_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["reading_assessment_materials.id"],
            name=op.f("fk_reading_assessment_sessions_material_id_reading_assessment_materials"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reading_assessment_sessions")),
    )
    op.create_index(
        op.f("ix_reading_assessment_sessions_administered_by_user_id"),
        "reading_assessment_sessions",
        ["administered_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reading_assessment_sessions_material_id"),
        "reading_assessment_sessions",
        ["material_id"],
        unique=False,
    )
    op.create_index(
        "ix_reading_session_history",
        "reading_assessment_sessions",
        ["learner_id", sa.literal_column("started_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "uq_reading_session_started",
        "reading_assessment_sessions",
        ["learner_id", "administered_by_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'started'"),
    )
    op.create_table(
        "reading_assessment_results",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reading_duration_ms", sa.Integer(), nullable=False),
        sa.Column("attempted_word_count", sa.Integer(), nullable=False),
        sa.Column("correct_word_count", sa.Integer(), nullable=False),
        sa.Column("omission_count", sa.Integer(), nullable=False),
        sa.Column("substitution_count", sa.Integer(), nullable=False),
        sa.Column("insertion_count", sa.Integer(), nullable=False),
        sa.Column("repetition_count", sa.Integer(), nullable=False),
        sa.Column("self_correction_count", sa.Integer(), nullable=False),
        sa.Column("unfamiliar_word_count", sa.Integer(), nullable=True),
        sa.Column("comprehension_correct", sa.Integer(), nullable=True),
        sa.Column("comprehension_total", sa.Integer(), nullable=True),
        sa.Column("scoring_version", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(comprehension_correct IS NULL AND comprehension_total IS NULL) OR "
            "(comprehension_correct IS NOT NULL AND comprehension_total IS NOT "
            "NULL AND comprehension_total > 0 AND comprehension_correct BETWEEN 0 "
            "AND comprehension_total)",
            name=op.f("ck_reading_assessment_results_comprehension_range"),
        ),
        sa.CheckConstraint(
            "attempted_word_count >= 0",
            name=op.f("ck_reading_assessment_results_attempted_word_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "correct_word_count <= attempted_word_count",
            name=op.f("ck_reading_assessment_results_correct_attempted"),
        ),
        sa.CheckConstraint(
            "correct_word_count >= 0",
            name=op.f("ck_reading_assessment_results_correct_word_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "insertion_count >= 0",
            name=op.f("ck_reading_assessment_results_insertion_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(btrim(scoring_version)) > 0",
            name=op.f("ck_reading_assessment_results_scoring_nonblank"),
        ),
        sa.CheckConstraint(
            "omission_count >= 0",
            name=op.f("ck_reading_assessment_results_omission_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "reading_duration_ms > 0", name=op.f("ck_reading_assessment_results_duration_positive")
        ),
        sa.CheckConstraint(
            "repetition_count >= 0",
            name=op.f("ck_reading_assessment_results_repetition_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "self_correction_count >= 0",
            name=op.f("ck_reading_assessment_results_self_correction_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "substitution_count >= 0",
            name=op.f("ck_reading_assessment_results_substitution_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "unfamiliar_word_count IS NULL OR unfamiliar_word_count BETWEEN 0 AND "
            "attempted_word_count",
            name=op.f("ck_reading_assessment_results_unfamiliar_range"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["reading_assessment_sessions.id"],
            name=op.f("fk_reading_assessment_results_session_id_reading_assessment_sessions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_reading_assessment_results_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reading_assessment_results")),
        sa.UniqueConstraint("session_id", name=op.f("uq_reading_assessment_results_session_id")),
    )
    op.create_index(
        op.f("ix_reading_assessment_results_submitted_by_user_id"),
        "reading_assessment_results",
        ["submitted_by_user_id"],
        unique=False,
    )
    _guards()


def downgrade() -> None:
    op.drop_table("reading_assessment_results")
    op.drop_table("reading_assessment_sessions")
    op.drop_table("reading_assessment_materials")
    for name in (
        "reading_material_guard",
        "reading_session_guard",
        "reading_result_guard",
        "reading_result_state_guard",
    ):
        op.execute(f"DROP FUNCTION {name}()")


def _guards() -> None:
    # No application imports: published schema and evidence rules stay reproducible.
    op.execute("""
    CREATE FUNCTION reading_material_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Immutable assessment material' USING ERRCODE = '23514';
        END IF;
        IF (to_jsonb(NEW) - ARRAY['is_active','updated_at','row_version']) IS DISTINCT FROM
           (to_jsonb(OLD) - ARRAY['is_active','updated_at','row_version']) THEN
            RAISE EXCEPTION 'Immutable assessment material' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER reading_material_immutable BEFORE UPDATE OR DELETE
        ON reading_assessment_materials FOR EACH ROW EXECUTE FUNCTION reading_material_guard();
    """)
    op.execute("""
    CREATE FUNCTION reading_session_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Immutable assessment session' USING ERRCODE = '23514';
        ELSIF TG_OP = 'INSERT' THEN
            IF NEW.status <> 'started' THEN
                RAISE EXCEPTION 'Assessment must start' USING ERRCODE = '23514';
            END IF;
        ELSE
            IF OLD.status <> 'started' OR
               (to_jsonb(NEW) - ARRAY['status','completed_at','abandoned_at',
                   'updated_at','row_version'])
               IS DISTINCT FROM
               (to_jsonb(OLD) - ARRAY['status','completed_at','abandoned_at',
                   'updated_at','row_version'])
            THEN
                RAISE EXCEPTION 'Immutable assessment session' USING ERRCODE = '23514';
            END IF;
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER reading_session_immutable BEFORE INSERT OR UPDATE OR DELETE
        ON reading_assessment_sessions FOR EACH ROW EXECUTE FUNCTION reading_session_guard();
    """)
    op.execute("""
    CREATE FUNCTION reading_result_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        target reading_assessment_sessions%ROWTYPE;
        material reading_assessment_materials%ROWTYPE;
    BEGIN
        IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'Immutable assessment result' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO target FROM reading_assessment_sessions
            WHERE id = NEW.session_id FOR UPDATE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Invalid assessment result' USING ERRCODE = '23503';
        END IF;
        IF target.status <> 'started' OR
           NEW.submitted_by_user_id <> target.administered_by_user_id OR
           NEW.submitted_at < target.started_at THEN
            RAISE EXCEPTION 'Invalid assessment result' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO STRICT material FROM reading_assessment_materials
            WHERE id = target.material_id;
        IF NEW.attempted_word_count::bigint + NEW.omission_count::bigint > material.word_count OR
           (material.comprehension_question_count = 0 AND
               (NEW.comprehension_total IS NOT NULL OR NEW.comprehension_correct IS NOT NULL)) OR
           (material.comprehension_question_count > 0 AND
               (NEW.comprehension_total IS DISTINCT FROM material.comprehension_question_count OR
                NEW.comprehension_correct IS NULL)) THEN
            RAISE EXCEPTION 'Invalid assessment observations' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER reading_result_immutable BEFORE INSERT OR UPDATE OR DELETE
        ON reading_assessment_results FOR EACH ROW EXECUTE FUNCTION reading_result_guard();
    """)
    op.execute("""
    CREATE FUNCTION reading_result_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        identity uuid;
        state text;
        completion timestamptz;
        submission timestamptz;
        has_result boolean;
    BEGIN
        IF TG_TABLE_NAME = 'reading_assessment_sessions' THEN
            identity := NEW.id;
        ELSE
            identity := NEW.session_id;
        END IF;
        SELECT status, completed_at INTO state, completion
            FROM reading_assessment_sessions WHERE id = identity;
        SELECT submitted_at INTO submission FROM reading_assessment_results
            WHERE session_id = identity;
        has_result := FOUND;
        IF (state = 'completed') IS DISTINCT FROM has_result OR
           (has_result AND submission > completion) THEN
            RAISE EXCEPTION 'Invalid assessment result state' USING ERRCODE = '23514';
        END IF;
        RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER reading_session_result_state
        AFTER INSERT OR UPDATE ON reading_assessment_sessions
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reading_result_state_guard();
    CREATE CONSTRAINT TRIGGER reading_result_session_state
        AFTER INSERT ON reading_assessment_results
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reading_result_state_guard();
    """)
