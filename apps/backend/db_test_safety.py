"""Pure URL guards for tests that may connect to disposable PostgreSQL."""

import ipaddress

from sqlalchemy import Connection, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

PROTECTED_DATABASES = frozenset({"readbuddy_component2_test", "readbuddy_c2_dev"})
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
TARGET_OVERRIDE_PARAMETERS = frozenset(
    {"database", "dbname", "host", "hostaddr", "service", "servicefile"}
)


def is_loopback_server_address(address: str | None) -> bool:
    """Accept PostgreSQL inet output, including IPv4 and IPv6 CIDR notation."""
    if address is None:
        return False
    try:
        return ipaddress.ip_interface(address).ip.is_loopback
    except ValueError:
        return False


def validate_test_database_connection(
    connection: Connection, expected_database: str | None
) -> None:
    """Fail closed unless a connection reaches the expected local test database."""
    current_database, server_address = connection.execute(
        text("SELECT current_database(), inet_server_addr()::text")
    ).one()
    if not expected_database or current_database != expected_database:
        raise ValueError("Refusing database connection: unexpected database target")
    if not is_loopback_server_address(server_address):
        raise ValueError("Refusing database connection: server address is not loopback")


def validate_test_database_url(value: str) -> URL:
    """Return a safe local disposable-test URL without exposing its credentials."""
    try:
        url = make_url(value)
    except (ArgumentError, ValueError):
        raise ValueError("Refusing invalid test database URL") from None

    if TARGET_OVERRIDE_PARAMETERS.intersection(url.query):
        raise ValueError("Refusing test database URL with connection-target overrides")
    database = url.database or ""
    if url.drivername != "postgresql+psycopg":
        raise ValueError("Refusing test database: PostgreSQL/psycopg is required")
    if database.casefold() in PROTECTED_DATABASES:
        raise ValueError("Refusing protected test database")
    if not database.endswith("_test"):
        raise ValueError(
            "Refusing test database: PostgreSQL/psycopg and a name ending in _test are required"
        )
    if url.host is None or url.host.casefold() not in LOCAL_HOSTS:
        raise ValueError("Refusing non-local test database host")
    return url
