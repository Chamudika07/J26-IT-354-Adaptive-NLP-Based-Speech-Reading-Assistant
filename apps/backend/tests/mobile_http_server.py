"""Explicit synthetic HTTP fixture; only the dedicated disposable mobile DB is accepted."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_db_engine
from app.main import create_app
from app.modules.assessments.models import ReadingAssessmentMaterial
from app.modules.auth.models import Role, User, UserRole
from app.modules.auth.passwords import hash_password
from app.modules.auth.provisioning import bootstrap_administrator
from app.modules.auth.provisioning_schemas import AccountCreate
from app.modules.learners.models import LearnerProfile


def main() -> None:
    value = os.environ["TEST_DATABASE_URL"]
    url = make_url(value)
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "mobile_test"
        or url.host != "127.0.0.1"
        or url.port != 55432
        or os.environ.get("ALLOW_TEST_DATABASE_RESET") != "1"
    ):
        raise RuntimeError("Requires the exclusive disposable mobile_test container")
    private_storage = TemporaryDirectory(prefix="nlp-mobile-pdf-")
    settings = Settings(
        _env_file=None,
        app_env="test",
        log_level="WARNING",
        database_url=SecretStr(value),
        jwt_signing_key=SecretStr("synthetic-mobile-http-fixture-key-never-deploy"),
        pdf_storage_root=Path(private_storage.name),
    )
    engine = create_db_engine(settings.database_url)
    with engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(engine) as db:
        admin = bootstrap_administrator(
            db,
            AccountCreate(
                login_handle="synthetic.mobile.admin",
                password="Synthetic mobile fixture passphrase 42",
            ),
        )
        # Only synthetic fixture data; these capabilities have no public provisioning API.
        db.add(
            ReadingAssessmentMaterial(
                code="synthetic-mobile",
                version=1,
                title="Synthetic original passage",
                language_tag="en",
                passage_text="A cat rests. A dog runs!",
                word_count=6,
                tokenization_version="synthetic-whitespace-v1",
                administration_instructions="Time the reading, then record observed counts.",
                comprehension_question_count=0,
            )
        )
        reader = User(
            login_handle="synthetic.mobile.reader",
            status="active",
            password_hash=hash_password("Synthetic mobile fixture passphrase 42"),
        )
        db.add(reader)
        db.flush()
        role = db.scalar(select(Role).where(Role.code == "learner"))
        assert role is not None
        db.add(UserRole(user_id=reader.id, role_id=role.id, granted_by_user_id=admin.user_id))
        db.add(
            LearnerProfile(
                display_name="Synthetic self reader",
                learner_user_id=reader.id,
                created_by_user_id=admin.user_id,
            )
        )
        db.commit()
    engine.dispose()
    try:
        uvicorn.run(
            create_app(settings),
            host="127.0.0.1",
            port=18000,
            access_log=False,
            log_level="warning",
        )
    finally:
        private_storage.cleanup()


if __name__ == "__main__":
    main()
