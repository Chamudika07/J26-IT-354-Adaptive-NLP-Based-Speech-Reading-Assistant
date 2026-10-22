"""0009 upgrade, checked metadata parity, preservation, and explicit loss refusal."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from tests.ocr.conftest import domain as _domain
from tests.ocr.conftest import pending as _pending

domain = _domain
pending = _pending

pytestmark = pytest.mark.integration


def config(db):
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.attributes["connection"] = db.connection()
    return cfg


def test_upgrade_backfills_direct_rows_and_safe_downgrade(domain):
    db, user, learner, source, parent = domain
    cfg = config(db)
    command.downgrade(cfg, "0008_pdf_text_extraction")
    assert "extraction_method" not in {
        c["name"] for c in inspect(db.connection()).get_columns("reading_material_extraction_runs")
    }
    before = db.scalar(
        text("SELECT assembled_text_sha256 FROM reading_material_extraction_runs WHERE id=:id"),
        {"id": parent.id},
    )
    command.upgrade(cfg, "head")
    assert ScriptDirectory.from_config(cfg).get_heads() == ["0009_ocr_review_workflow"]
    row = db.execute(
        text(
            "SELECT extraction_method,assembled_text_sha256 "
            "FROM reading_material_extraction_runs WHERE id=:id"
        ),
        {"id": parent.id},
    ).one()
    assert row == ("embedded_pdf", before)
    command.check(cfg)
    command.downgrade(cfg, "0008_pdf_text_extraction")
    assert not any(
        "extraction_review" in name for name in inspect(db.connection()).get_table_names()
    )
    command.upgrade(cfg, "head")
    command.check(cfg)


def test_downgrade_refuses_ocr_history(pending):
    db, *_ = pending
    with pytest.raises(IntegrityError, match="Downgrade refused"), db.begin_nested():
        command.downgrade(config(db), "0008_pdf_text_extraction")
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0009_ocr_review_workflow"
