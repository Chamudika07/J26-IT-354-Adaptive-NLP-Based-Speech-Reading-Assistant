"""Additive 0006 -> 0007 migration, existing evidence preservation, and rollback."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


@pytest.mark.integration
def test_reading_material_upgrade_downgrade_and_preservation(postgres_engine):
    with postgres_engine.begin() as connection:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0006_reading_assessments")
        before = set(inspect(connection).get_table_names())
        identity = uuid4()
        connection.execute(
            text(
                "INSERT INTO reading_assessment_materials "
                "(id,code,version,title,language_tag,passage_text,word_count,tokenization_version,"
                "administration_instructions,comprehension_question_count) VALUES "
                "(:id,:code,1,'Synthetic original','en','A cat rests.',3,"
                "'synthetic-v1','Read once.',0)"
            ),
            {"id": identity, "code": "synthetic_" + identity.hex},
        )
        command.upgrade(config, "head")
        added = {
            "reading_materials",
            "reading_material_revisions",
            "reading_material_processing_runs",
            "reading_material_sentence_features",
            "reading_material_sources",
            "reading_material_extraction_runs",
            "reading_material_extraction_pages",
        }
        assert set(inspect(connection).get_table_names()) - before == added
        assert (
            connection.scalar(
                text("SELECT passage_text FROM reading_assessment_materials WHERE id=:id"),
                {"id": identity},
            )
            == "A cat rests."
        )
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0008_pdf_text_extraction"
        )
        command.check(config)
        command.downgrade(config, "0006_reading_assessments")
        assert set(inspect(connection).get_table_names()) == before
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_proc WHERE proname IN "
                    "('rm_material_guard','rm_revision_guard','rm_run_guard','rm_sentence_guard',"
                    "'rm_run_consistency','rm_sentence_state')"
                )
            )
            == 0
        )
        command.upgrade(config, "head")
        command.check(config)
        # Existing assessment materials are immutable; roll back this whole migration exercise.
        connection.rollback()
