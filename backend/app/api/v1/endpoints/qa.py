"""Evidence-Grounded Policy Q&A API endpoints."""

import logging
import re
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.security import AuthenticatedUser, get_current_user_optional, require_authenticated_user
from app.db.audit_repo import audit_repo
from app.api.v1.endpoints.policies import SHARED_USER_IDS, _dev_policy_store
from app.schemas.audit import AuditEventCreate
from app.schemas.qa import QARequest, QAResponse
from app.services.qa_service import qa_service
from app.services.retrieval.dense_service import dense_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service
from app.services.benchmarks.qa_benchmark_service import (
    BenchmarkExecutionReport,
    qa_benchmark_service,
)

logger = logging.getLogger("claimwise.api.qa")

router = APIRouter(prefix="/qa", tags=["Evidence-Grounded Q&A"])


def _retrieve_qa_evidence(question, search_query, policy_ids, top_k=None):
    """Keep procedural evidence discoverable when incident history dominates search."""
    limit = top_k or get_settings().retrieval_top_k
    primary, mode = hybrid_retrieval_service.retrieve(
        query=search_query, policy_ids=policy_ids, top_k=limit,
    )
    if not re.search(r"\b(?:evidence|proof|document\w*|receipt\w*|claim\s+(?:procedure|process)|filing|submit\w*|report\w*|deadline\w*)\b", question, re.I):
        return primary, mode

    # A separate query gives general claims conditions a chance to rank;
    # they need not repeat the incident's words (e.g. 'lost luggage').
    procedural, procedural_mode = hybrid_retrieval_service.retrieve(
        query="claim supporting documents receipts proof police report property irregularity report valuations",
        policy_ids=policy_ids, top_k=limit,
    )
    merged = []
    seen = set()
    # Interleave so an explicit small top_k still includes both searches.
    for i in range(max(len(primary), len(procedural))):
        for rows in (procedural, primary):
            if i >= len(rows):
                continue
            clause = rows[i]
            key = (clause.policy_id, clause.clause_id)
            if key not in seen:
                seen.add(key)
                merged.append(clause)
    budget = top_k or limit * 2
    return [c.model_copy(update={"fused_rank": i + 1}) for i, c in enumerate(merged[:budget])], (
        "hybrid" if mode == "hybrid" or procedural_mode == "hybrid" else mode
    )


def _is_platform_question(text: str) -> bool:
    t = text.lower().strip()
    return bool(re.search(
        r"\b(?:how\s+(?:does|do)\s+(?:claimwise|this\s+website|this\s+site|this\s+platform|the\s+site|the\s+website|it)\s+work|"
        r"what\s+(?:is|can|does)\s+claimwise|"
        r"how\s+to\s+use\s+(?:claimwise|this\s+website|this\s+site)|"
        r"what\s+can\s+i\s+do\s+(?:here|on\s+this\s+website|on\s+this\s+site)|"
        r"features\s+of\s+claimwise|about\s+claimwise|"
        r"what\s+is\s+this\s+(?:website|platform|app))\b",
        t,
        re.I,
    ))


def _platform_guidance_response(question: str) -> QAResponse:
    from datetime import datetime, timezone
    from app.schemas.qa import PolicyEvidenceStatus
    answer = (
        "### Welcome to ClaimWise — Evidence-First AI Insurance Assistant\n\n"
        "ClaimWise is built on the core principle: **\"Evidence first. If no proof, no answer.\"** "
        "Here is a guide to how the platform works and what you can do across each section:\n\n"
        "1. **My Policies (`/policies`)**:\n"
        "   - Upload your insurance contracts, Product Disclosure Statements (PDS), or Benefit Schedules (PDFs up to 25MB).\n"
        "   - ClaimWise deterministically extracts granular clauses, computes cryptographic SHA-256 integrity hashes, and indexes benefits and exclusions.\n\n"
        "2. **Ask ClaimWise AI (`/workspace` & Floating Widget)**:\n"
        "   - Ask questions about your policy terms or situational guidance (e.g., *“What should I do first after my luggage is stolen?”* or *“What to do in a car accident?”*).\n"
        "   - Every coverage answer cites exact Clause IDs, Page Numbers, and verbatim quotes from the policy text.\n\n"
        "3. **Coverage Gap Analysis (`/coverage`)**:\n"
        "   - Describe any real-world incident or medical situation (e.g., *“car accident while driving in Malaysia”* or *“ER visit for acute appendicitis”*).\n"
        "   - ClaimWise decomposes the scenario into categorized verdicts (**Covered**, **Conditional**, **Excluded**, **Not Specified**), outlines mandatory preconditions, suggests questions for your insurer, and offers an **Interactive Clause Clarification Assistant**.\n\n"
        "4. **Multi-Policy Comparison (`/compare`)**:\n"
        "   - Select two or more policies to view a side-by-side comparison matrix of deductibles, copays, out-of-pocket maximums, and benefit limits.\n\n"
        "5. **Medical Bill Review (`/bills`)**:\n"
        "   - Upload medical invoices or hospital bills. The OCR engine extracts CPT/HCPCS codes, charge amounts, and flags unbundled services or billing errors.\n\n"
        "6. **Claims Adjudication & Appeals (`/claims`, `/appeals`)**:\n"
        "   - Adjudicate medical claims against your specific policy rules, calculate exact patient cost-sharing, and auto-generate evidence-grounded appeal letters with policy citations.\n\n"
        "7. **Audit Ledger & Benchmarks (`/activity`)**:\n"
        "   - Every policy evaluation, question, and claim adjudication is immutably logged on a cryptographically hash-chained audit ledger. You can also run the automated 40-question benchmark."
    )
    return QAResponse(
        question=question,
        answer=answer,
        evidence_sufficient=True,
        evidence_status=PolicyEvidenceStatus.SUPPORTED,
        abstention_reason=None,
        clarification_question="Which feature would you like to explore first? You can upload a policy at /policies or evaluate a scenario at /coverage.",
        citations=[],
        retrieval_mode="platform_guidance",
        retrieved_evidence=[],
        model_used="claimwise-platform-guide",
        latency_ms=5,
        created_at=datetime.now(timezone.utc),
    )


@router.post(
    "/ask",
    response_model=QAResponse,
    status_code=status.HTTP_200_OK,
    summary="Query insurance policy with verifiable citations",
)
async def ask_policy_question(
    payload: QARequest,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> QAResponse:
    """
    Query one selected policy or the account's complete saved policy set with strict evidence grounding.
    
    Pipeline:
    1. Scope validation: Confirms each selected policy exists and is within authorized scope.
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

    question = payload.question.strip()

    if len(question) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must be at least 3 characters in length.",
        )

    if _is_platform_question(question):
        return _platform_guidance_response(question)

    requested_ids = [item.strip() for item in (payload.policy_ids or []) if item and item.strip()]
    if payload.policy_id and payload.policy_id.strip():
        requested_ids = [payload.policy_id.strip()]

    # With no explicit scope, search every policy visible to this account.
    visible_policies = {}
    for policy in _dev_policy_store.values():
        if not policy.policy_id:
            continue
        p_uid = getattr(policy, "user_id", None)
        if current_user and p_uid == current_user.id:
            visible_policies[policy.policy_id] = policy
    if not requested_ids:
        requested_ids = list(visible_policies)
    requested_ids = list(dict.fromkeys(requested_ids))
    if not requested_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No saved policies are available. Upload a policy in My Policies first.",
        )

    missing_ids = [policy_id for policy_id in requested_ids if policy_id not in _dev_policy_store]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy '{missing_ids[0]}' not found in active session.",
        )
    unauthorized_ids = [policy_id for policy_id in requested_ids if policy_id not in visible_policies]
    if unauthorized_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="One or more selected policies do not belong to this account.",
        )

    policy_records = [visible_policies[policy_id] for policy_id in requested_ids]

    # Ensure each saved policy is indexed before querying the combined corpus.
    for policy_id, policy_record in zip(requested_ids, policy_records):
        hybrid_retrieval_service.index_policy(
            policy_id=policy_id,
            clauses=policy_record.clauses,
            document_hash=policy_record.document_hash,
        )

    # Enhance search query for follow-up questions and situational guidance
    search_query = question
    if payload.history:
        prior_user_turns = [m.content for m in payload.history if m.role == "user"]
        if prior_user_turns:
            search_query = f"{prior_user_turns[0]} {prior_user_turns[-1]} {question}"

    situational_terms = []
    is_procedural = bool(re.search(r"\b(?:what\s+(?:should|to\s+do|must|do)|steps|procedure|filing|claim\s+process|submit|report|notify|deadline|documentation|receipts?|evidence|proof)\b", question, re.I))

    if re.search(r"\b(?:luggage|baggage|stolen|theft|lost)\b", question, re.I):
        if is_procedural:
            situational_terms.append("baggage property loss theft incident reporting notification carrier transport provider documentation")
        else:
            situational_terms.append("baggage personal effects luggage theft loss stolen property benefit limit")

    if re.search(r"\b(?:car|accident|driving|vehicle|rental|motor)\b", question, re.I):
        if is_procedural:
            situational_terms.append("motor vehicle collision crash rental automobile accident report notification claim process documentation overseas international")
        else:
            situational_terms.append("motor vehicle collision crash accidental loss damage indemnity own vehicle scope of cover")

    if situational_terms:
        search_query = f"{search_query} {' '.join(situational_terms)}"

    # 2. Execute Hybrid Retrieval with Reciprocal Rank Fusion
    retrieved_clauses, retrieval_mode = _retrieve_qa_evidence(
        question=question, search_query=search_query,
        policy_ids=requested_ids,
        top_k=payload.top_k,
    )

    # 3. Synthesize grounded answer with post-generation citation validation
    qa_response = qa_service.generate_grounded_answer(
        question=question,
        retrieved_clauses=retrieved_clauses,
        authorized_policy_ids=requested_ids,
        retrieval_mode=retrieval_mode,
        policy_clauses=policy_records[0].clauses if len(policy_records) == 1 else None,
        extraction_status=policy_records[0].status if len(policy_records) == 1 else None,
        has_extractable_text=policy_records[0].has_extractable_text if len(policy_records) == 1 else None,
        history=payload.history,
    )

    user_id = getattr(current_user, "id", None) or "dev-user-001"
    qa_outcome = "answered" if qa_response.evidence_sufficient else "abstained"
    await audit_repo.record_event(
        AuditEventCreate(
            action="qa.ask",
            resource_type="policy",
            resource_id=requested_ids[0] if len(requested_ids) == 1 else None,
            outcome=qa_outcome,
            user_id=user_id,
            metadata={
                "question": question[:128],
                "policy_ids": requested_ids,
                "evidence_sufficient": qa_response.evidence_sufficient,
                "evidence_status": qa_response.evidence_status.value,
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
async def get_qa_pipeline_status(current_user: AuthenticatedUser = Depends(require_authenticated_user)) -> Dict[str, Any]:
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
            "active_indexed_policies": [pid for pid in hybrid_retrieval_service._bm25.get_indexed_policy_ids()
                                        if (policy := _dev_policy_store.get(pid)) and policy.user_id == current_user.id],
        },
        "hybrid_fusion": {
            "algorithm": "Reciprocal Rank Fusion (RRF)",
            "rrf_k": settings.retrieval_rrf_k,
            "top_k": settings.retrieval_top_k,
            "mode": "hybrid" if dense_service.is_available() else "degraded_bm25_only",
        },
    }


@router.get(
    "/benchmark",
    response_model=BenchmarkExecutionReport,
    summary="Execute and retrieve 40-question systematic Q&A benchmark report",
)
async def run_or_get_qa_benchmark(
    live: bool = False,
    max_questions: Optional[int] = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> BenchmarkExecutionReport:
    """
    Execute the systematic 40-question benchmark suite (25 answerable, 15 unanswerable)
    evaluating Groundedness %, Citation Accuracy %, and Honest Abstention Rate %.

    Parameters:
    - live: If True, queries the live Google Gemini API. If False, runs in deterministic
      offline mode using verified benchmark ground truth.
    - max_questions: Optional limit for rapid subset benchmarking.
    """
    if get_settings().environment == "production":
        raise HTTPException(status_code=403, detail="Benchmarks are disabled in production. Use an isolated benchmark environment.")
    return qa_benchmark_service.run_benchmark(use_live_llm=live, max_questions=max_questions)
