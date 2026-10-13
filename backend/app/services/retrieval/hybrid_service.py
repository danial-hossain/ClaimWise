"""Hybrid Retrieval Service combining BM25 and Dense Search with Reciprocal Rank Fusion (RRF).

Implements:
    RRF(d) = Σ 1 / (k + rank_i(d))
Deduplicates results by stable clause ID, preserves page-level evidence metadata,
and transparently reports degraded mode when dense retrieval is blocked.
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.schemas.policy import ExtractedClause
from app.schemas.qa import RetrievedClause
from app.services.retrieval.bm25_service import BM25RetrievalService, bm25_service
from app.services.retrieval.dense_service import DenseRetrievalService, dense_service

logger = logging.getLogger("claimwise.retrieval.hybrid")


class HybridRetrievalService:
    """
    Hybrid retriever fusing lexical BM25 and dense vector rankings using RRF.
    """

    def __init__(
        self,
        lexical_engine: Optional[BM25RetrievalService] = None,
        dense_engine: Optional[DenseRetrievalService] = None,
        rrf_k: Optional[int] = None,
    ):
        settings = get_settings()
        self._bm25 = lexical_engine or bm25_service
        self._dense = dense_engine or dense_service
        self._default_k = rrf_k or settings.retrieval_rrf_k

    def index_policy(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        document_hash: str = "",
    ) -> Dict[str, Any]:
        """
        Index policy clauses into both lexical and dense engines.
        """
        lexical_count = self._bm25.index_policy(policy_id, clauses, document_hash)
        dense_count = self._dense.index_policy(policy_id, clauses)

        return {
            "policy_id": policy_id,
            "lexical_clauses_indexed": lexical_count,
            "dense_clauses_indexed": dense_count,
            "dense_operational": self._dense.is_available(),
        }

    def remove_policy(self, policy_id: str) -> None:
        """Remove policy clauses from both engines."""
        self._bm25.remove_policy(policy_id)
        self._dense.remove_policy(policy_id)

    def retrieve(
        self,
        query: str,
        policy_ids: List[str],
        top_k: Optional[int] = None,
        rrf_k: Optional[int] = None,
    ) -> tuple[List[RetrievedClause], str]:
        """
        Perform hybrid retrieval with Reciprocal Rank Fusion.
        
        Returns:
            Tuple of (List[RetrievedClause], retrieval_mode)
            where retrieval_mode is 'hybrid' or 'degraded_bm25_only'.
        """
        settings = get_settings()
        k_val = rrf_k if rrf_k is not None else self._default_k
        limit = top_k if top_k is not None else settings.retrieval_top_k

        # 1. Execute BM25 lexical query
        # Retrieve candidate pool (2x limit) for fusion
        candidate_pool_size = max(limit * 3, 20)
        lexical_matches = self._bm25.query(query, policy_ids, top_k=candidate_pool_size)

        # 2. Execute Dense query (if available)
        dense_operational = self._dense.is_available()
        dense_matches = (
            self._dense.query(query, policy_ids, top_k=candidate_pool_size)
            if dense_operational
            else []
        )

        mode = "hybrid" if (dense_operational and dense_matches) else "degraded_bm25_only"

        # Map unique clause key (policy_id:clause_id) to clause info and rank scores
        # item: { 'info': clause_meta, 'lexical_rank': int|None, 'dense_rank': int|None, 'rrf_score': float }
        clause_map: Dict[str, Dict[str, Any]] = {}

        # Accumulate BM25 rankings
        for match in lexical_matches:
            key = f"{match.policy_id}:{match.clause_id}"
            if key not in clause_map:
                clause_map[key] = {
                    "clause_id": match.clause_id,
                    "page_number": match.page_number,
                    "policy_id": match.policy_id,
                    "document_hash": match.document_hash,
                    "clause_heading": match.clause_heading,
                    "text": match.text,
                    "lexical_rank": match.rank,
                    "dense_rank": None,
                    "rrf_score": 0.0,
                }
            else:
                clause_map[key]["lexical_rank"] = match.rank

            # Add RRF contribution: 1 / (k + rank)
            clause_map[key]["rrf_score"] += 1.0 / (k_val + match.rank)

        # Accumulate Dense rankings
        for match in dense_matches:
            key = f"{match.policy_id}:{match.clause_id}"
            if key not in clause_map:
                clause_map[key] = {
                    "clause_id": match.clause_id,
                    "page_number": match.page_number,
                    "policy_id": match.policy_id,
                    "document_hash": match.document_hash,
                    "clause_heading": match.clause_heading,
                    "text": match.text,
                    "lexical_rank": None,
                    "dense_rank": match.rank,
                    "rrf_score": 0.0,
                }
            else:
                clause_map[key]["dense_rank"] = match.rank

            # Add RRF contribution: 1 / (k + rank)
            clause_map[key]["rrf_score"] += 1.0 / (k_val + match.rank)

        # If no matches in either engine, return empty
        if not clause_map:
            return [], mode

        # Sort all deduplicated candidates by fused RRF score descending
        sorted_candidates = sorted(clause_map.values(), key=lambda x: x["rrf_score"], reverse=True)

        # Construct final RetrievedClause objects
        fused_results: List[RetrievedClause] = []
        for idx, item in enumerate(sorted_candidates[:limit]):
            fused_results.append(
                RetrievedClause(
                    clause_id=item["clause_id"],
                    page_number=item["page_number"],
                    policy_id=item["policy_id"],
                    document_hash=item["document_hash"],
                    clause_heading=item["clause_heading"],
                    text=item["text"],
                    lexical_rank=item["lexical_rank"],
                    dense_rank=item["dense_rank"],
                    fused_rank=idx + 1,
                    rrf_score=round(item["rrf_score"], 6),
                )
            )

        return fused_results, mode


hybrid_retrieval_service = HybridRetrievalService()
