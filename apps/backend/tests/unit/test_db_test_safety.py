from unittest.mock import MagicMock

import pytest

from db_test_safety import (
    is_loopback_server_address,
    validate_test_database_connection,
    validate_test_database_url,
)


@pytest.mark.parametrize("address", ["127.0.0.1/32", "::1/128"])
def test_accepts_loopback_server_address_with_cidr(address: str) -> None:
    assert is_loopback_server_address(address)


def test_rejects_non_loopback_server_address() -> None:
    assert not is_loopback_server_address("192.0.2.10/32")


@pytest.mark.parametrize("address", ["invalid", "127.0.0.1/999", None])
def test_rejects_invalid_server_address(address: str | None) -> None:
    assert not is_loopback_server_address(address)


@pytest.mark.parametrize("address", ["127.0.0.1/32", "::1/128"])
def test_accepts_expected_database_on_loopback_connection(address: str) -> None:
    connection = MagicMock()
    connection.execute.return_value.one.return_value = ("synthetic_test", address)

    validate_test_database_connection(connection, "synthetic_test")

    connection.execute.assert_called_once()


@pytest.mark.parametrize("address", ["192.0.2.10/32", None, "invalid"])
def test_rejects_unsafe_connected_server_address(address: str | None) -> None:
    connection = MagicMock()
    connection.execute.return_value.one.return_value = ("synthetic_test", address)

    with pytest.raises(ValueError, match="server address is not loopback"):
        validate_test_database_connection(connection, "synthetic_test")


def test_rejects_unexpected_connected_database() -> None:
    connection = MagicMock()
    connection.execute.return_value.one.return_value = ("other_test", "127.0.0.1/32")

    with pytest.raises(ValueError, match="unexpected database target"):
        validate_test_database_connection(connection, "synthetic_test")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_accepts_local_disposable_database(host: str) -> None:
    url = validate_test_database_url(
        f"postgresql+psycopg://synthetic@{host}:5432/readbuddy_merge_validation_test"
    )
    assert url.database == "readbuddy_merge_validation_test"


@pytest.mark.parametrize("database", ["readbuddy_component2_test", "readbuddy_c2_dev"])
def test_rejects_protected_database(database: str) -> None:
    with pytest.raises(ValueError, match="protected"):
        validate_test_database_url(f"postgresql+psycopg://synthetic@127.0.0.1:5432/{database}")


@pytest.mark.parametrize("host", ["database.example", "192.0.2.10"])
def test_rejects_non_local_host(host: str) -> None:
    with pytest.raises(ValueError, match="non-local"):
        validate_test_database_url(f"postgresql+psycopg://synthetic@{host}:5432/synthetic_test")


@pytest.mark.parametrize("parameter", ["host", "hostaddr", "service", "dbname"])
def test_rejects_connection_target_override(parameter: str) -> None:
    with pytest.raises(ValueError, match="connection-target overrides"):
        validate_test_database_url(
            f"postgresql+psycopg://synthetic@127.0.0.1:5432/synthetic_test?{parameter}=untrusted"
        )


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://synthetic@127.0.0.1:5432/synthetic_test",
        "postgresql+psycopg://synthetic@127.0.0.1:5432/synthetic_dev",
        "not-a-database-url",
    ],
)
def test_rejects_invalid_driver_suffix_or_url(url: str) -> None:
    with pytest.raises(ValueError, match="Refusing"):
        validate_test_database_url(url)
