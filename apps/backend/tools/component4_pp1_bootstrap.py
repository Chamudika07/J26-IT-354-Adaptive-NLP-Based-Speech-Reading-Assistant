"""One-time operator bootstrap, not an application module or provisioning endpoint.

Execution requires separate approval for three fictional records and self-audit references.
No production code imports this tool. Shared Auth/Learners source is unchanged.
"""

import argparse
import getpass
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import create_db_engine, create_session_factory
from app.modules.auth.passwords import hash_password
from app.modules.learner_modelling.pp1_seed import configured_url, verify_target

HANDLE = "c4_demo_learner"
DISPLAY = "Fictional PP1 Learner"


def bootstrap(db: Session, password: str) -> UUID:
    """Operator-only transaction: refuse any existing account, never update records."""
    verify_target(db)
    if db.execute(text("SELECT count(*) FROM users")).scalar_one() != 0:
        raise ValueError("Bootstrap requires an empty fictional-account environment")
    role = db.execute(text("SELECT id FROM roles WHERE code='learner' AND is_active")).scalar_one()
    # Existing reviewed history-protection triggers apply on UPDATE, not INSERT.
    # Refuse unknown INSERT/DELETE triggers and non-return rewrite rules.
    if (
        db.execute(
            text(
                "SELECT count(*) FROM pg_trigger WHERE tgrelid IN "
                "('public.users'::regclass,'public.user_roles'::regclass,"
                "'public.learner_profiles'::regclass) "
                "AND NOT tgisinternal AND (tgtype::int & (4|8)) <> 0 AND tgenabled <> 'D'"
            )
        ).scalar_one()
        != 0
    ):
        raise ValueError("Unexpected insert/delete triggers; review required")
    if (
        db.execute(
            text(
                "SELECT count(*) FROM pg_rewrite WHERE ev_class IN "
                "('public.users'::regclass,'public.user_roles'::regclass,"
                "'public.learner_profiles'::regclass) "
                "AND rulename <> '_RETURN'"
            )
        ).scalar_one()
        != 0
    ):
        raise ValueError("Unexpected rewrite rules; review required")
    encoded = hash_password(password)
    user, grant, learner = uuid4(), uuid4(), uuid4()
    db.execute(
        text(
            "INSERT INTO users (id,login_handle,password_hash,status) "
            "VALUES (:id,:handle,:encoded,'active')"
        ),
        {"id": user, "handle": HANDLE, "encoded": encoded},
    )
    db.execute(
        text(
            "INSERT INTO user_roles (id,user_id,role_id,granted_by_user_id) "
            "VALUES (:id,:user,:role,:user)"
        ),
        {"id": grant, "user": user, "role": role},
    )
    db.execute(
        text(
            "INSERT INTO learner_profiles (id,learner_user_id,display_name,created_by_user_id) "
            "VALUES (:id,:user,:display,:user)"
        ),
        {"id": learner, "user": user, "display": DISPLAY},
    )
    result = db.execute(
        text(
            "SELECT count(*) FROM users u JOIN user_roles r ON r.user_id=u.id "
            "JOIN learner_profiles p ON p.learner_user_id=u.id "
            "WHERE u.id=:user AND u.status='active' AND r.role_id=:role "
            "AND r.granted_by_user_id=u.id AND r.revoked_at IS NULL "
            "AND p.created_by_user_id=u.id AND p.archived_at IS NULL"
        ),
        {"user": user, "role": role},
    ).scalar_one()
    if result != 1:
        raise ValueError("Fictional bootstrap verification failed")
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description="One-time fictional PP1 operator bootstrap")
    parser.add_argument(
        "--approve-three-fictional-records-and-self-audit", action="store_true", required=True
    )
    parser.parse_args()
    engine = None
    try:
        url = configured_url()  # Reject wrong environments before asking for a password.
        password = getpass.getpass("New fictional learner password (hidden): ")
        if password != getpass.getpass("Repeat fictional learner password (hidden): "):
            raise ValueError("Password confirmation differs")
        engine = create_db_engine(url)
        with create_session_factory(engine)() as db, db.begin():
            user = bootstrap(db, password)
        del password
        print(
            "Fictional PP1 account created and verified. Account UUID for server allowlist:", user
        )
    except Exception:
        raise SystemExit(
            "Fictional bootstrap stopped; transaction rolled back if opened."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
