"""Evidence-Grounded Policy Q&A API endpoints."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.security import AuthenticatedUser, get_current_user_optional
from app.db.audit_repo import audit_repo
from app.api.v1.endpoints.policies import _dev_policy_store
from app.schemas.audit import AuditEventCreate
from app.schemas.qa import QARequest, QAResponse
from app.services.qa_service import qa_service
from app.services.retrieval.dense_service import dense_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service

logger = logging.getLogger("claimwise.api.qa")

router = APIRouter(prefix="/qa", tags=["Evidence-Grounded Q&A"])


@router.post(
    "/ask",
    response_model=QAResponse,
    status_code=status.HTTP_200_OK,
    summary="Query insurance policy with verifiable citations",
)
async def ask_policy_question(
    payload: QARequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> QAResponse:
    """
    Query an insurance policy with strict evidence grounding.
    
    Pipeline:
    1. Scope validation: Confirms target policy_id exists and is within authorized scope.
    2. Hybrid Retrieval: Queries BM25 and dense vector representations fused via Reciprocal Rank Fusion (RRF).
    3. Grounded Synthesis: Gemini generates answer strictly from retrieved policy clauses.
    4. Deterministic Post-Generation Verification: Validates Clause IDs, Page Numbers, and exact verbatim quotes.
    5. Honest Abstention: Declares insufficient evidence if proof cannot be cryptographically verified.
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required on protected production routes.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    policy_id = payload.policy_id.strip()
    question = payload.question.strip()

    if len(question) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must be at least 3 characters in length.",
        )

    # 1. Verify policy exists and index is hydrated
    # In development preview mode, verify policy exists in _dev_policy_store
    policy_record = _dev_policy_store.get(policy_id)
    if not policy_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found in active session. Please upload a policy PDF first.",
        )

    # Ensure policy clauses are indexed in the hybrid retrieval engine
    if policy_record.clauses:
        hybrid_retrieval_service.index_policy(
            policy_id=policy_id,
            clauses=policy_record.clauses,
            document_hash=policy_record.document_hash,
        )

    # 2. Execute Hybrid Retrieval with Reciprocal Rank Fusion
    retrieved_clauses, retrieval_mode = hybrid_retrieval_service.retrieve(
        query=question,
        policy_ids=[policy_id],
        top_k=settings.retrieval_top_k,
    )

    # 3. Synthesize grounded answer with post-generation citation validation
    qa_response = qa_service.generate_grounded_answer(
        question=question,
        retrieved_clauses=retrieved_clauses,
        authorized_policy_ids=[policy_id],
        retrieval_mode=retrieval_mode,
    )

    user_id = current_user.id if current_user else "dev-user-001"
    qa_outcome = "answered" if qa_response.evidence_sufficient else "abstained"
    await audit_repo.record_event(
        AuditEventCreate(
            action="qa.ask",
            resource_type="policy",
            resource_id=policy_id,
            outcome=qa_outcome,
            user_id=user_id,
            metadata={
                "question": question[:128],
                "evidence_sufficient": qa_response.evidence_sufficient,
                "retrieval_mode": retrieval_mode,
                "citations_count": len(qa_response.citations),
            },
        )
    )

    return qa_response


@router.get(
    "/status",
    summary="Retrieve Q&A and retrieval pipeline operational telemetry",
)
async def get_qa_pipeline_status() -> Dict[str, Any]:
    """
    Inspect the operational readiness of the retrieval pipeline and Gemini engine.
    Never exposes API keys or sensitive secrets.
    """
    settings = get_settings()
    dense_status = dense_service.provider.get_status()

    return {
        "gemini_engine": {
            "configured": qa_service.is_configured(),
            "model_name": settings.gemini_model_name,
            "status": "ready" if qa_service.is_configured() else "unconfigured_key_missing",
        },
        "dense_embeddings": dense_status,
        "bm25_lexical": {
            "status": "operational",
            "active_indexed_policies": hybrid_retrieval_service._bm25.get_indexed_policy_ids(),
        },
        "hybrid_fusion": {
            "algorithm": "Reciprocal Rank Fusion (RRF)",
            "rrf_k": settings.retrieval_rrf_k,
            "top_k": settings.retrieval_top_k,
            "mode": "hybrid" if dense_service.is_available() else "degraded_bm25_only",
        },
    }
