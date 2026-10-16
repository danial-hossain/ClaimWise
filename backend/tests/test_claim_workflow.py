"""Workflow contract tests; storage/AI replaced at their external boundaries."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import AuthenticatedUser, require_authenticated_user
from app.api.v1.endpoints import claims, coverage, qa
from app.models.domain import ClaimStatus
from app.schemas.claim import ClaimRecord
from app.schemas.coverage import CoverageGapAnalysisResult


@pytest.fixture
def client():
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(id="owner")
    yield TestClient(app)
    app.dependency_overrides.clear()


def analysis():
    return CoverageGapAnalysisResult(id="analysis-1", policy_id="policy-1", category="Travel", situation="Lost luggage", description="Bag lost on arrival", verdict="uncertain", explanation="Confirm with insurer.", analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc)).model_dump(mode="json")


def claim(owner="owner"):
    now = datetime.now(timezone.utc)
    return ClaimRecord(id="claim-1", user_id=owner, policy_id="policy-1", incident_date=date.today(), total_billed_cents=0, status=ClaimStatus.DRAFT, created_at=now, updated_at=now)


def test_authentication_required():
    response = TestClient(app).get('/api/v1/coverage/analyses?policy_id=p')
    assert response.status_code == 401
    assert TestClient(app).get('/api/v1/claims').status_code == 401


def test_analysis_ownership_is_passed_to_repository(client, monkeypatch):
    seen = []
    monkeypatch.setattr(coverage.workflow_repo, 'get', lambda aid, uid: seen.append((aid, uid)))
    assert client.get('/api/v1/coverage/analyses/foreign').status_code == 404
    assert seen == [('foreign', 'owner')]


def test_intake_uses_server_analysis_and_rejects_policy_mismatch(client, monkeypatch):
    monkeypatch.setattr(claims, 'get_policy_record', lambda _: SimpleNamespace(user_id='owner'))
    monkeypatch.setattr(coverage.workflow_repo, 'get', lambda *_: {'analysis': analysis(), 'messages': []})
    save = AsyncMock()
    monkeypatch.setattr(claims.claim_repo, 'save_claim', save)
    payload = dict(policy_id='policy-1', analysis_id='analysis-1', claim_type='Travel', incident_description='Bag lost on arrival', incident_date=str(date.today()))
    response = client.post('/api/v1/claims/intake', json=payload)
    assert response.status_code == 201, response.text
    assert response.json()['coverage_analysis'] == analysis()
    assert response.json()['user_id'] == 'owner'
    assert response.json()['status'] == 'draft'
    payload['policy_id'] = 'different'
    assert client.post('/api/v1/claims/intake', json=payload).status_code == 400
    assert save.await_count == 1


def test_claim_access_isolation_in_development(client, monkeypatch):
    monkeypatch.setattr(claims.claim_repo, 'get_claim', lambda _: claim('someone-else'))
    assert client.get('/api/v1/claims/claim-1').status_code == 403
    assert client.patch('/api/v1/claims/claim-1/intake', json={'incident_description': 'New details'}).status_code == 403


def test_checklist_update_keeps_typed_items(client, monkeypatch):
    monkeypatch.setattr(claims.claim_repo, 'get_claim', lambda _: claim())
    monkeypatch.setattr(claims.claim_repo, 'save_claim', AsyncMock())
    response = client.patch('/api/v1/claims/claim-1/intake', json={'checklist': [{'id': 'receipt', 'title': 'Receipt', 'mandatory': False, 'completed': True}]})
    assert response.status_code == 200, response.text
    assert response.json()['checklist'][0]['completed'] is True
    assert client.patch('/api/v1/claims/claim-1/intake', json={'incident_date': None}).status_code == 422


def test_followup_restores_server_context_and_persists_answer(client, monkeypatch):
    from app.schemas.qa import QAResponse
    result = QAResponse(question='What evidence?', answer='Confirm the missing facts.', evidence_sufficient=False, evidence_status='not_specified', retrieval_mode='degraded_bm25_only', retrieved_evidence=[], model_used='test', latency_ms=1, created_at=datetime.now(timezone.utc))
    ask = AsyncMock(return_value=result)
    monkeypatch.setattr(qa, 'ask_policy_question', ask)
    monkeypatch.setattr(coverage.workflow_repo, 'get', lambda *_: {'analysis': analysis(), 'messages': [{'sender': 'user', 'text': 'Earlier question'}]})
    appended = []
    monkeypatch.setattr(coverage.workflow_repo, 'append', lambda *args: appended.append(args))
    response = client.post('/api/v1/coverage/analyses/analysis-1/ask', json={'question': 'What evidence?'})
    assert response.status_code == 200, response.text
    request = ask.await_args.args[0]
    assert request.policy_id == 'policy-1'
    assert 'Lost luggage' in request.history[0].content
    assert 'Prior coverage assessment' in request.history[1].content
    assert request.history[2].content == 'Earlier question'
    assert appended[0][1] == 'owner'
    assert appended[0][2][1]['qaResponse']['answer'] == result.answer


def test_claim_database_failure_is_not_reported_as_saved(monkeypatch):
    from app.db.claim_repo import claim_repo, local_store
    import asyncio
    def fail(_):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(local_store, 'save_claim', fail)
    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(claim_repo.save_claim(claim()))

@pytest.fixture
def coverage_boundary(monkeypatch):
    from app.schemas.policy import ExtractedClause
    from app.schemas.qa import VerifiedCitation
    clause = ExtractedClause(clause_id='BAG-1', page_number=2, text='Report stolen luggage to the police within 24 hours.', document_hash='policy-hash')
    policy = SimpleNamespace(user_id='owner', status='success', has_extractable_text=True, clauses=[clause], document_hash='policy-hash')
    result = CoverageGapAnalysisResult(id='saved-luggage-analysis', policy_id='policy-1', category='Insurance scenario', situation='my luggage was stolen', description='', verdict='conditional', explanation='Review the reporting requirement; approval is not guaranteed.', clauses=[VerifiedCitation(clause_id='BAG-1', page_number=2, policy_id='policy-1', exact_quote=clause.text)])
    monkeypatch.setattr(coverage, 'get_policy_record', lambda _: policy)
    monkeypatch.setattr(coverage.coverage_gap_service, 'analyze_scenario', lambda **_: result)
    return result


def test_completed_analysis_survives_supplemental_audit_failure(client, monkeypatch, coverage_boundary):
    saved = {}
    def persist(result, owner):
        saved[(result.id, owner)] = {'analysis': result.model_dump(mode='json'), 'messages': []}
    monkeypatch.setattr(coverage.workflow_repo, 'save', persist)
    monkeypatch.setattr(coverage.workflow_repo, 'get', lambda aid, owner: saved.get((aid, owner)))
    monkeypatch.setattr(coverage.audit_repo, 'record_event', AsyncMock(side_effect=RuntimeError('audit unavailable')))
    response = client.post('/api/v1/coverage/analyze', json={'policy_id': 'policy-1', 'situation': 'my luggage was stolen', 'category': 'Insurance scenario'})
    assert response.status_code == 200, response.text
    assert response.json()['verdict'] == 'conditional'
    restored = client.get('/api/v1/coverage/analyses/' + response.json()['id'])
    assert restored.status_code == 200
    assert restored.json()['analysis']['clauses'][0]['clause_id'] == 'BAG-1'


def test_failed_analysis_persistence_returns_retryable_error(client, monkeypatch, coverage_boundary):
    from psycopg import OperationalError
    def unavailable(*_):
        raise OperationalError('database disconnected')
    monkeypatch.setattr(coverage.workflow_repo, 'save', unavailable)
    audit = AsyncMock()
    monkeypatch.setattr(coverage.audit_repo, 'record_event', audit)
    response = client.post('/api/v1/coverage/analyze', json={'policy_id': 'policy-1', 'situation': 'my luggage was stolen'})
    assert response.status_code == 503, response.text
    assert response.json()['error']['code'] == 'DATABASE_UNAVAILABLE'
    assert 'retry' in response.json()['error']['message'].lower()
    assert 'database disconnected' not in response.text
    audit.assert_not_awaited()


def test_workflow_schema_initialization_is_serialized_and_retried():
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import MagicMock
    from app.db.workflow_repo import WorkflowRepository
    repo = WorkflowRepository()
    failed = MagicMock()
    failed.commit.side_effect = RuntimeError('initialization interrupted')
    with pytest.raises(RuntimeError):
        repo._table(failed)
    ready = MagicMock()
    barrier = threading.Barrier(2)
    def initialize():
        barrier.wait(timeout=5)
        repo._table(ready)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(initialize), pool.submit(initialize)
        first.result(timeout=5)
        second.result(timeout=5)
    ready.commit.assert_called_once()
    repo._table(ready)
    ready.commit.assert_called_once()


def test_unexpected_errors_have_a_safe_traceable_reference(caplog):
    import json
    import asyncio
    from starlette.requests import Request
    from app.core.exceptions import global_exception_handler
    request = Request({'type': 'http', 'method': 'POST', 'path': '/api/v1/coverage/analyze', 'query_string': b'', 'headers': []})
    response = asyncio.run(global_exception_handler(request, RuntimeError('private internal detail')))
    data = json.loads(response.body)
    assert response.status_code == 500
    assert len(data['error']['request_id']) == 12
    assert 'private internal detail' not in data['error']['message']
    assert data['error']['request_id'] in caplog.text
