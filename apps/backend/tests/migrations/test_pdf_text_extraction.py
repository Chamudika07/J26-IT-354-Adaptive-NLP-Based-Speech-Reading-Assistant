"""One additive PDF migration, preserving original plain-text evidence."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text


@pytest.mark.integration
def test_pdf_upgrade_downgrade_preserves_plain_text(postgres_engine):
    with postgres_engine.begin() as connection:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0007_reading_material_processing")
        before = set(inspect(connection).get_table_names())
        user, learner, material, revision = (uuid4() for _ in range(4))
        connection.execute(
            text(
                "INSERT INTO users(id,login_handle,password_hash,status) "
                "VALUES (:id,:login,'synthetic','active')"
            ),
            {"id": user, "login": "synthetic_" + user.hex},
        )
        connection.execute(
            text(
                "INSERT INTO learner_profiles(id,display_name,created_by_user_id) "
                "VALUES (:id,'Synthetic',:actor)"
            ),
            {"id": learner, "actor": user},
        )
        connection.execute(
            text(
                "INSERT INTO reading_materials(id,learner_id,created_by_user_id) "
                "VALUES (:id,:learner,:actor)"
            ),
            {"id": material, "learner": learner, "actor": user},
        )
        connection.execute(
            text("""INSERT INTO reading_material_revisions
            (id,material_id,revision_number,title,language_tag,source_kind,original_text,
             source_sha256,created_by_user_id,created_at)
            VALUES (:id,:material,1,'Synthetic','en','plain_text','A cat.',
              encode(sha256(convert_to('A cat.','UTF8')),'hex'),:actor,now())"""),
            {"id": revision, "material": material, "actor": user},
        )
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) - before == {
            "reading_material_sources",
            "reading_material_extraction_runs",
            "reading_material_extraction_pages",
        }
        assert (
            connection.scalar(
                text("SELECT original_text FROM reading_material_revisions WHERE id=:id"),
                {"id": revision},
            )
            == "A cat."
        )
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0008_pdf_text_extraction"
        )
        command.check(config)
        command.downgrade(config, "0007_reading_material_processing")
        assert set(inspect(connection).get_table_names()) == before
        assert (
            connection.scalar(
                text("SELECT original_text FROM reading_material_revisions WHERE id=:id"),
                {"id": revision},
            )
            == "A cat."
        )
        command.upgrade(config, "head")
        command.check(config)
        connection.rollback()
