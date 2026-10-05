"""One engine per app lifespan; one session per request, with explicit commits."""

from collections.abc import Iterator
from typing import cast

from fastapi import Request
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_db_engine(database_url: SecretStr) -> Engine:
    return create_engine(
        database_url.get_secret_value(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"},
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    # Closing also rolls back unfinished transactions; services explicitly commit.
    with factory() as session:
        yield session
