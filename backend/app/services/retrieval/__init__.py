"""Retrieval package exposing BM25, Dense, and Hybrid services."""

from app.services.retrieval.bm25_service import BM25RetrievalService, bm25_service
from app.services.retrieval.dense_service import (
    BaseEmbeddingProvider,
    BGEM3EmbeddingProvider,
    DenseRetrievalService,
    MockDenseEmbeddingProvider,
    dense_service,
)
from app.services.retrieval.hybrid_service import (
    HybridRetrievalService,
    hybrid_retrieval_service,
)

__all__ = [
    "BM25RetrievalService",
    "bm25_service",
    "BaseEmbeddingProvider",
    "BGEM3EmbeddingProvider",
    "MockDenseEmbeddingProvider",
    "DenseRetrievalService",
    "dense_service",
    "HybridRetrievalService",
    "hybrid_retrieval_service",
]
