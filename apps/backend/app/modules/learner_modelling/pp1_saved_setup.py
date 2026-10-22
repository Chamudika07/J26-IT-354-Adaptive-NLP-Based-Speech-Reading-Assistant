"""Guarded owner-only installation of approved synthetic session storage; no grants/seed."""

import argparse
import getpass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy import inspect, text
from sqlalchemy.engine import URL

from app.db.session import create_db_engine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve-pp1-saved-storage", action="store_true", required=True)
    parser.parse_args()
    engine = None
    try:
        backend = Path(__file__).resolve().parents[3]
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "alembic"))
        if ScriptDirectory.from_config(config).get_heads() != ["0008_c4_pp1_saved"]:
            raise ValueError("Unexpected history")
        password = getpass.getpass("PP1 owner database password (hidden): ")
        url = URL.create(
            "postgresql+psycopg",
            username="readbuddy_c4_pp1_owner",
            password=password,
            host="127.0.0.1",
            port=5432,
            database="readbuddy_component4_pp1_demo",
        )
        del password
        engine = create_db_engine(SecretStr(url.render_as_string(hide_password=False)))
        with engine.begin() as db:
            if tuple(
                db.execute(
                    text(
                        "SELECT current_database(),current_user,"
                        "host(inet_server_addr()),inet_server_port()"
                    )
                ).one()
            ) != ("readbuddy_component4_pp1_demo", "readbuddy_c4_pp1_owner", "127.0.0.1", 5432):
                raise ValueError("Wrong environment")
            if db.execute(text("SELECT version_num FROM alembic_version")).scalars().all() != [
                "0007_c4_pp1_demo"
            ]:
                raise ValueError("Unexpected starting revision; do not retry blindly")
            before = set(inspect(db).get_table_names(schema="public"))
            if "component4_pp1_saved_sessions" in before:
                raise ValueError("Unexpected existing storage")
            config.attributes["connection"] = db
            command.upgrade(config, "0008_c4_pp1_saved")
            after = set(inspect(db).get_table_names(schema="public"))
            if after != before | {"component4_pp1_saved_sessions"}:
                raise ValueError("Unexpected schema changes")
            if (
                db.execute(text("SELECT count(*) FROM component4_pp1_saved_sessions")).scalar_one()
                != 0
            ):
                raise ValueError("Unexpected saved data")
        print("PP1 synthetic session storage installed and verified. No grants or data inserted.")
    except Exception:
        raise SystemExit(
            "PP1 storage setup stopped; transaction rolled back if opened. Review before retry."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
