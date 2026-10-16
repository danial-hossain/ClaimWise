"""The test runner must never select the working application database implicitly."""
import pytest

from tests._database_safety import (
    UnsafeTestDatabase, configure_test_environment, validate_test_database,
)

URL = "postgresql://claimwise_test_runner:synthetic@localhost/claimwise_test_suite"
NAME = "claimwise_test_suite"


@pytest.mark.parametrize("suffix", [
    "?host=other", "?dbname=production", "?user=admin", "?service=production",
    "?port=5433", "?password=override", "?hostaddr=192.0.2.1",
])
def test_rejects_connection_target_overrides(suffix):
    with pytest.raises(UnsafeTestDatabase):
        validate_test_database(URL + suffix, NAME)


@pytest.mark.parametrize("url,confirmation", [
    (URL, ""), (URL, "wrong"),
    (URL.replace(NAME, "production"), "production"),
    (URL.replace("claimwise_test_runner", "application"), NAME),
    (URL.replace(":synthetic", ""), NAME),
    ("postgresql://secret:private@[invalid", NAME),
])
def test_rejects_unsafe_configuration_without_exposing_credentials(url, confirmation):
    with pytest.raises(UnsafeTestDatabase) as caught:
        validate_test_database(url, confirmation)
    assert "synthetic" not in str(caught.value)
    assert "private" not in str(caught.value)


def test_rejects_application_database_even_with_different_credentials():
    protected = "postgresql://application:private@127.0.0.1/claimwise_test_suite"
    with pytest.raises(UnsafeTestDatabase):
        validate_test_database(URL, NAME, [protected])


def test_rejects_neon_pooler_alias_of_application_database():
    target = URL.replace("localhost", "ep-example-pooler.example.test")
    protected = URL.replace("localhost", "ep-example.example.test")
    with pytest.raises(UnsafeTestDatabase):
        validate_test_database(target, NAME, [protected])


def test_valid_explicit_disposable_configuration():
    assert validate_test_database(URL + "?sslmode=require", NAME) == URL + "?sslmode=require"


def test_default_environment_cannot_inherit_application_database_or_provider_key():
    environment = {"DATABASE_URL": "production-private", "GEMINI_API_KEY": "private"}
    assert configure_test_environment(environment) is None
    assert environment["DATABASE_URL"] == "placeholder"
    assert environment["GEMINI_API_KEY"] == "placeholder"


def test_disposable_database_requires_explicit_confirmation():
    environment = {"TEST_DATABASE_URL": URL, "CLAIMWISE_TEST_DB_CONFIRM": NAME}
    assert configure_test_environment(environment) == URL
    assert environment["DATABASE_URL"] == URL


def test_offline_guard_blocks_sync_connections_before_network():
    import psycopg
    from tests import conftest
    if conftest.TEST_DATABASE_URL:
        # Exercise the actual guard with a target other than the attested database.
        target = "postgresql://application:synthetic@invalid/production"
    else:
        target = URL
    with pytest.raises(UnsafeTestDatabase):
        psycopg.connect(target)


@pytest.mark.asyncio
async def test_guard_blocks_async_connections_and_pools_before_network():
    import asyncpg
    target = "postgresql://application:synthetic@invalid/production"
    with pytest.raises(UnsafeTestDatabase):
        await asyncpg.connect(target)
    with pytest.raises(UnsafeTestDatabase):
        await asyncpg.create_pool(target)
