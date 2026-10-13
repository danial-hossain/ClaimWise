"""Cryptographic Audit Trail Endpoints."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import get_settings
from app.core.security import AuthenticatedUser, get_current_user_optional
from app.db.audit_repo import audit_repo
from app.schemas.audit import AuditEvent, AuditVerificationResult

logger = logging.getLogger("claimwise.api.audit")

router = APIRouter(prefix="/audit", tags=["Cryptographic Audit Trail"])


@router.get(
    "/events",
    response_model=List[AuditEvent],
    summary="Query authorized audit events",
)
async def list_audit_events(
    action: Optional[str] = Query(None, description="Filter by action name"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(50, ge=1, le=200, description="Page size limit"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> List[AuditEvent]:
    """
    List cryptographic audit events for the authorized user.
    Enforces strict tenant isolation: users cannot view another user's audit records.
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view audit trail.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = current_user.id if current_user else None
    return audit_repo.list_events(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/verify",
    response_model=AuditVerificationResult,
    summary="Cryptographically verify audit event hash chain",
)
async def verify_audit_chain(
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> AuditVerificationResult:
    """
    Execute full cryptographic verification over the audit event hash chain.
    
    Verifies:
    1. Sequential monotonicity of event sequence numbers.
    2. Genesis block linkage.
    3. Hash linkage: each previous_hash matches the prior event's SHA-256 hash.
    4. Canonical JSON recomputation: verifies no payload fields or metadata have been altered.
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to verify audit chain.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return audit_repo.verify_chain()
