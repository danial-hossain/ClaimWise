"""Fail-closed database selection for tests; never infer a test DB from DATABASE_URL."""
from collections.abc import MutableMapping
from urllib.parse import parse_qsl, unquote, urlsplit
import re


class UnsafeTestDatabase(ValueError):
    pass


def database_identity(url: str) -> tuple[str, int, str]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().replace("-pooler.", ".")
    if host in {"localhost", "::1"}:
        host = "127.0.0.1"
    return host, parsed.port or 5432, unquote(parsed.path.removeprefix("/"))


def validate_test_database(url: str, confirmation: str, protected_urls=()) -> str:
    """Require explicit disposable database/role names and exclude known application DBs."""
    try:
        parsed = urlsplit(url)
        identity = database_identity(url)
        valid = (
            parsed.scheme in {"postgres", "postgresql"}
            and bool(parsed.hostname) and bool(parsed.password)
            and re.fullmatch(r"claimwise_test_[a-z0-9_]+", identity[2])
            and re.fullmatch(r"claimwise_test_[a-z0-9_]+", unquote(parsed.username or ""))
            and confirmation == identity[2]
            and not parsed.fragment
            and all(key in {"sslmode", "sslrootcert", "connect_timeout", "channel_binding"}
                    for key, _ in parse_qsl(parsed.query))
        )
        if not valid:
            raise UnsafeTestDatabase("Invalid disposable PostgreSQL test configuration.")
        for protected in protected_urls:
            if protected and "://" in protected and database_identity(protected) == identity:
                raise UnsafeTestDatabase("Refusing to use a configured application database for tests.")
    except UnsafeTestDatabase:
        raise
    except (TypeError, ValueError):
        raise UnsafeTestDatabase("Invalid disposable PostgreSQL test configuration.") from None
    return url


def configure_test_environment(environment: MutableMapping[str, str], protected_urls=()) -> str | None:
    selected = environment.get("TEST_DATABASE_URL", "")
    if selected:
        validate_test_database(selected, environment.get("CLAIMWISE_TEST_DB_CONFIRM", ""), protected_urls)
    environment.update({
        "DATABASE_URL": selected or "placeholder",
        "GEMINI_API_KEY": "placeholder",
        "JWT_SECRET": "claimwise-isolated-test-secret-key-32-characters",
        "JWT_ISSUER": "claimwise-tests",
        "JWT_AUDIENCE": "authenticated",
        "ENVIRONMENT": "development",
        "DEBUG": "false",
    })
    return selected or None
