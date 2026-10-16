"""Test infrastructure: explicit database opt-in and isolated upload storage."""
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from dotenv import dotenv_values

from tests._database_safety import configure_test_environment, database_identity, UnsafeTestDatabase


# Set safe credentials BEFORE test modules import app/settings or persistent stores.
PROJECT = Path(__file__).resolve().parents[2]
protected_urls = [os.environ.get("DATABASE_URL", "")]
protected_urls += [dotenv_values(path).get("DATABASE_URL", "") for path in (PROJECT / ".env", PROJECT / "backend/.env")]
try:
    TEST_DATABASE_URL = configure_test_environment(os.environ, protected_urls)
except UnsafeTestDatabase as exc:
    raise pytest.UsageError(str(exc)) from None


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    blocked = [item.nodeid for item in items if item.get_closest_marker("database")]
    if blocked and not TEST_DATABASE_URL and not config.option.collectonly:
        raise pytest.UsageError(
            "PostgreSQL integration tests BLOCKED: configure TEST_DATABASE_URL and "
            "CLAIMWISE_TEST_DB_CONFIRM for a verified disposable database. "
            "Use -m 'not database' for the independent tests. No integration test was executed.\n"
            + "\n".join(blocked)
        )


@pytest.fixture(scope="session")
def verified_test_database():
    if not TEST_DATABASE_URL:
        return None
    import psycopg
    expected = database_identity(TEST_DATABASE_URL)[2]
    try:
        # Read-only attestation; no schema writes or clears until all checks pass.
        with psycopg.connect(TEST_DATABASE_URL, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                database, role = cursor.fetchone()
                if database != expected or role != unquote(urlsplit(TEST_DATABASE_URL).username or ""):
                    raise UnsafeTestDatabase("The connected server does not match the disposable test database.")
                cursor.execute("SELECT purpose FROM public.claimwise_test_database_marker")
                if cursor.fetchall() != [("disposable-claimwise-tests",)]:
                    raise UnsafeTestDatabase("Missing disposable database attestation.")
                cursor.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
                if cursor.fetchone() is None:
                    raise UnsafeTestDatabase("The disposable test server needs the pgvector extension.")
    except UnsafeTestDatabase as exc:
        pytest.fail(str(exc), pytrace=False)
    except Exception:
        pytest.fail("Disposable PostgreSQL verification failed; check connectivity, TLS, role and attestation. No tests may write to it.", pytrace=False)
    return TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def database_connection_guard(monkeypatch, verified_test_database):
    """Catch unmarked persistence dependencies and late settings/DSN changes."""
    import asyncpg
    import psycopg
    from app.core.config import get_settings
    from app.db.session import DatabaseManager

    def check(url=None, kwargs=None):
        candidate = url or get_settings().database_url
        overrides = {"host", "hostaddr", "port", "dbname", "database", "user", "password", "service", "conninfo"}
        if (not verified_test_database or candidate != verified_test_database
                or overrides.intersection(kwargs or {})):
            raise UnsafeTestDatabase("Database access blocked: use a verified disposable PostgreSQL test database.")

    connect = psycopg.connect
    async_connect, create_pool = asyncpg.connect, asyncpg.create_pool
    sync_pool = DatabaseManager.get_sync_pool

    def guarded_connect(conninfo="", *args, **kwargs):
        check(conninfo, kwargs)
        return connect(conninfo, *args, **kwargs)

    async def guarded_async_connect(*args, **kwargs):
        check(kwargs.get("dsn") or (args[0] if args else None), kwargs)
        return await async_connect(*args, **kwargs)

    async def guarded_create_pool(*args, **kwargs):
        check(kwargs.get("dsn") or (args[0] if args else None), kwargs)
        return await create_pool(*args, **kwargs)

    def guarded_sync_pool(self):
        check()
        return sync_pool(self)

    monkeypatch.setattr(psycopg, "connect", guarded_connect)
    monkeypatch.setattr(asyncpg, "connect", guarded_async_connect)
    monkeypatch.setattr(asyncpg, "create_pool", guarded_create_pool)
    monkeypatch.setattr(DatabaseManager, "get_sync_pool", guarded_sync_pool)


@pytest.fixture(autouse=True)
def isolated_policy_pdf_storage(monkeypatch, tmp_path):
    from app.api.v1.endpoints import policies
    original = policies._policy_pdf_path

    def test_pdf_path(document_hash):
        # Retain the real integrity/path validation, changing only the storage root.
        validated = original(document_hash)
        return tmp_path / "policy_pdfs" / validated.name

    monkeypatch.setattr(policies, "_policy_pdf_path", test_pdf_path)


@pytest.fixture
def memory_policy_store(monkeypatch, request):
    """Explicit service-test input only; database integration tests never use this fixture."""
    from app.api.v1.endpoints import policies, coverage, qa
    from app.services import appeal_generator_service
    store = {}
    for module in (policies, coverage, qa, appeal_generator_service, request.module):
        if hasattr(module, "_dev_policy_store"):
            monkeypatch.setattr(module, "_dev_policy_store", store)
    return store


@pytest.fixture
def parsed_sample_policy_records():
    """Parse the actual fictional PDF fixtures, with explicit synthetic ownership."""
    from app.services.document_service import document_service
    records = {}
    for suffix in ("A", "B"):
        name = f"Sample_Health_Insurance_Policy_{suffix}.pdf"
        record = document_service.process_pdf((PROJECT / "test_pdfs" / name).read_bytes(), name)
        record.policy_id = f"policy_{suffix.lower()}"
        record.user_id = "dev-user-001"
        records[record.policy_id] = record
    return records


@pytest.fixture
def sample_policy_records(memory_policy_store, parsed_sample_policy_records):
    memory_policy_store.update(parsed_sample_policy_records)
    return memory_policy_store


@pytest.fixture
def persisted_sample_policy_records(verified_test_database, parsed_sample_policy_records):
    """Real persistence integrations seed owned records only after server attestation."""
    if not verified_test_database:
        pytest.fail("Persistence fixtures require the verified disposable database")
    from app.api.v1.endpoints.policies import _dev_policy_store
    for policy_id, record in parsed_sample_policy_records.items():
        _dev_policy_store[policy_id] = record
    return parsed_sample_policy_records


@pytest.fixture(autouse=True)
def isolated_retrieval_indexes(monkeypatch):
    """Do not let earlier service tests contaminate later API status/evidence results."""
    from app.services.retrieval.hybrid_service import hybrid_retrieval_service
    from app.services.retrieval.bm25_service import BM25RetrievalService
    from app.services.benchmarks.qa_benchmark_service import qa_benchmark_service
    monkeypatch.setattr(qa_benchmark_service, "_policies_hydrated", False)
    monkeypatch.setattr(hybrid_retrieval_service, "_bm25", BM25RetrievalService())
    monkeypatch.setattr(hybrid_retrieval_service, "_indexed_document_hashes", {})
    monkeypatch.setattr(hybrid_retrieval_service, "_indexed_policy_results", {})
    monkeypatch.setattr(hybrid_retrieval_service, "_source_clauses", {})
    monkeypatch.setattr(hybrid_retrieval_service._dense, "_clause_embeddings", {})
