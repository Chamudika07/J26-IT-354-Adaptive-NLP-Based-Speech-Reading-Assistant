"""Internal development orphan cleanup: python -m app.modules.reading_materials.pdf.cleanup."""

import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DatabaseSettings
from app.db.session import create_db_engine
from app.modules.reading_materials.pdf.models import Source
from app.modules.reading_materials.pdf.storage import LocalStorage


def main() -> None:
    from app.db import model_registry  # noqa: F401

    settings = DatabaseSettings()
    storage = LocalStorage(Path(os.environ["PDF_STORAGE_ROOT"]))
    engine = create_db_engine(settings.database_url)
    try:

        def referenced(key: str) -> bool:
            with Session(engine) as db:
                return (
                    db.scalar(
                        select(Source.id)
                        .where(Source.storage_backend == storage.backend, Source.storage_key == key)
                        .limit(1)
                    )
                    is not None
                )

        count = storage.cleanup(referenced)
        print(f"Removed {count} old unreferenced objects")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
