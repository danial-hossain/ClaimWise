"""Dense Embedding and Vector Search Service for ClaimWise.

Provides 1024-dimensional dense vector embeddings aligned with BGE-M3.
Features lazy initialization, dimension validation, L2 vector normalization,
in-memory embedding caching, and explicit operational telemetry.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import importlib.util
import logging
import math
from typing import Any, Dict, List, Optional
import numpy as np

from app.schemas.policy import ExtractedClause

logger = logging.getLogger("claimwise.retrieval.dense")


@dataclass
class DenseMatch:
    """Result of dense vector similarity search."""
    clause_id: str
    page_number: int
    policy_id: str
    document_hash: str
    clause_heading: Optional[str]
    text: str
    rank: int  # 1-based rank
    score: float  # Cosine similarity score [-1.0, 1.0]


class BaseEmbeddingProvider(ABC):
    """Abstract base provider for 1024-dimensional dense embeddings."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Target embedding vector dimension (1024 for BGE-M3)."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the embedding provider is operational in the current environment."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Diagnostic telemetry describing operational status or blocker reasons."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate normalized 1024-dimensional embedding for a single string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized 1024-dimensional embeddings for a batch of strings."""
        pass


class BGEM3EmbeddingProvider(BaseEmbeddingProvider):
    """
    Production embedding provider targeting BAAI/bge-m3 (1024 dimensions).
    
    Architecture & Guardrails:
    - Licensing: Apache-2.0
    - Model Size: ~2.2 GB weights, ~4 GB RAM minimum for inference
    - Setup: pip install torch sentence-transformers
    - Lazy loading: Never downloads or initializes model during module import
    - Strict blocker reporting: Explicitly reports missing torch/transformers without faking embeddings
    """

    def __init__(self):
        self._model = None
        self._cache: Dict[str, List[float]] = {}
        self._initialized = False
        self._check_environment()

    def _check_environment(self) -> bool:
        has_torch = importlib.util.find_spec("torch") is not None
        has_st = importlib.util.find_spec("sentence_transformers") is not None
        has_flag = importlib.util.find_spec("FlagEmbedding") is not None
        self._has_dependencies = has_torch and (has_st or has_flag)
        return self._has_dependencies

    @property
    def dimension(self) -> int:
        return 1024

    def is_available(self) -> bool:
        return self._has_dependencies

    def get_status(self) -> Dict[str, Any]:
        if not self._has_dependencies:
            return {
                "provider": "bge-m3",
                "status": "blocked",
                "available": False,
                "dimension": 1024,
                "message": (
                    "BGE-M3 dense retrieval is inactive: PyTorch (~2.5GB) and sentence-transformers "
                    "or FlagEmbedding packages are not installed in the current environment. "
                    "Dense retrieval is disabled; operating in degraded BM25 lexical mode."
                ),
                "requirements": "pip install torch sentence-transformers",
            }
        return {
            "provider": "bge-m3",
            "status": "available",
            "available": True,
            "dimension": 1024,
            "message": "BGE-M3 dense vector engine dependencies detected.",
        }

    def _ensure_model_loaded(self):
        if not self._has_dependencies:
            raise RuntimeError(
                "Cannot compute dense embeddings: PyTorch or sentence-transformers is missing. "
                "Dense retrieval is currently blocked."
            )
        if self._model is None:
            logger.info("Lazily loading BAAI/bge-m3 embedding model...")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("BAAI/bge-m3")
                self._initialized = True
            except Exception as exc:
                logger.error("Failed to load BGE-M3 model: %s", exc)
                raise RuntimeError(f"Failed to load BGE-M3 model: {exc}") from exc

    def embed_text(self, text: str) -> List[float]:
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if text_hash in self._cache:
            return self._cache[text_hash]

        self._ensure_model_loaded()
        vec = self._model.encode(text, normalize_embeddings=True)
        if len(vec) != self.dimension:
            raise ValueError(f"Expected embedding dimension {self.dimension}, got {len(vec)}")

        res = [float(x) for x in vec]
        self._cache[text_hash] = res
        return res

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        uncached_texts: List[str] = []
        uncached_indices: List[int] = []

        for idx, text in enumerate(texts):
            th = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if th in self._cache:
                results.append(self._cache[th])
            else:
                results.append([])
                uncached_texts.append(text)
                uncached_indices.append(idx)

        if uncached_texts:
            self._ensure_model_loaded()
            vecs = self._model.encode(uncached_texts, normalize_embeddings=True)
            for idx, vec in zip(uncached_indices, vecs):
                if len(vec) != self.dimension:
                    raise ValueError(f"Expected embedding dimension {self.dimension}, got {len(vec)}")
                res = [float(x) for x in vec]
                th = hashlib.sha256(texts[idx].encode("utf-8")).hexdigest()
                self._cache[th] = res
                results[idx] = res

        return results


class MockDenseEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic 1024-dimensional mock embedding provider for automated tests.
    
    Generates pseudo-dense, L2-normalized vectors derived from cryptographic SHA-256
    text hashes. Enables thorough unit testing of cosine similarity, vector caching,
    dimension checks, and RRF fusion without external network or GPU requirements.
    """

    def __init__(self, dimension: int = 1024):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def is_available(self) -> bool:
        return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": "mock-dense",
            "status": "active_test_mode",
            "available": True,
            "dimension": self._dimension,
            "message": "Deterministic mock dense embedding provider active for testing.",
        }

    def _generate_vector(self, text: str) -> List[float]:
        # Generate 1024-dim deterministic float array from hash
        raw = []
        salt = text
        for i in range(self._dimension // 16):
            h = hashlib.sha256(f"{salt}_{i}".encode("utf-8")).digest()
            # Unpack 16 float values from digest
            for b in h[:16]:
                raw.append((float(b) - 128.0) / 128.0)

        raw = raw[:self._dimension]
        # Normalize to L2 unit norm
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [x / norm for x in raw]

    def embed_text(self, text: str) -> List[float]:
        return self._generate_vector(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(t) for t in texts]


class DenseRetrievalService:
    """
    Manages vector storage and cosine similarity search over policy clauses.
    """

    def __init__(self, provider: Optional[BaseEmbeddingProvider] = None):
        self._provider = provider or BGEM3EmbeddingProvider()
        # policy_id -> List[tuple[ExtractedClause, List[float]]]
        self._clause_embeddings: Dict[str, List[tuple[ExtractedClause, List[float]]]] = {}

    def set_provider(self, provider: BaseEmbeddingProvider):
        """Switch embedding provider (e.g. for testing with MockDenseEmbeddingProvider)."""
        self._provider = provider

    @property
    def provider(self) -> BaseEmbeddingProvider:
        return self._provider

    def is_available(self) -> bool:
        return self._provider.is_available()

    def index_policy(self, policy_id: str, clauses: List[ExtractedClause]) -> int:
        """
        Embed and index clauses for dense vector search.
        """
        if not self.is_available():
            logger.info("Dense provider unavailable. Skipping vector embedding for policy %s.", policy_id)
            return 0

        texts = [f"{c.clause_heading or ''}\n{c.text}" for c in clauses]
        vectors = self._provider.embed_batch(texts)

        clause_pairs = list(zip(clauses, vectors))
        self._clause_embeddings[policy_id] = clause_pairs
        logger.info("Dense embedded %d clauses for policy %s.", len(clause_pairs), policy_id)
        return len(clause_pairs)

    def remove_policy(self, policy_id: str) -> bool:
        removed = self._clause_embeddings.pop(policy_id, None)
        return removed is not None

    def query(
        self,
        query_text: str,
        policy_ids: List[str],
        top_k: int = 10,
    ) -> List[DenseMatch]:
        """
        Perform cosine similarity search across authorized policies.
        """
        if not self.is_available():
            return []

        query_vec = np.array(self._provider.embed_text(query_text), dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm == 0:
            return []

        scored_matches: List[tuple[float, ExtractedClause, str]] = []

        for pid in policy_ids:
            pairs = self._clause_embeddings.get(pid, [])
            for clause, vec_list in pairs:
                c_vec = np.array(vec_list, dtype=np.float32)
                c_norm = np.linalg.norm(c_vec)
                if c_norm == 0:
                    continue
                # Cosine similarity
                sim = float(np.dot(query_vec, c_vec) / (q_norm * c_norm))
                scored_matches.append((sim, clause, pid))

        # Sort descending by similarity
        scored_matches.sort(key=lambda x: x[0], reverse=True)

        results: List[DenseMatch] = []
        for idx, (sim, clause, pid) in enumerate(scored_matches[:top_k]):
            results.append(
                DenseMatch(
                    clause_id=clause.clause_id,
                    page_number=clause.page_number,
                    policy_id=pid,
                    document_hash=clause.document_hash,
                    clause_heading=clause.clause_heading,
                    text=clause.text,
                    rank=idx + 1,
                    score=sim,
                )
            )

        return results


dense_service = DenseRetrievalService()
