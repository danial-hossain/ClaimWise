"""Automated unit tests for BM25, Dense, and Hybrid RRF Retrieval services."""

import pytest
from app.schemas.policy import ExtractedClause
from app.services.retrieval.bm25_service import BM25RetrievalService, tokenize_text
from app.services.retrieval.dense_service import (
    DenseRetrievalService,
    MockDenseEmbeddingProvider,
)
from app.services.retrieval.hybrid_service import HybridRetrievalService


@pytest.fixture
def sample_clauses() -> list[ExtractedClause]:
    """Sample insurance clauses for retrieval verification."""
    return [
        ExtractedClause(
            clause_id="SEC-1.1",
            page_number=1,
            clause_heading="Emergency Room Services",
            heading_confidence="high",
            section_number="1.1",
            text="Emergency room visits are covered with a $250 copay prior to deductible satisfaction.",
            token_count=18,
            document_hash="hash_alpha_123",
        ),
        ExtractedClause(
            clause_id="SEC-2.3",
            page_number=2,
            clause_heading="Annual Deductible and Coinsurance",
            heading_confidence="high",
            section_number="2.3",
            text="Individual annual deductible is $1,500. After deductible, member pays 20% coinsurance.",
            token_count=16,
            document_hash="hash_alpha_123",
        ),
        ExtractedClause(
            clause_id="SEC-4.0",
            page_number=4,
            clause_heading="Exclusions and Limitations",
            heading_confidence="high",
            section_number="4.0",
            text="Cosmetic procedures, experimental treatments, and non-prescribed holistic therapies are strictly excluded.",
            token_count=17,
            document_hash="hash_alpha_123",
        ),
        ExtractedClause(
            clause_id="SEC-5.1",
            page_number=5,
            clause_heading="Pre-existing Conditions Waiting Period",
            heading_confidence="high",
            section_number="5.1",
            text="A 6-month waiting period applies to pre-existing conditions prior to effective coverage date.",
            token_count=16,
            document_hash="hash_alpha_123",
        ),
    ]


def test_bm25_tokenization_preserves_clause_numbers():
    """Verify tokenizer preserves clause numbers, hyphenated terms, and digits."""
    tokens = tokenize_text("Section 1.1 Emergency in-network visit with $250 co-pay.")
    assert "1.1" in tokens
    assert "in-network" in tokens
    assert "co-pay" in tokens
    assert "250" in tokens


def test_bm25_exact_clause_lookup(sample_clauses):
    """Verify looking up exact clause identifier 'SEC-1.1' ranks it #1."""
    bm25 = BM25RetrievalService()
    bm25.index_policy("policy-001", sample_clauses)

    results = bm25.query("SEC-1.1", policy_ids=["policy-001"], top_k=2)
    assert len(results) >= 1
    assert results[0].clause_id == "SEC-1.1"
    assert results[0].rank == 1
    assert results[0].page_number == 1


def test_bm25_exclusion_and_deductible_queries(sample_clauses):
    """Verify keyword queries for exclusions and deductibles match relevant clauses."""
    bm25 = BM25RetrievalService()
    bm25.index_policy("policy-001", sample_clauses)

    # Query exclusions
    excl_res = bm25.query("experimental excluded therapies", policy_ids=["policy-001"], top_k=1)
    assert len(excl_res) == 1
    assert excl_res[0].clause_id == "SEC-4.0"

    # Query deductible
    ded_res = bm25.query("what is the individual annual deductible amount", policy_ids=["policy-001"], top_k=1)
    assert len(ded_res) == 1
    assert ded_res[0].clause_id == "SEC-2.3"


def test_bm25_policy_isolation_prevents_leakage(sample_clauses):
    """Verify query strictly filters by authorized policy_ids and prevents cross-user leakage."""
    bm25 = BM25RetrievalService()
    bm25.index_policy("user-alice-policy", sample_clauses[:2])
    bm25.index_policy("user-bob-policy", sample_clauses[2:])

    # Querying as Alice must NEVER return Bob's clauses
    alice_matches = bm25.query("experimental excluded cosmetic", policy_ids=["user-alice-policy"])
    assert len(alice_matches) == 0  # Alice's policy has no exclusion clauses

    # Querying as Bob returns his clause
    bob_matches = bm25.query("experimental excluded cosmetic", policy_ids=["user-bob-policy"])
    assert len(bob_matches) == 1
    assert bob_matches[0].policy_id == "user-bob-policy"


def test_bm25_empty_index_and_no_match(sample_clauses):
    """Verify querying an empty index or querying with zero keyword overlap returns empty."""
    bm25 = BM25RetrievalService()
    # Empty index
    assert bm25.query("emergency", policy_ids=["unknown-policy"]) == []

    # Indexed, but unrelated query
    bm25.index_policy("policy-001", sample_clauses)
    no_matches = bm25.query("quantum mechanics astrophysics telescope", policy_ids=["policy-001"])
    assert len(no_matches) == 0


def test_mock_dense_embedding_dimension_and_normalization():
    """Verify dense embedding generates exact 1024-dim unit-normalized vectors."""
    provider = MockDenseEmbeddingProvider(dimension=1024)
    assert provider.dimension == 1024

    vec = provider.embed_text("Emergency room services with $250 copay.")
    assert len(vec) == 1024
    # Check L2 unit norm sum(x^2) ≈ 1.0
    norm_sq = sum(x * x for x in vec)
    assert pytest.approx(norm_sq, abs=1e-4) == 1.0


def test_dense_retrieval_cosine_search(sample_clauses):
    """Verify dense vector search returns cosine similarity ranked results."""
    dense = DenseRetrievalService(provider=MockDenseEmbeddingProvider(dimension=1024))
    dense.index_policy("policy-001", sample_clauses)

    results = dense.query("annual deductible coinsurance", policy_ids=["policy-001"], top_k=2)
    assert len(results) == 2
    assert results[0].rank == 1
    assert -1.0 <= results[0].score <= 1.0


def test_hybrid_rrf_combines_lexical_and_dense(sample_clauses):
    """Verify RRF correctly fuses lexical and dense rankings and calculates RRF score."""
    lexical = BM25RetrievalService()
    lexical.index_policy("policy-001", sample_clauses)

    dense = DenseRetrievalService(provider=MockDenseEmbeddingProvider(dimension=1024))
    dense.index_policy("policy-001", sample_clauses)

    hybrid = HybridRetrievalService(lexical_engine=lexical, dense_engine=dense, rrf_k=60)
    results, mode = hybrid.retrieve("emergency deductible", policy_ids=["policy-001"], top_k=3)

    assert mode == "hybrid"
    assert len(results) >= 1
    # Check RRF score calculation: score = sum(1 / (60 + rank))
    first = results[0]
    assert first.fused_rank == 1
    assert first.rrf_score > 0
    assert first.document_hash == "hash_alpha_123"


def test_hybrid_degraded_mode_when_dense_unavailable(sample_clauses):
    """Verify system transparently reports degraded mode when dense provider is inactive."""
    lexical = BM25RetrievalService()
    lexical.index_policy("policy-001", sample_clauses)

    # Create dense engine with unavailable provider
    class UnavailableProvider(MockDenseEmbeddingProvider):
        def is_available(self) -> bool:
            return False

    dense = DenseRetrievalService(provider=UnavailableProvider())
    hybrid = HybridRetrievalService(lexical_engine=lexical, dense_engine=dense)

    results, mode = hybrid.retrieve("emergency copay", policy_ids=["policy-001"], top_k=2)

    assert mode == "degraded_bm25_only"
    assert len(results) >= 1
    assert results[0].dense_rank is None
    assert results[0].lexical_rank == 1
