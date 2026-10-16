"""Follow-ups must retrieve claims conditions beyond incident headings."""
from types import SimpleNamespace

from app.api.v1.endpoints import qa
from app.schemas.policy import ExtractedClause
from app.services.retrieval.bm25_service import BM25RetrievalService
from app.services.retrieval.hybrid_service import HybridRetrievalService


def retriever(monkeypatch):
    engine = HybridRetrievalService(
        lexical_engine=BM25RetrievalService(),
        dense_engine=SimpleNamespace(is_available=lambda: False, index_policy=lambda *args: 0),
    )
    clauses = [ExtractedClause(
        clause_id=f'c{i}', page_number=1, text=text,
        document_hash='a' * 64, token_count=len(text.split()),
    ) for i, text in enumerate([
        'My luggage lost during my trip. Luggage cover.',
        'The trip includes lost luggage benefits.',
        'Luggage lost during a trip must meet the policy conditions.',
        'Provide supporting documents for your claim, including receipts and a police report.',
    ])]
    engine.index_policy('selected', clauses, 'a' * 64)
    engine.index_policy('other-account', [clauses[-1].model_copy(update={'clause_id': 'foreign'})], 'b' * 64)
    monkeypatch.setattr(qa, 'hybrid_retrieval_service', engine)
    return engine


def test_document_followup_keeps_procedure_evidence_in_selected_policy(monkeypatch):
    retriever(monkeypatch)
    rows, _ = qa._retrieve_qa_evidence(
        'What evidence do I need next?',
        ('My luggage was lost during my trip. ' * 5) + 'What evidence do I need next?',
        ['selected'],
    )
    assert any('supporting documents' in c.text for c in rows)
    assert all(c.policy_id == 'selected' for c in rows)
    assert len({(c.policy_id, c.clause_id) for c in rows}) == len(rows)


def test_explicit_limit_and_nonprocedural_queries_remain_supported(monkeypatch):
    engine = retriever(monkeypatch)
    rows, _ = qa._retrieve_qa_evidence('What evidence?', 'lost luggage', ['selected'], top_k=1)
    assert len(rows) == 1
    assert 'supporting documents' in rows[0].text
    rows, _ = qa._retrieve_qa_evidence('Is luggage covered?', 'lost luggage', ['selected'])
    expected, _ = engine.retrieve('lost luggage', ['selected'], top_k=6)
    assert [c.clause_id for c in rows] == [c.clause_id for c in expected]
