"""Explicit local-development bootstrap; never run on application startup."""

import argparse
import getpass
import warnings

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.exceptions import SecurityError
from app.db.session import create_db_engine, create_session_factory
from app.modules.auth.provisioning import bootstrap_administrator
from app.modules.auth.provisioning_schemas import AccountCreate


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first local development administrator")
    parser.add_argument("--confirm-local-development", action="store_true", required=True)
    parser.parse_args()
    try:
        settings = Settings()
        if settings.app_env != "development":
            print("Bootstrap is restricted to APP_ENV=development.")
            return 1
        handle = input("Administrator login handle: ")
        # Fail closed if the terminal cannot disable echo; never fall back to stdin.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Password (15-128 characters): ")
            confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match; nothing created.")
            return 1
        payload = AccountCreate(login_handle=handle, password=password)
        engine = create_db_engine(settings.database_url)
        try:
            with create_session_factory(engine)() as db:
                result = bootstrap_administrator(db, payload)
            print(f"Administrator created: {result.user_id}. Sign in through /api/v1/auth/login.")
        finally:
            engine.dispose()
        return 0
    except ValidationError:
        print("Invalid configuration or account input; private values suppressed.")
    except SecurityError as exc:
        print(exc.message)
    except SQLAlchemyError:
        print("Database operation failed; check connectivity and migration state.")
    except (EOFError, KeyboardInterrupt):
        print("Bootstrap cancelled.")
    except getpass.GetPassWarning:
        print("A terminal with hidden password input is required; nothing created.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
