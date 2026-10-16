"""Coverage-Gap Analysis API endpoints (F2)."""

import logging
import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from psycopg import Error as PostgresError
from psycopg_pool import PoolTimeout

from app.core.config import get_settings
from app.core.exceptions import DatabaseConnectionException
from app.core.security import AuthenticatedUser, get_current_user_optional, require_authenticated_user
from app.db.audit_repo import audit_repo
from app.db.workflow_repo import workflow_repo
from app.api.v1.endpoints.policies import SHARED_USER_IDS, _dev_policy_store
from app.schemas.audit import AuditEventCreate
from app.schemas.coverage import (
    CoverageGapAnalysisResult,
    CoverageGapReportResponse,
    CoverageScenarioRequest,
    CoverageVerdict,
    PresetScenarioItem,
)
from app.schemas.policy import ExtractedClause, PolicyExtractionResult
from app.schemas.qa import PolicyEvidenceStatus, QARequest, ChatHistoryMessage
from app.services.coverage_gap_service import CoverageAnalysisError, coverage_gap_service
from app.services.document_service import document_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service

logger = logging.getLogger("claimwise.api.coverage")

router = APIRouter(prefix="/coverage", tags=["Coverage-Gap Analysis"])


def _find_test_pdfs_dir() -> Optional[str]:
    """Locate test_pdfs directory containing sample policies."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        cand = os.path.join(cur, "test_pdfs")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def get_policy_record(policy_id: str) -> PolicyExtractionResult:
    """Retrieve policy from store or hydrate sample policies if requested."""
    clean_id = policy_id.strip()

    # 1. Direct match in active memory store
    if clean_id in _dev_policy_store:
        return _dev_policy_store[clean_id]

    # 2. Check by name or partial hash
    for p in _dev_policy_store.values():
        if p.policy_id == clean_id or p.document_name.lower() == clean_id.lower():
            return p

    # 3. Check if requesting sample policy A or B
    lower_id = clean_id.lower()
    sample_filename = None
    if "policy_a" in lower_id or lower_id in ["policy-a", "sample_a", "a"]:
        sample_filename = "Sample_Health_Insurance_Policy_A.pdf"
    elif "policy_b" in lower_id or lower_id in ["policy-b", "sample_b", "b"]:
        sample_filename = "Sample_Health_Insurance_Policy_B.pdf"

    if sample_filename:
        test_dir = _find_test_pdfs_dir()
        if test_dir:
            file_path = os.path.join(test_dir, sample_filename)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    pdf_bytes = f.read()
                record = document_service.process_pdf(pdf_bytes, filename=sample_filename)
                record.policy_id = clean_id
                _dev_policy_store[clean_id] = record
                _dev_policy_store[sample_filename] = record
                # Index into hybrid search
                if record.clauses:
                    hybrid_retrieval_service.index_policy(
                        policy_id=clean_id,
                        clauses=record.clauses,
                        document_hash=record.document_hash,
                    )
                return record

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Policy with ID '{policy_id}' not found in active session. Please upload a policy PDF first.",
    )


@router.get(
    "/presets",
    response_model=List[PresetScenarioItem],
    summary="Retrieve standard care scenario assessment templates",
)
async def get_coverage_presets() -> List[PresetScenarioItem]:
    """Return standard predefined healthcare scenarios for rapid coverage gap assessment."""
    return coverage_gap_service.get_standard_presets()


@router.post(
    "/analyze",
    response_model=CoverageGapAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a care need or medical scenario against policy language",
)
async def analyze_coverage_scenario(
    payload: CoverageScenarioRequest,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> CoverageGapAnalysisResult:
    """
    Dedicated user-need vs policy gap engine (F2).
    
    Evaluates care scenario against target policy clauses and returns grounded determination:
    - covered: Explicitly included benefit with standard cost sharing
    - conditional: Covered only if prior authorization, step therapy, or precertification conditions met
    - excluded: Explicitly barred under policy exclusions
    - uncertain: Policy language is silent or does not specify coverage terms (honest abstention)
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required on protected production routes.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = current_user.id if current_user else "dev-user-001"
    policy_record = get_policy_record(payload.policy_id)
    p_uid = getattr(policy_record, "user_id", None)
    if p_uid != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Policy '{payload.policy_id}' belongs to another account.",
        )

    from app.services.document_service import EXTRACTION_VERSION
    if isinstance(policy_record, PolicyExtractionResult) and policy_record.extraction_version < EXTRACTION_VERSION:
        from app.api.v1.endpoints.policies import _policy_pdf_path
        from app.services.policy_evidence_refresh import refresh_policy_evidence
        path = _policy_pdf_path(policy_record.document_hash)
        if path.is_file():
            policy_record = await run_in_threadpool(refresh_policy_evidence, policy_record, path.read_bytes())
            await run_in_threadpool(_dev_policy_store.__setitem__, payload.policy_id, policy_record)

    retrieval_trace = []
    if (
        policy_record.status != "success"
        or not policy_record.has_extractable_text
        or not policy_record.clauses
    ):
        result = CoverageGapAnalysisResult(
            id=f"gap-{uuid.uuid4().hex[:8]}",
            policy_id=payload.policy_id,
            category=payload.category or "General",
            situation=payload.situation,
            description=payload.description or "",
            verdict=CoverageVerdict.UNCERTAIN,
            evidence_status=PolicyEvidenceStatus.EVIDENCE_UNAVAILABLE,
            explanation="Policy evidence is unavailable because this document could not be fully extracted. Coverage cannot be determined from the available text.",
            insurer_questions=["Can you provide a text-readable copy of the complete policy or confirm this benefit directly?"],
            confidence_score=0.0,
        )
    else:
        try:
            result = await run_in_threadpool(
                coverage_gap_service.analyze_scenario,
                policy_id=payload.policy_id,
                situation=payload.situation,
                category=payload.category,
                description=payload.description,
                policy_clauses=policy_record.clauses,
                document_hash=policy_record.document_hash,
                use_live_llm=True,
                retrieval_trace=retrieval_trace,
            )
        except CoverageAnalysisError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Coverage analysis could not be verified. Your scenario is unchanged; please retry.",
            ) from None

    result.policy_name = getattr(policy_record, "document_name", None)
    user_id = current_user.id if current_user else "dev-user-001"
    valid = [
        citation for citation in result.clauses
        if citation.verified and citation.policy_id == payload.policy_id and any(
            clause.clause_id == citation.clause_id
            and clause.page_number == citation.page_number
            and citation.exact_quote.strip()
            and (
                citation.exact_quote.strip().rstrip(". ,;:") in clause.text
            )
            for clause in policy_record.clauses
        )
    ]
    if len(valid) != len(result.clauses):
        result.clauses = valid
        result.verdict = CoverageVerdict.UNCERTAIN
        result.evidence_status = PolicyEvidenceStatus.NOT_SPECIFIED
        result.explanation = "Some generated citations could not be verified against the uploaded policy. Coverage remains uncertain; review the verified evidence with your insurer."
        result.confidence_score = 0.0

    # A successful response always identifies a durable analysis. Keep the
    # synchronous database driver off the request event loop.
    try:
        await run_in_threadpool(workflow_repo.save, result, user_id)
    except (PostgresError, PoolTimeout) as exc:
        logger.exception("Could not save coverage analysis %s", result.id)
        raise DatabaseConnectionException(
            "We could not save your coverage analysis right now. Please retry; your incident text is still available."
        ) from exc

    # Supplemental audit storage must not turn an already-saved evaluation into
    # a generic 500 and prevent the member from opening their findings.
    try:
        try:
            from app.services.pii_service import pii_service
            masked_sit = pii_service.mask_text(payload.situation[:100]).masked_text
        except Exception:
            masked_sit = payload.situation[:100]

        await audit_repo.record_event(
            AuditEventCreate(
                action="coverage.analyze",
                resource_type="policy",
                resource_id=payload.policy_id,
                outcome=result.verdict.value,
                user_id=user_id,
                metadata={
                    "situation": masked_sit,
                    "category": payload.category,
                    "verdict": result.verdict.value,
                    "evidence_status": result.evidence_status.value,
                    "prior_auth_required": result.prior_auth_required,
                    "citations_count": len(result.clauses),
                    "clauses": [
                        {
                            "clause_id": c.clause_id,
                            "heading": c.clause_heading,
                            "page_number": c.page_number,
                        }
                        for c in (result.clauses or [])[:5]
                    ],
                    "validation_check": f"Prior authorization: {'Required' if result.prior_auth_required else 'Not Required'}; Evidence: {result.evidence_status.value}",
                    "retrieval": retrieval_trace,
                },
            )
        )
    except Exception:
        logger.exception("Could not record audit event for saved coverage analysis %s", result.id)

    return result


@router.get(
    "/report/{policy_id}",
    response_model=CoverageGapReportResponse,
    summary="Generate full multi-scenario coverage gap audit report for policy",
)
async def get_policy_coverage_report(
    policy_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> CoverageGapReportResponse:
    """
    Generate a policy-specific report from explicit benefit and exclusion clauses
    in the uploaded document. Computes coverage metrics and categorizes findings.
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required on protected production routes.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    policy_record = get_policy_record(policy_id)
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if policy_record.user_id not in SHARED_USER_IDS and policy_record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Policy belongs to another account.")

    report = coverage_gap_service.generate_policy_coverage_report(
        policy_id=policy_id,
        policy_name=policy_record.document_name,
        policy_clauses=policy_record.clauses,
        document_hash=policy_record.document_hash,
        use_live_llm=False,
    )

    user_id = current_user.id if current_user else "dev-user-001"
    await audit_repo.record_event(
        AuditEventCreate(
            action="coverage.report",
            resource_type="policy",
            resource_id=policy_id,
            outcome="completed",
            user_id=user_id,
            metadata={
                "total_scenarios": report.total_scenarios_evaluated,
                "covered_count": report.covered_count,
                "conditional_count": report.conditional_count,
                "excluded_count": report.excluded_count,
                "uncertain_count": report.uncertain_count,
                "coverage_score_pct": report.coverage_score_pct,
            },
        )
    )

    return report


@router.get("/analyses", response_model=List[CoverageGapAnalysisResult])
async def list_analyses(policy_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    return workflow_repo.list(current_user.id, policy_id)


def owned_analysis(analysis_id: str, user_id: str):
    record = workflow_repo.get(analysis_id, user_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return record


@router.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    return owned_analysis(analysis_id, current_user.id)



class AnalysisQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


@router.post("/analyses/{analysis_id}/ask")
async def ask_analysis(analysis_id: str, payload: AnalysisQuestion, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    from app.api.v1.endpoints.qa import ask_policy_question
    record = owned_analysis(analysis_id, current_user.id)
    analysis = record["analysis"]
    context = ChatHistoryMessage(role="user", content="Incident context (user supplied, not policy evidence): " + analysis["situation"] + " " + analysis["description"])
    assessment = ChatHistoryMessage(role="assistant", content=(
        "Prior coverage assessment, not an insurer decision: " + analysis["verdict"] + ". " + analysis["explanation"]
        + " Conditions: " + (analysis.get("conditions_summary") or "Not established")
        + " Cost sharing and limits: " + (analysis.get("cost_sharing_summary") or "Not established")
        + " Questions to confirm: " + "; ".join(analysis.get("insurer_questions", []))
        + " Recheck policy evidence before answering; do not treat prior conclusions as independent policy proof."
    ))
    history = [context, assessment] + [ChatHistoryMessage(role=m["sender"], content=m["text"]) for m in record["messages"][-6:]]
    result = await ask_policy_question(QARequest(question=payload.question, policy_id=analysis["policy_id"], history=history), current_user)
    workflow_repo.append(analysis_id, current_user.id, [
        {"sender": "user", "text": payload.question},
        {"sender": "assistant", "text": result.answer, "qaResponse": result.model_dump(mode="json")},
    ])
    return result
