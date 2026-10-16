"""AI overlap claims need authentic sources from each selected policy."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import AuthenticatedUser, require_authenticated_user
from app.api.v1.endpoints import comparisons, policies
from app.schemas.policy import ExtractedClause
from app.services.overlap_service import analyze_overlaps, qa_service


def policy(pid, owner='owner'):
    return SimpleNamespace(policy_id=pid, user_id=owner, status='success', has_extractable_text=True,
        document_name=f'{pid}.pdf', clauses=[ExtractedClause(clause_id='coverage', page_number=2,
        text='We cover emergency medical expenses during overseas travel.', document_hash='a' * 64)])


def finding():
    return {'benefit': 'Overseas emergency medical expenses', 'explanation': 'Both policies cover this risk.',
        'qualifications': 'Limits and eligibility must be confirmed.', 'citations': [
            {'policy_id': pid, 'clause_id': 'coverage', 'page_number': 2,
             'exact_quote': 'We cover emergency medical expenses during overseas travel.'} for pid in ('a', 'b')]}


def mock_ai(monkeypatch, findings):
    monkeypatch.setattr(qa_service, 'is_configured', lambda: True)
    monkeypatch.setattr(qa_service, '_call_gemini_api', lambda *args, **kwargs: json.dumps({'overlaps': findings}))


def test_real_sources_from_two_policies_are_required(monkeypatch):
    mock_ai(monkeypatch, [finding()])
    result = analyze_overlaps({'a': policy('a'), 'b': policy('b')})
    assert result.status == 'overlaps_found'
    assert {c.policy_id for c in result.overlaps[0].citations} == {'a', 'b'}
    assert all(r.complete for r in result.policies)


@pytest.mark.parametrize('invalid', ['quote', 'page', 'foreign', 'one_policy'])
def test_invalid_or_one_sided_overlap_is_not_presented(monkeypatch, invalid):
    item = finding()
    if invalid == 'quote': item['citations'][0]['exact_quote'] = 'We cover everything.'
    if invalid == 'page': item['citations'][0]['page_number'] = 99
    if invalid == 'foreign': item['citations'][0]['policy_id'] = 'other-account'
    if invalid == 'one_policy': item['citations'][0]['policy_id'] = 'b'
    mock_ai(monkeypatch, [item])
    result = analyze_overlaps({'a': policy('a'), 'b': policy('b')})
    assert result.overlaps == []
    assert result.status == 'incomplete'
    assert result.rejected_findings == 1


def test_empty_analysis_does_not_invent_fixed_benefits(monkeypatch):
    mock_ai(monkeypatch, [])
    assert analyze_overlaps({'a': policy('a'), 'b': policy('b')}).status == 'no_verified_overlaps'


def test_pdf_linebreaks_are_restored_to_verbatim_source(monkeypatch):
    documents = {'a': policy('a'), 'b': policy('b')}
    documents['a'].clauses[0].text = 'We cover emergency\nmedical expenses during overseas travel.'
    mock_ai(monkeypatch, [finding()])
    result = analyze_overlaps(documents)
    assert result.status == 'overlaps_found'
    quote = result.overlaps[0].citations[0].exact_quote
    assert '\n' in quote
    assert quote in documents['a'].clauses[0].text


def test_unconfigured_ai_does_not_return_sample_data(monkeypatch):
    monkeypatch.setattr(qa_service, 'is_configured', lambda: False)
    with pytest.raises(RuntimeError): analyze_overlaps({'a': policy('a'), 'b': policy('b')})


def test_endpoint_authentication_ownership_and_duplicates(monkeypatch):
    client = TestClient(app)
    assert client.post('/api/v1/comparisons/overlaps', json={'policy_ids': ['a', 'b']}).status_code == 401
    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(id='owner')
    monkeypatch.setattr(policies, '_dev_policy_store', {'a': policy('a'), 'b': policy('b', 'someone-else')})
    try:
        assert client.post('/api/v1/comparisons/overlaps', json={'policy_ids': ['a', 'a']}).status_code == 400
        assert client.post('/api/v1/comparisons/overlaps', json={'policy_ids': ['a', 'b']}).status_code == 403
        assert client.post('/api/v1/comparisons/overlaps', json={'policy_ids': ['a', 'missing']}).status_code == 404
        monkeypatch.setattr(policies, '_dev_policy_store', {'a': policy('a'), 'b': policy('b')})
        mock_ai(monkeypatch, [finding()])
        response = client.post('/api/v1/comparisons/overlaps', json={'policy_ids': ['a', 'b']})
        assert response.status_code == 200, response.text
        assert len(response.json()['overlaps']) == 1
    finally:
        app.dependency_overrides.clear()
