"""Startup must not require PostgreSQL or embedding model warmup."""
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.local_store import (
    LazyPersistentStore, PersistentPolicyStore, PersistentBillStore,
    PersistentClaimStore, PersistentAppealDraftStore, PersistentComparisonStore,
)


@pytest.mark.parametrize(('store_type', 'method', 'records', 'key'), [
    (PersistentPolicyStore, 'list_policies', {'policy': 'saved-policy'}, 'policy'),
    (PersistentBillStore, 'list_bills', {'bill': 'saved-bill'}, 'bill'),
    (PersistentClaimStore, 'list_claims', [SimpleNamespace(id='claim')], 'claim'),
    (PersistentAppealDraftStore, 'list_appeal_drafts', {'appeal': 'saved-appeal'}, 'appeal'),
    (PersistentComparisonStore, 'list_comparisons', [SimpleNamespace(id='comparison')], 'comparison'),
])
def test_records_load_once_on_first_read(store_type, method, records, key):
    database = SimpleNamespace(**{method: MagicMock(return_value=records)})
    store = store_type(database)
    loader = getattr(database, method)
    loader.assert_not_called()
    assert key in store
    assert store.get(key) is not None
    assert list(store.values())
    assert list(store.keys()) == [key]
    assert dict(store) == store.copy()
    assert len(store) == 1
    loader.assert_called_once()


def test_failed_hydration_retries_instead_of_caching_empty_results():
    database = SimpleNamespace(list_policies=MagicMock(side_effect=[RuntimeError('offline'), {'saved': 'policy'}]))
    store = PersistentPolicyStore(database)
    with pytest.raises(RuntimeError, match='offline'):
        store.get('saved')
    assert store.get('saved') == 'policy'
    assert database.list_policies.call_count == 2


def test_first_pop_loads_before_deleting_from_database():
    database = SimpleNamespace(list_policies=MagicMock(return_value={'saved': 'policy'}), delete_policy=MagicMock())
    store = PersistentPolicyStore(database)
    assert store.pop('saved') == 'policy'
    database.delete_policy.assert_called_once_with('saved')
    assert 'saved' not in store


def test_hydration_preserves_a_newly_saved_cache_record():
    database = SimpleNamespace(list_policies=MagicMock(return_value={'saved': 'old'}))
    store = PersistentPolicyStore(database)
    dict.__setitem__(store, 'saved', 'updated')
    assert list(store.values()) == ['updated']


def test_concurrent_reads_only_hydrate_once():
    database = SimpleNamespace(list_policies=MagicMock(return_value={'saved': 'policy'}))
    store = PersistentPolicyStore(database)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _: store.get('saved'), range(8))) == ['policy'] * 8
    database.list_policies.assert_called_once()


def test_cold_import_and_lifespan_do_not_touch_database_or_embedding_index():
    script = '''
from unittest.mock import patch
with patch('psycopg.connect', side_effect=AssertionError('startup opened database')), patch('psycopg_pool.ConnectionPool', side_effect=AssertionError('startup opened pool')):
    from app.main import app
    from app.services.retrieval.hybrid_service import hybrid_retrieval_service
    from fastapi.testclient import TestClient
    with patch.object(hybrid_retrieval_service, 'index_policy', side_effect=AssertionError('startup loaded embedding index')):
        with TestClient(app) as client:
            response = client.get('/api/v1/health')
            assert response.status_code == 200, response.text
            assert response.json()['status'] == 'healthy'
print('COLD_START_HEALTHY')
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'COLD_START_HEALTHY' in result.stdout


def test_appeal_builds_its_policy_index_after_a_cold_start(monkeypatch):
    from app.services.appeal_generator_service import DenialAppealService, hybrid_retrieval_service
    policy = SimpleNamespace(clauses=[SimpleNamespace(clause_id='clause-1', text='An appeal may be requested.', page_number=1)], document_hash='hash')
    claim = SimpleNamespace(policy_id='policy-1')
    index = MagicMock()
    retrieve = MagicMock(return_value=([], 'degraded_bm25_only'))
    monkeypatch.setattr(hybrid_retrieval_service, 'index_policy', index)
    monkeypatch.setattr(hybrid_retrieval_service, 'retrieve', retrieve)
    DenialAppealService()._gather_and_verify_evidence(claim, policy, 'DENIED')
    index.assert_called_once_with('policy-1', policy.clauses, 'hash')
    retrieve.assert_called_once()
