"""PostgreSQL enforces credential integrity even outside service code."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.modules.auth import service
from app.modules.auth.models import AuthRefreshToken, AuthSession, User

pytestmark = pytest.mark.integration


@pytest.fixture
def persisted_session(db_session, active_user, settings):
    service.login(
        db_session, settings, active_user.login_handle, "Synthetic accessible passphrase 42"
    )
    return db_session.scalar(select(AuthSession)), db_session.scalar(select(AuthRefreshToken))


@pytest.mark.parametrize(
    "field,value",
    [
        ("row_version", 0),
        ("revocation_reason", "invalid"),
        ("revocation_reason", "logout"),
        ("user_id", uuid4()),
    ],
)
def test_invalid_session_fields(db_session, persisted_session, field, value):
    session, _ = persisted_session
    with pytest.raises(IntegrityError), db_session.begin_nested():
        # Core update deliberately bypasses ORM version generation for DB constraint testing.
        db_session.execute(
            AuthSession.__table__.update()
            .where(AuthSession.id == session.id)
            .values({field: value})
        )


@pytest.mark.parametrize(
    "field", ["authenticated_at", "expires_at", "idle_expires_at", "revoked_at"]
)
def test_invalid_session_timestamp_order(db_session, persisted_session, field):
    session, _ = persisted_session
    invalid = (
        session.created_at + timedelta(seconds=1)
        if field == "authenticated_at"
        else session.created_at - timedelta(seconds=1)
    )
    values = {field: invalid}
    if field == "revoked_at":
        values["revocation_reason"] = "logout"
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            AuthSession.__table__.update().where(AuthSession.id == session.id).values(values)
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("token_digest", b"short"),
        ("generation", -1),
        ("session_id", uuid4()),
    ],
)
def test_invalid_refresh_fields(db_session, persisted_session, field, value):
    _, token = persisted_session
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            AuthRefreshToken.__table__.update()
            .where(AuthRefreshToken.id == token.id)
            .values({field: value})
        )


@pytest.mark.parametrize("field", ["expires_at", "consumed_at"])
def test_invalid_refresh_timestamp_order(db_session, persisted_session, field):
    _, token = persisted_session
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            AuthRefreshToken.__table__.update()
            .where(AuthRefreshToken.id == token.id)
            .values({field: token.created_at - timedelta(seconds=1)})
        )


@pytest.mark.parametrize("duplicate", ["digest", "generation", "current"])
def test_unique_refresh_rules(db_session, persisted_session, duplicate):
    session, token = persisted_session
    values = dict(
        session_id=session.id,
        generation=1,
        token_digest=b"n" * 32,
        created_at=token.created_at,
        expires_at=token.expires_at,
        consumed_at=token.created_at,
    )
    if duplicate == "digest":
        values["token_digest"] = token.token_digest
    elif duplicate == "generation":
        values["generation"] = 0
    else:
        values["consumed_at"] = None
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(AuthRefreshToken(**values))
        db_session.flush()


def test_session_user_restrict_and_credential_cascade(db_session, persisted_session):
    session, token = persisted_session
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(delete(User).where(User.id == session.user_id))
    db_session.execute(delete(AuthSession).where(AuthSession.id == session.id))
    assert (
        db_session.scalar(select(AuthRefreshToken).where(AuthRefreshToken.id == token.id)) is None
    )
