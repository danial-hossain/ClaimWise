"""Policy upload and management endpoints."""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.security import AuthenticatedUser, get_current_user_optional
from app.db.audit_repo import audit_repo
from app.db.policy_repo import policy_repo
from app.models.domain import PolicyType
from app.schemas.audit import AuditEventCreate
from app.schemas.policy import (
    PolicyExtractionResult,
)
from app.services.document_service import DocumentProcessingError, document_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service

logger = logging.getLogger("claimwise.api.policies")

router = APIRouter(prefix="/policies", tags=["Policies"])

# In-memory store for local development preview mode when database is unconfigured
# Stores: policy_id -> PolicyExtractionResult
_dev_policy_store: Dict[str, PolicyExtractionResult] = {}


@router.post(
    "/upload",
    response_model=PolicyExtractionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Secure policy document ingestion and clause extraction",
)
async def upload_policy(
    file: UploadFile = File(..., description="Insurance policy PDF document"),
    title: Optional[str] = Form(None, description="Descriptive title of policy"),
    insurer_name: Optional[str] = Form(None, description="Name of insurance provider"),
    policy_type: PolicyType = Form(default=PolicyType.HEALTH, description="Insurance category"),
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> PolicyExtractionResult:
    """
    Securely ingest an insurance policy PDF, extract clauses with 1-based page numbers,
    compute SHA-256 integrity hash, and return structured evidence chunks.
    
    Security & Validation:
    - Verifies .pdf file extension.
    - Validates MIME type.
    - Inspects file header signature magic bytes (%PDF) to reject disguised formats.
    - Enforces maximum file size limit in streaming chunks.
    - Does not log sensitive document contents or credentials.
    - Runs in clearly marked 'development_preview' mode when database is not configured.
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required on protected production routes.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    filename = file.filename or "policy.pdf"

    # 1. Filename extension validation
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension for '{filename}'. Only PDF documents (.pdf) are accepted.",
        )

    # 2. MIME type inspection
    content_type = (file.content_type or "").lower()
    allowed_mimes = [m.lower() for m in settings.allowed_upload_mime_types] + ["application/x-pdf", "application/octet-stream"]
    if content_type and content_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid Content-Type '{content_type}'. Must be 'application/pdf'.",
        )

    # 3. Streamed byte-limited read (prevents decompression bombs & memory exhaustion)
    max_bytes = settings.max_upload_size_bytes
    byte_buffer = bytearray()
    chunk_size = 512 * 1024  # 512 KB chunks

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
            detail="Uploaded file is empty (0 bytes). Please upload a valid non-empty PDF document.",
        )

    # 5. Magic byte verification (%PDF)
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invalid file signature. File header does not match PDF format (%PDF). Untrusted file format rejected.",
        )

    # 6. Extract clauses and compute integrity hash using DocumentService
    try:
        extraction_result = document_service.process_pdf(
            file_bytes=file_bytes,
            filename=filename,
            persistence_mode="development_preview",
        )
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if exc.status_code == "empty" else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )

    # Check for unrecoverable malformed PDF
    if extraction_result.status == "malformed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=extraction_result.message,
        )

    # 7. Database Persistence / Development Mode Handling
    persisted_id: Optional[str] = None
    policy_title = title or filename.rsplit(".", 1)[0].replace("_", " ").title()
    carrier = insurer_name or "Unknown Insurer"

    if current_user and extraction_result.has_extractable_text:
        # Attempt real database write if user is authenticated
        persisted_id = await policy_repo.save_policy_and_chunks(
            user_id=current_user.id,
            title=policy_title,
            insurer_name=carrier,
            policy_type=policy_type,
            document_hash=extraction_result.document_hash,
            clauses=extraction_result.clauses,
        )

    if persisted_id:
        extraction_result.persistence_mode = "persistent_db"
        extraction_result.policy_id = persisted_id
        extraction_result.message += " [Persisted to database]"
    else:
        # Local development in-memory mode: assign unique ID and retain in memory
        dev_id = f"dev-policy-{uuid.uuid4().hex[:8]}"
        extraction_result.persistence_mode = "development_preview"
        extraction_result.policy_id = dev_id
        if current_user is None:
            extraction_result.message += (
                " [Local Development Mode: Processed in memory. "
                "Database connection unverified; record held in development session.]"
            )
        else:
            extraction_result.message += (
                " [Local Development Mode: Database unverified/unreachable; "
                "record held in memory preview.]"
            )
        _dev_policy_store[dev_id] = extraction_result

    # Index clauses into retrieval engine
    effective_id = persisted_id or extraction_result.policy_id
    if effective_id and extraction_result.clauses:
        hybrid_retrieval_service.index_policy(
            policy_id=effective_id,
            clauses=extraction_result.clauses,
            document_hash=extraction_result.document_hash,
        )

    logger.info(
        "PDF processed: name=%s, size=%d bytes, hash=%s, clauses=%d, persistence=%s",
        filename,
        len(file_bytes),
        extraction_result.document_hash,
        extraction_result.total_clauses,
        extraction_result.persistence_mode,
    )

    user_id = current_user.id if current_user else "dev-user-001"
    await audit_repo.record_event(
        AuditEventCreate(
            action="policy.upload",
            resource_type="policy",
            resource_id=extraction_result.policy_id,
            outcome=extraction_result.status,
            user_id=user_id,
            metadata={
                "filename": filename,
                "total_clauses": extraction_result.total_clauses,
                "document_hash": extraction_result.document_hash,
                "persistence_mode": extraction_result.persistence_mode,
            },
        )
    )

    return extraction_result


@router.get(
    "",
    response_model=List[PolicyExtractionResult],
    summary="List extracted policies in current session",
)
async def list_policies() -> List[PolicyExtractionResult]:
    """
    List policies currently available in the development preview session.
    """
    return list(_dev_policy_store.values())


@router.get(
    "/{policy_id}",
    response_model=PolicyExtractionResult,
    summary="Retrieve extracted policy details and clauses",
)
async def get_policy(policy_id: str) -> PolicyExtractionResult:
    """
    Retrieve full extraction result and clauses by policy identifier.
    """
    if policy_id not in _dev_policy_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID '{policy_id}' not found in active session.",
        )
    return _dev_policy_store[policy_id]
