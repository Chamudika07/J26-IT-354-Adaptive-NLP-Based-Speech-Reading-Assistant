"""Migrate all modules through one shared history, never on application startup."""

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from app.core.config import Settings
from app.db.model_registry import target_metadata


def configured_url() -> str:
    settings = Settings()
    return (settings.migration_database_url or settings.database_url).get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=configured_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate_connection(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests inject an explicitly guarded PostgreSQL connection: never read a developer .env.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        migrate_connection(connection)
        return
    engine = create_engine(
        configured_url(),
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"},
    )
    try:
        with engine.connect() as connection:
            migrate_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
