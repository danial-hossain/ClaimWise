"""Claim Intake, Evidence-Based Adjudication, PDF Export, and Mock Sandbox Gateway Endpoints."""

from datetime import date, datetime, timezone
import logging
from typing import List, Optional
from urllib.parse import quote
import uuid

from fastapi.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.core.config import get_settings
from app.core.security import AuthenticatedUser, get_current_user_optional, require_authenticated_user
from app.db.audit_repo import audit_repo
from app.db.claim_repo import claim_repo
from app.models.domain import ClaimStatus
from app.schemas.audit import AuditEventCreate
from app.schemas.claim import (
    BillExtractionResult,
    ClaimAdjudicateRequest,
    ClaimCreateFromBillRequest,
    ClaimIntakeCreateRequest,
    ClaimIntakeUpdateRequest,
    ClaimChecklistItem,
    ClaimFileMeta,
    ClaimTimelineEvent,
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
from app.schemas.guidance import (
    IncidentCategory,
    IncidentGuidanceResult,
    IncidentQuestionnaireRequest,
    IncidentQuestionnaireSchema,
)
from app.services.appeal_generator_service import appeal_generator_service
from app.services.bill_parser_service import bill_parser_service
from app.services.claim_adjudication_service import claim_adjudication_service
from app.services.claims_guidance_service import claims_guidance_service
from app.services.document_service import DocumentProcessingError
from app.services.pdf_export_service import pdf_export_service
from app.services.sandbox_service import sandbox_service
from app.api.v1.endpoints.coverage import get_policy_record
from app.api.v1.endpoints.policies import SHARED_USER_IDS, check_policy_access

logger = logging.getLogger("claimwise.api.claims")

router = APIRouter(prefix="/claims", tags=["Claims & Adjudication"])


@router.post(
    "/intake",
    response_model=ClaimRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a saved claim draft from user-provided incident details",
)
async def create_claim_intake(
    payload: ClaimIntakeCreateRequest,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> ClaimRecord:
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    policy = get_policy_record(payload.policy_id)
    user_id = current_user.id if current_user else "dev-user-001"
    policy_user_id = getattr(policy, "user_id", None)
    if policy_user_id != current_user.id and policy_user_id not in SHARED_USER_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected policy belongs to another account.")

    analysis = None
    if payload.analysis_id:
        from app.api.v1.endpoints.coverage import owned_analysis
        analysis = owned_analysis(payload.analysis_id, user_id)["analysis"]
        if analysis["policy_id"] != payload.policy_id:
            raise HTTPException(status_code=400, detail="Analysis and claim must use the same policy.")
    now = datetime.now(timezone.utc)
    claim = ClaimRecord(
        analysis_id=payload.analysis_id,
        coverage_analysis=analysis,
        id=str(uuid.uuid4()),
        user_id=user_id,
        policy_id=payload.policy_id,
        claim_reference=payload.claim_reference or f"CLM-{uuid.uuid4().hex[:8].upper()}",
        incident_date=payload.incident_date,
        total_billed_cents=payload.estimated_loss_cents or 0,
        status=ClaimStatus.DRAFT,
        claim_type=payload.claim_type.strip(),
        incident_description=payload.incident_description.strip(),
        incident_location=payload.incident_location.strip() if payload.incident_location else None,
        estimated_loss_cents=payload.estimated_loss_cents,
        checklist=payload.checklist,
        created_at=now,
        updated_at=now,
        timeline=[ClaimTimelineEvent(
            id=str(uuid.uuid4()),
            event_type="draft_created",
            summary="Claim draft created from details provided by the user.",
            source="internal",
            created_at=now,
        )],
    )
    await claim_repo.save_claim(claim)
    return claim


@router.patch(
    "/{claim_id}/intake",
    response_model=ClaimRecord,
    summary="Update user-provided claim details and checklist progress",
)
async def update_claim_intake(
    claim_id: str,
    payload: ClaimIntakeUpdateRequest,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> ClaimRecord:
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    _check_claim_access(claim, current_user)

    updates = payload.model_dump(exclude_unset=True)
    for field in {"claim_type", "incident_description", "incident_date"}:
        if field in updates and updates[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null.")
    changed_fields = []
    for field, value in updates.items():
        if field == "checklist":
            claim.checklist = payload.checklist or []
            changed_fields.append("document checklist")
        elif field in {"incident_date", "incident_description", "incident_location", "claim_type", "estimated_loss_cents", "claim_reference", "claim_description_draft"}:
            setattr(claim, field, value.strip() if isinstance(value, str) and field != "claim_reference" else value)
            changed_fields.append(field.replace("_", " "))

    editable_statuses = {
        ClaimStatus.DRAFT,
        ClaimStatus.EVIDENCE_GATHERING,
        ClaimStatus.PREPARING_DOCUMENTS,
        ClaimStatus.READY_TO_SUBMIT,
        ClaimStatus.ANALYZED,
    }
    if claim.status in editable_statuses:
        details_complete = bool(
            claim.claim_type
            and claim.incident_description
            and claim.incident_location
            and claim.estimated_loss_cents is not None
        )
        checklist_complete = all(item.completed for item in claim.checklist)
        claim.status = (
            ClaimStatus.READY_TO_SUBMIT
            if details_complete and checklist_complete
            else ClaimStatus.PREPARING_DOCUMENTS
        )

    now = datetime.now(timezone.utc)
    claim.updated_at = now
    if changed_fields:
        claim.timeline.append(ClaimTimelineEvent(
            id=str(uuid.uuid4()),
            event_type="claim_updated",
            summary=f"Updated {', '.join(changed_fields)}.",
            source="internal",
            created_at=now,
        ))
    await claim_repo.save_claim(claim)
    return claim


@router.post(
    "/{claim_id}/documents",
    response_model=ClaimRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Upload supporting evidence to a saved claim",
)
async def upload_claim_document(
    claim_id: str,
    file: UploadFile = File(...),
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> ClaimRecord:
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    _check_claim_access(claim, current_user)

    settings = get_settings()
    max_bytes = settings.max_upload_size_bytes
    content = await file.read(max_bytes + 1)
    await file.close()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The selected file is empty.")
    if len(content) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="The file exceeds the configured upload limit.")

    file_name = (file.filename or "claim-document").replace("\\", "_").replace("/", "_")[:255]
    ext = ("." + file_name.rsplit(".", 1)[-1].lower()) if "." in file_name else ""
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported document format '{ext}'. Allowed formats: PDF, JPG, PNG, TIFF.",
        )

    signatures = {
        ".pdf": (b"%PDF",), ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
        ".tif": (b"II*\x00", b"MM\x00*"), ".tiff": (b"II*\x00", b"MM\x00*"),
    }
    mime_types = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
                  ".jpeg": "image/jpeg", ".tif": "image/tiff", ".tiff": "image/tiff"}
    expected_mime = mime_types[ext]
    is_valid_sig = content.startswith(signatures[ext]) and (file.content_type or "application/octet-stream").lower() in {expected_mime, "application/octet-stream"}
    if not is_valid_sig:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File signature verification failed: Content does not match expected document format.",
        )

    now = datetime.now(timezone.utc)
    document_id = str(uuid.uuid4())
    mime_type = expected_mime
    claim_repo.save_claim_document(document_id, claim.id, file_name, mime_type, content, now)
    claim.documents.append(ClaimFileMeta(
        id=document_id,
        file_name=file_name,
        file_size_bytes=len(content),
        mime_type=mime_type,
        uploaded_at=now,
    ))
    claim.updated_at = now
    claim.timeline.append(ClaimTimelineEvent(
        id=str(uuid.uuid4()),
        event_type="document_added",
        summary=f"Added supporting document: {file_name}.",
        source="internal",
        created_at=now,
    ))
    if claim.status == ClaimStatus.DRAFT:
        claim.status = ClaimStatus.PREPARING_DOCUMENTS
    await claim_repo.save_claim(claim)
    return claim


@router.get(
    "/{claim_id}/documents/{document_id}",
    summary="Download a supporting document attached to a claim",
)
async def download_claim_document(
    claim_id: str,
    document_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> Response:
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    _check_claim_access(claim, current_user)
    document = claim_repo.get_claim_document(claim_id, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim document not found.")
    return Response(
        content=document["content"],
        media_type=document["mime_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document['file_name'])}",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _check_claim_access(claim: ClaimRecord, current_user: Optional[AuthenticatedUser]) -> None:
    """Enforce server-side ownership check and tenant isolation on claim operations."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if claim.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: Claim belongs to another account.")


@router.post(
    "/upload-bill",
    response_model=BillExtractionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload medical bill PDF and extract line items for review",
)
async def upload_medical_bill(
    file: UploadFile = File(..., description="Medical bill or provider invoice PDF"),
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    user_id = current_user.id if current_user else "dev-user-001"
    bill_result.user_id = user_id
    claim_repo.save_bill_extraction(bill_result)

    # Record audit trail
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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

    bill_uid = getattr(bill, "user_id", None)
    if bill_uid != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Medical bill belongs to another account.",
        )

    if payload.policy_id:
        from app.api.v1.endpoints.policies import _dev_policy_store, SHARED_USER_IDS
        pol = _dev_policy_store.get(payload.policy_id)
        if not pol:
            raise HTTPException(status_code=404, detail="Selected policy not found.")
        check_policy_access(pol, current_user)

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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> List[ClaimRecord]:
    """List claims available in the active session for the authenticated user."""
    return claim_repo.list_claims(user_id=current_user.id)


@router.get(
    "/guidance/questions",
    response_model=IncidentQuestionnaireSchema,
    summary="Retrieve structured incident questionnaire schema and preset templates",
)
async def get_incident_questionnaire_schema() -> IncidentQuestionnaireSchema:
    """Return the interactive incident intake questionnaire schema, fields, options, and starter templates."""
    return claims_guidance_service.get_questionnaire_schema()


@router.post(
    "/guidance/evaluate",
    response_model=IncidentGuidanceResult,
    summary="Evaluate incident questionnaire against policy clauses and generate claims guidance",
)
async def evaluate_incident_guidance(
    payload: IncidentQuestionnaireRequest,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> IncidentGuidanceResult:
    """
    Evidence-grounded evaluation of user care incident against target policy.
    Identifies timely filing limits, prior auth requirements, network risks, document checklist, and provider inquiries.
    """
    try:
        policy = get_policy_record(payload.policy_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not load the selected policy. Please retry.",
        )

    check_policy_access(policy, current_user)
    result = claims_guidance_service.evaluate_incident(payload, policy)

    # Audit storage is supplemental to generating a member's guidance. A database
    # outage in the audit log must not turn a valid policy analysis into HTTP 500.
    user_id = current_user.id if current_user else "anonymous"
    try:
        await audit_repo.record_event(
            AuditEventCreate(
                user_id=user_id,
                action="claims.guidance.evaluated",
                resource_type="guidance",
                resource_id=result.guidance_id,
                details={
                    "policy_id": payload.policy_id,
                    "incident_category": payload.incident_category.value,
                    "readiness_score_pct": result.readiness_score_pct,
                    "risk_level": result.risk_level.value,
                },
            )
        )
    except Exception:
        logger.exception("Could not persist audit event for claim guidance %s", result.guidance_id)

    return result


@router.get(
    "/{claim_id}",
    response_model=ClaimRecord,
    summary="Retrieve claim details by ID",
)
async def get_claim_by_id(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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


@router.get(
    "/{claim_id}/guidance",
    response_model=IncidentGuidanceResult,
    summary="Generate evidence-grounded claims guidance for an existing claim",
)
async def get_claim_guidance(
    claim_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> IncidentGuidanceResult:
    """
    Retrieve claims guidance evaluated against the designated policy for an existing claim record.
    """
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID '{claim_id}' not found.",
        )
    _check_claim_access(claim, current_user)

    try:
        policy = get_policy_record(claim.policy_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not load the selected policy. Please retry.",
        )

    check_policy_access(policy, current_user)
    req = IncidentQuestionnaireRequest(
        policy_id=claim.policy_id,
        incident_date=claim.incident_date.isoformat(),
        estimated_loss_cents=claim.estimated_loss_cents,
        incident_category=IncidentCategory.OTHER,
        user_notes=" ".join(filter(None, [
            f"Claim type: {claim.claim_type}" if claim.claim_type else "",
            f"Incident: {claim.incident_description}" if claim.incident_description else "",
            f"Location: {claim.incident_location}" if claim.incident_location else "",
        ])) or None,
        provided_document_titles=[document.file_name for document in claim.documents],
    )

    return claims_guidance_service.evaluate_incident(req, policy)



@router.post(
    "/{claim_id}/adjudicate",
    response_model=ExplanationOfBenefits,
    summary="Run evidence-based adjudication against policy clauses and generate EOB",
)
async def adjudicate_claim(
    claim_id: str,
    payload: Optional[ClaimAdjudicateRequest] = None,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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

    from app.api.v1.endpoints.policies import _dev_policy_store, SHARED_USER_IDS
    pol = _dev_policy_store.get(claim.policy_id)
    if not pol:
        raise HTTPException(status_code=404, detail="Selected policy not found.")
    check_policy_access(pol, current_user)

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
                "policy_id": claim.policy_id,
                "total_billed_cents": eob.total_billed_cents,
                "member_responsibility_cents": eob.total_illustrative_member_cents,
                "illustrative_insurer_cents": eob.total_illustrative_insurer_cents,
                "adjudicated_items_count": len(eob.items),
                "validation_check": f"Rules calculation completed: {len(eob.items)} line items processed; Member owes ${(eob.total_illustrative_member_cents or 0)/100:.2f}",
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
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


@router.post("/{claim_id}/description-draft")
async def generate_claim_description(claim_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    from app.api.v1.endpoints.qa import ask_policy_question
    from app.schemas.qa import QARequest, ChatHistoryMessage
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    _check_claim_access(claim, current_user)
    response = await ask_policy_question(QARequest(
        policy_id=claim.policy_id,
        question="Help draft a factual first-person claim description using only the incident facts provided. Separate policy considerations and cite their clauses. Do not invent facts, amounts, documents or approval. Identify missing information for my review.",
        history=[ChatHistoryMessage(role="user", content=f"Incident: {claim.incident_description}. Date: {claim.incident_date}. Location: {claim.incident_location or 'not provided'}. Estimated loss in cents: {claim.estimated_loss_cents}.")],
    ), current_user)
    return {"description": response.answer, "citations": response.citations}


@router.delete("/{claim_id}/documents/{document_id}", response_model=ClaimRecord)
async def remove_claim_document(claim_id: str, document_id: str, current_user: AuthenticatedUser = Depends(require_authenticated_user)):
    from app.db.local_store import local_store
    claim = claim_repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    _check_claim_access(claim, current_user)
    if not any(document.id == document_id for document in claim.documents):
        raise HTTPException(status_code=404, detail="Document not found.")
    with local_store._connection() as conn:
        conn.execute("DELETE FROM claim_documents WHERE claim_id=%s AND id=%s", (claim_id, document_id))
        conn.commit()
    claim.documents = [document for document in claim.documents if document.id != document_id]
    claim.updated_at = datetime.now(timezone.utc)
    await claim_repo.save_claim(claim)
    return claim
