"""Explicit fixed-fixture seed for the standalone temporary PP1 environment only."""

import argparse
import json
import os
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.session import create_db_engine, create_session_factory
from app.modules.learner_modelling.pp1_demo import APPROVED_DIGEST, FIXTURE, dataset_digest
from app.modules.learner_modelling.pp1_models import Pp1DemoDataset

TARGET = "readbuddy_component4_pp1_demo"
PROVENANCE = {
    "synthetic": True,
    "fixture": "pp1_fixture.json",
    "generator": "component4-python-engines-v1",
}


def configured_url() -> SecretStr:
    raw = os.environ.get("READBUDDY_PP1_DATABASE_URL", "")
    if os.environ.get("APP_ENV") != "development":
        raise ValueError("Development configuration required")
    try:
        url = make_url(raw)
        valid = (
            url.drivername == "postgresql+psycopg"
            and url.host == "127.0.0.1"
            and url.port == 5432
            and url.database == TARGET
            and bool(url.username)
            and url.username != "postgres"
            and not url.query
        )
    except Exception:
        valid = False
    if not valid:
        raise ValueError("Unexpected PP1 database configuration")
    return SecretStr(raw)


def verify_target(db: Session) -> None:
    database, user = db.execute(text("SELECT current_database(), current_user")).one()
    if database != TARGET or user == "postgres":
        raise ValueError("Unexpected PP1 database identity")
    if not db.execute(
        text("SELECT NOT rolsuper FROM pg_roles WHERE rolname=current_user")
    ).scalar_one():
        raise ValueError("Non-superuser required")
    if db.execute(text("SELECT version_num FROM alembic_version")).scalars().all() != [
        "0007_c4_pp1_demo"
    ]:
        raise ValueError("Expected PP1 migration head")


def seed_dataset(db: Session) -> bool:
    """Caller owns transaction. Insert once, verify existing data, never overwrite."""
    raw = FIXTURE.read_text(encoding="utf-8")
    if dataset_digest(raw) != APPROVED_DIGEST:
        raise ValueError("Unapproved fixture")
    payload = json.loads(raw)
    inserted = db.execute(
        insert(Pp1DemoDataset)
        .values(
            id=uuid4(),
            dataset_key="pp1-six-session-journey",
            fixture_version=1,
            source_digest=APPROVED_DIGEST,
            source_payload=payload,
            provenance=PROVENANCE,
        )
        .on_conflict_do_nothing(index_elements=["dataset_key"])
        .returning(Pp1DemoDataset.id)
    ).scalar_one_or_none()
    row = db.execute(
        select(Pp1DemoDataset).where(Pp1DemoDataset.dataset_key == "pp1-six-session-journey")
    ).scalar_one()
    if (
        row.fixture_version != 1
        or row.source_digest != APPROVED_DIGEST
        or row.provenance != PROVENANCE
        or row.source_payload != payload
        or dataset_digest(json.dumps(row.source_payload)) != APPROVED_DIGEST
    ):
        raise ValueError("Existing dataset differs; nothing overwritten")
    return inserted is not None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed only the fixed standalone fictional PP1 dataset"
    )
    parser.add_argument("--development-synthetic-only", action="store_true", required=True)
    parser.parse_args()
    engine = None
    try:
        engine = create_db_engine(configured_url())
        with create_session_factory(engine)() as db, db.begin():
            verify_target(db)
            created = seed_dataset(db)
        print(
            "PP1 dataset: created and verified"
            if created
            else "PP1 dataset: already present and verified"
        )
    except Exception:
        raise SystemExit(
            "PP1 seed stopped; transaction rolled back if opened. No credentials displayed."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
