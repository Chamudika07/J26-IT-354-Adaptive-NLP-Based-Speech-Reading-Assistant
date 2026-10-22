"""Upgrade each pre-merge branch head without losing its existing evidence."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from db_test_safety import validate_test_database_connection

MERGED_TABLES = {
    "simplification_sessions",
    "simplification_vocabulary",
    "simplification_feedback",
    "reading_assessment_materials",
    "reading_assessment_sessions",
    "reading_assessment_results",
    "reading_materials",
    "reading_material_revisions",
    "reading_material_processing_runs",
    "reading_material_sentence_features",
    "reading_material_sources",
    "reading_material_extraction_runs",
    "reading_material_extraction_pages",
}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("start_revision", "evidence_table", "evidence_column", "evidence_value"),
    [
        (
            "0006_simplification_tables",
            "simplification_vocabulary",
            "simplified_definition",
            "A synthetic definition retained across the merge.",
        ),
        (
            "0008_pdf_text_extraction",
            "reading_assessment_materials",
            "passage_text",
            "Synthetic reading evidence.",
        ),
    ],
)
def test_pre_merge_branch_head_upgrades_to_merged_head(
    postgres_engine, start_revision, evidence_table, evidence_column, evidence_value
):
    with postgres_engine.begin() as connection:
        validate_test_database_connection(connection, postgres_engine.url.database)
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, start_revision)
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == start_revision

        evidence_id = uuid4()
        if start_revision == "0006_simplification_tables":
            connection.execute(
                text(
                    "INSERT INTO simplification_vocabulary "
                    "(id,term,simplified_definition,source,language_tag) "
                    "VALUES (:id,'synthetic-term',:value,'user','en')"
                ),
                {"id": evidence_id, "value": evidence_value},
            )
        else:
            connection.execute(
                text(
                    "INSERT INTO reading_assessment_materials "
                    "(id,code,version,title,language_tag,passage_text,word_count,"
                    "tokenization_version,administration_instructions,"
                    "comprehension_question_count) VALUES "
                    "(:id,:code,1,'Synthetic material','en',:value,3,'synthetic-v1',"
                    "'Read once.',0)"
                ),
                {
                    "id": evidence_id,
                    "code": "synthetic_" + evidence_id.hex,
                    "value": evidence_value,
                },
            )

        command.upgrade(config, "head")

        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0009_merge_heads"
        )
        assert MERGED_TABLES <= set(inspect(connection).get_table_names())
        assert (
            connection.scalar(
                text(f'SELECT "{evidence_column}" FROM "{evidence_table}" WHERE id=:id'),
                {"id": evidence_id},
            )
            == evidence_value
        )
        command.check(config)
