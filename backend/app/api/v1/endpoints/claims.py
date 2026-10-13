"""Claim Intake, Evidence-Based Adjudication, PDF Export, and Mock Sandbox Gateway Endpoints."""

from datetime import date, datetime, timezone
import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.core.config import get_settings
from app.core.security import AuthenticatedUser, get_current_user_optional
from app.db.audit_repo import audit_repo
from app.db.claim_repo import claim_repo
from app.models.domain import ClaimStatus
from app.schemas.audit import AuditEventCreate
from app.schemas.claim import (
    BillExtractionResult,
    ClaimAdjudicateRequest,
    ClaimCreateFromBillRequest,
    ClaimRecord,
    ExplanationOfBenefits,
    SandboxOutcomeStatus,
    SandboxPayerOutcome,
    SandboxSubmitRequest,
)
from app.schemas.appeal import (
    AppealDraftCreateRequest,
    AppealDraftUpdateRequest,
    AppealExportPackage,
    ClaimAppealDraft,
)
from app.services.appeal_generator_service import appeal_generator_service
from app.services.bill_parser_service import bill_parser_service
from app.services.claim_adjudication_service import claim_adjudication_service
from app.services.document_service import DocumentProcessingError
from app.services.pdf_export_service import pdf_export_service
from app.services.sandbox_service import sandbox_service

logger = logging.getLogger("claimwise.api.claims")

router = APIRouter(prefix="/claims", tags=["Claims & Adjudication"])


def _check_claim_access(claim: ClaimRecord, current_user: Optional[AuthenticatedUser]) -> None:
    """Enforce server-side ownership check and tenant isolation on claim operations."""
    settings = get_settings()
    if settings.environment.lower() == "production":
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required on protected production routes.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if claim.user_id and claim.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Claim '{claim.id}' belongs to another user.",
            )
    else:
        # In development preview mode, enforce isolation if a specific non-dev authenticated user is supplied
        if current_user and current_user.id != "dev-user-001" and claim.user_id and claim.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Claim '{claim.id}' belongs to another user.",
            )


@router.post(
    "/upload-bill",
    response_model=BillExtractionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload medical bill PDF and extract line items for review",
)
async def upload_medical_bill(
    file: UploadFile = File(..., description="Medical bill or provider invoice PDF"),
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> BillExtractionResult:
    """
    Ingest a medical bill PDF, extract itemized charges, CPT codes, dates, and page numbers.
    Treats extracted items as unverified until reviewed by the user.
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production mode.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    filename = file.filename or "medical_bill.pdf"

    # 1. Extension validation
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension for '{filename}'. Only PDF documents (.pdf) are accepted.",
        )

    # 2. MIME type inspection
    content_type = (file.content_type or "").lower()
    allowed_mimes = [m.lower() for m in settings.allowed_upload_mime_types] + [
        "application/x-pdf",
        "application/octet-stream",
    ]
    if content_type and content_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid Content-Type '{content_type}'. Must be 'application/pdf'.",
        )

    # 3. Streamed byte-limited read
    max_bytes = settings.max_upload_size_bytes
    byte_buffer = bytearray()
    chunk_size = 512 * 1024

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            byte_buffer.extend(chunk)
            if len(byte_buffer) > max_bytes:
                max_mb = max_bytes // (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File exceeds maximum allowed upload size limit of {max_mb} MB.",
                )
    finally:
        await file.close()

    file_bytes = bytes(byte_buffer)

    # 4. Empty document validation
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes). Please upload a valid non-empty medical bill PDF.",
        )

    # 5. Magic byte verification (%PDF)
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invalid file signature. File header does not match PDF format (%PDF). Untrusted file format rejected.",
        )

    # 6. Parse bill line items
    try:
        bill_result = bill_parser_service.parse_bill_pdf(
            file_bytes=file_bytes,
            filename=filename,
        )
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if exc.status_code == "empty" else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )

    # Store parsed bill in session repository
    claim_repo.save_bill_extraction(bill_result)

    # Record audit trail
    user_id = current_user.id if current_user else "dev-user-001"
    await audit_repo.record_event(
        AuditEventCreate(
            action="claim.upload_bill",
            resource_type="medical_bill",
            resource_id=bill_result.bill_id,
            outcome="success",
            user_id=user_id,
            metadata={
                "filename": filename,
                "document_hash": bill_result.document_hash,
                "item_count": len(bill_result.line_items),
                "total_billed_cents": bill_result.total_billed_cents,
            },
        )
    )

    return bill_result


@router.post(
    "",
    response_model=ClaimRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new claim from reviewed medical bill line items",
)
async def create_claim_from_bill(
    payload: ClaimCreateFromBillRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ClaimRecord:
    """
    Construct a verified claim record from reviewed and edited medical bill line items.
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production mode.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = current_user.id if current_user else "dev-user-001"
    claim_id = str(uuid.uuid4())

    bill = claim_repo.get_bill_extraction(payload.bill_id)
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsed bill with ID '{payload.bill_id}' not found in active session.",
        )

    line_items = payload.line_items if payload.line_items is not None else bill.line_items
    total_billed = sum(item.billed_charge_cents for item in line_items)

    claim = ClaimRecord(
        id=claim_id,
        user_id=user_id,
        policy_id=payload.policy_id,
        claim_reference=payload.claim_reference or f"CLM-{uuid.uuid4().hex[:6].upper()}",
        bill_id=bill.bill_id,
        bill_document_name=bill.document_name,
        bill_document_hash=bill.document_hash,
        incident_date=date.today(),
        total_billed_cents=total_billed,
        status=ClaimStatus.DRAFT,
        line_items=line_items,
        adjudicated_items=[],
        eob=None,
        sandbox_submission=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    await claim_repo.save_claim(claim)

    await audit_repo.record_event(
        AuditEventCreate(
            action="claim.create",
            resource_type="claim",
            resource_id=claim.id,
            outcome="success",
            user_id=user_id,
            metadata={
                "claim_reference": claim.claim_reference,
                "total_billed_cents": total_billed,
                "line_item_count": len(line_items),
            },
        )
    )

    return claim


@router.get(
    "",
    response_model=List[ClaimRecord],
    summary="List claims in the current authorized session",
)
async def list_claims(
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> List[ClaimRecord]:
    """List claims available in the active session for the authenticated user."""
    settings = get_settings()
    if settings.environment.lower() == "production":
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required in production mode.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return claim_repo.list_claims(user_id=current_user.id)

    if current_user and current_user.id != "dev-user-001":
        return claim_repo.list_claims(user_id=current_user.id)
    return claim_repo.list_claims(user_id=None)


@router.get(
    "/{claim_id}",
    response_model=ClaimRecord,
    summary="Retrieve claim details by ID",
)
async def get_claim_by_id(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ClaimRecord:
    """Retrieve full claim record by identifier."""
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)
    return claim


@router.post(
    "/{claim_id}/adjudicate",
    response_model=ExplanationOfBenefits,
    summary="Run evidence-based adjudication against policy clauses and generate EOB",
)
async def adjudicate_claim(
    claim_id: str,
    payload: Optional[ClaimAdjudicateRequest] = None,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ExplanationOfBenefits:
    """
    Evaluate all claim line items against the policy's retrieved clauses,
    calculate illustrative cost shares using pure-Python integer-cents arithmetic,
    and return an itemized, mathematically reconciled EOB.
    """
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    # Resolve financial parameters
    coins_pct = payload.member_coinsurance_percentage if payload else 20.0
    deductible_cents = payload.initial_remaining_deductible_cents if payload and payload.initial_remaining_deductible_cents is not None else 100000
    oop_max_cents = payload.initial_remaining_oop_max_cents if payload and payload.initial_remaining_oop_max_cents is not None else 400000

    eob = claim_adjudication_service.adjudicate_claim(
        claim_id=claim.id,
        policy_id=claim.policy_id,
        policy_name="Master Policy Schedule",
        bill_document_hash=claim.bill_document_hash,
        policy_document_hash=None,
        line_items=claim.line_items,
        member_coinsurance_percentage=coins_pct,
        initial_remaining_deductible_cents=deductible_cents,
        initial_remaining_oop_max_cents=oop_max_cents,
    )

    # Update claim state
    claim.status = ClaimStatus.ANALYZED
    claim.adjudicated_items = eob.items
    claim.eob = eob
    claim.updated_at = datetime.now(timezone.utc)

    await claim_repo.save_claim(claim)

    # Audit logging
    user_id = current_user.id if current_user else claim.user_id
    await audit_repo.record_event(
        AuditEventCreate(
            action="claim.adjudicate",
            resource_type="claim",
            resource_id=claim.id,
            outcome="success",
            user_id=user_id,
            metadata={
                "total_billed_cents": eob.total_billed_cents,
                "member_responsibility_cents": eob.total_illustrative_member_cents,
                "illustrative_insurer_cents": eob.total_illustrative_insurer_cents,
                "adjudicated_items_count": len(eob.items),
            },
        )
    )

    return eob


@router.get(
    "/{claim_id}/eob",
    response_model=ExplanationOfBenefits,
    summary="Retrieve structured Explanation of Benefits (EOB)",
)
async def get_claim_eob(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ExplanationOfBenefits:
    """Retrieve structured EOB for an adjudicated claim."""
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    if not claim.eob:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Claim has not been adjudicated yet. Please run POST /api/v1/claims/{claim_id}/adjudicate first.",
        )

    return claim.eob


@router.get(
    "/{claim_id}/eob/pdf",
    summary="Export formal Explanation of Benefits (EOB) statement as styled PDF",
)
async def export_claim_eob_pdf(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> Response:
    """
    Generate and stream an Explanation of Benefits (EOB) PDF statement.
    Enforces authorization, mathematical integrity, and streaming download headers.
    """
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    if not claim.eob:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Claim must be adjudicated before generating EOB PDF statement.",
        )

    pdf_bytes = pdf_export_service.generate_eob_pdf(claim=claim, eob=claim.eob)

    user_id = current_user.id if current_user else claim.user_id
    await audit_repo.record_event(
        AuditEventCreate(
            action="eob.export_pdf",
            resource_type="eob",
            resource_id=claim.id,
            outcome="success",
            user_id=user_id,
            metadata={
                "claim_reference": claim.claim_reference,
                "pdf_size_bytes": len(pdf_bytes),
            },
        )
    )

    filename = f"ClaimWise_EOB_{claim.claim_reference or claim.id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


@router.post(
    "/{claim_id}/sandbox-submit",
    response_model=SandboxPayerOutcome,
    summary="Simulate submission to local mock payer sandbox with explicit confirmation",
)
async def submit_claim_to_sandbox(
    claim_id: str,
    payload: SandboxSubmitRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> SandboxPayerOutcome:
    """
    Simulate electronic claim submission to the local mock payer sandbox.
    Requires mandatory user confirmation to guarantee no live transmissions occur.
    """
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    # State validation: must be analyzed before submitting
    if claim.status not in (ClaimStatus.ANALYZED, ClaimStatus.SANDBOX_SUBMITTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Claim must be in 'analyzed' status before sandbox submission (current status: '{claim.status.value}'). Run /adjudicate first.",
        )

    try:
        outcome = sandbox_service.simulate_submission(claim=claim, request=payload)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))

    # Update claim state
    claim.status = ClaimStatus.SANDBOX_SUBMITTED
    claim.sandbox_submission = outcome.model_dump()
    claim.updated_at = datetime.now(timezone.utc)

    await claim_repo.save_claim(claim)

    user_id = current_user.id if current_user else claim.user_id
    await audit_repo.record_event(
        AuditEventCreate(
            action="sandbox.submit",
            resource_type="claim",
            resource_id=claim.id,
            outcome=outcome.outcome_status.value,
            user_id=user_id,
            metadata={
                "scenario": str(payload.requested_scenario) if payload.requested_scenario else "default",
                "submission_id": outcome.submission_id,
                "remittance_code": outcome.simulated_remittance_code,
            },
        )
    )

    return outcome


@router.get(
    "/{claim_id}/sandbox-status",
    response_model=SandboxPayerOutcome,
    summary="Retrieve mock sandbox payer outcome",
)
async def get_sandbox_status(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> SandboxPayerOutcome:
    """Retrieve simulated outcome from mock payer gateway."""
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    if not claim.sandbox_submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim '{claim_id}' has not been submitted to the mock sandbox yet.",
        )

    return SandboxPayerOutcome(**claim.sandbox_submission)


# ==============================================================================
# EVIDENCE-BASED DENIAL APPEAL ENDPOINTS
# ==============================================================================

@router.post(
    "/{claim_id}/appeal-draft",
    response_model=ClaimAppealDraft,
    status_code=status.HTTP_201_CREATED,
    summary="Generate evidence-grounded denial appeal draft for a claim",
)
async def generate_claim_appeal_draft(
    claim_id: str,
    payload: Optional[AppealDraftCreateRequest] = None,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ClaimAppealDraft:
    """
    Generate a structured, evidence-grounded appeal draft for a denied or simulated-denied claim.
    """
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    draft = appeal_generator_service.generate_appeal_draft(claim=claim, request=payload)
    claim_repo.save_appeal_draft(draft)

    user_id = current_user.id if current_user else claim.user_id
    await audit_repo.record_event(
        AuditEventCreate(
            action="appeal.generate",
            resource_type="appeal",
            resource_id=draft.draft_id,
            outcome="success",
            user_id=user_id,
            metadata={
                "claim_id": claim.id,
                "denial_reason": draft.denial_reason_code,
                "citation_count": len(draft.policy_clauses_cited),
            },
        )
    )

    return draft


@router.get(
    "/{claim_id}/appeal-draft",
    response_model=ClaimAppealDraft,
    summary="Retrieve active appeal draft for a claim",
)
async def get_claim_appeal_draft(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ClaimAppealDraft:
    """Retrieve existing appeal draft or generate on demand if claim exists."""
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    draft = claim_repo.get_appeal_draft(claim_id)
    if not draft:
        draft = appeal_generator_service.generate_appeal_draft(claim=claim)
        claim_repo.save_appeal_draft(draft)

    return draft


@router.put(
    "/{claim_id}/appeal-draft",
    response_model=ClaimAppealDraft,
    summary="Update appeal draft with human user edits",
)
async def update_claim_appeal_draft(
    claim_id: str,
    payload: AppealDraftUpdateRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ClaimAppealDraft:
    """
    Apply user modifications to an appeal draft. Sets draft status to 'user_edited'.
    """
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    draft = claim_repo.get_appeal_draft(claim_id)
    if not draft:
        draft = appeal_generator_service.generate_appeal_draft(claim=claim)

    updated_draft = appeal_generator_service.update_appeal_draft(draft, payload)
    claim_repo.save_appeal_draft(updated_draft)

    user_id = current_user.id if current_user else claim.user_id
    await audit_repo.record_event(
        AuditEventCreate(
            action="appeal.edit",
            resource_type="appeal",
            resource_id=updated_draft.draft_id,
            outcome="success",
            user_id=user_id,
            metadata={
                "claim_id": claim.id,
                "new_status": updated_draft.status.value,
            },
        )
    )

    return updated_draft


@router.post(
    "/{claim_id}/appeal-draft/export",
    response_model=AppealExportPackage,
    summary="Finalize and export reviewed appeal package for offline member filing",
)
async def export_claim_appeal_package(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> AppealExportPackage:
    """
    Finalize and export reviewed appeal package (Markdown).
    """
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    draft = claim_repo.get_appeal_draft(claim_id)
    if not draft:
        draft = appeal_generator_service.generate_appeal_draft(claim=claim)

    export_pkg = appeal_generator_service.export_appeal_package(draft)
    claim_repo.save_appeal_draft(draft)
    return export_pkg


@router.get(
    "/{claim_id}/appeal-draft/pdf",
    summary="Export formal reviewed appeal package as styled PDF",
)
async def export_claim_appeal_pdf(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> Response:
    """
    Generate and stream a formal denial appeal package PDF.
    Enforces user-reviewed state: draft must be reviewed by the user before PDF export.
    """
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    draft = claim_repo.get_appeal_draft(claim_id)
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No appeal draft found for claim '{claim_id}'. Generate draft first.",
        )

    try:
        pdf_bytes = pdf_export_service.generate_appeal_pdf(draft)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )

    user_id = current_user.id if current_user else claim.user_id
    await audit_repo.record_event(
        AuditEventCreate(
            action="appeal.export_pdf",
            resource_type="appeal",
            resource_id=draft.draft_id,
            outcome="success",
            user_id=user_id,
            metadata={
                "claim_id": claim.id,
                "pdf_size_bytes": len(pdf_bytes),
                "status": draft.status.value,
            },
        )
    )

    filename = f"ClaimWise_Appeal_{claim.claim_reference or claim.id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )
