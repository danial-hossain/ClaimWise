"""Multi-Policy Comparison Endpoints with Server-Side PDF Export and Audit Trail."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.config import get_settings
from app.core.security import AuthenticatedUser, get_current_user_optional
from app.db.audit_repo import audit_repo
from app.db.comparison_repo import comparison_repo
from app.schemas.audit import AuditEventCreate
from app.schemas.comparison import (
    ComparisonCostSimulation,
    ComparisonCreateRequest,
    ComparisonRecord,
    CostSimulationAssumption,
)
from app.services.comparison_service import comparison_service
from app.services.pdf_export_service import pdf_export_service

logger = logging.getLogger("claimwise.api.comparisons")

router = APIRouter(prefix="/comparisons", tags=["Multi-Policy Comparisons"])


def _check_comparison_access(record: ComparisonRecord, current_user: Optional[AuthenticatedUser]) -> None:
    """Enforce server-side ownership check and tenant isolation on comparison records."""
    settings = get_settings()
    if settings.environment.lower() == "production":
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required on protected production routes.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if record.user_id and record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Comparison '{record.id}' belongs to another user.",
            )
    else:
        if current_user and current_user.id != "dev-user-001" and record.user_id and record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Comparison '{record.id}' belongs to another user.",
            )


@router.post(
    "",
    response_model=ComparisonRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Create a side-by-side comparison across 2 to 4 authorized policies",
)
async def create_comparison(
    payload: ComparisonCreateRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ComparisonRecord:
    """
    Build a comprehensive comparison matrix for 2-4 policies.
    """
    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production mode.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = current_user.id if current_user else "dev-user-001"

    try:
        record = comparison_service.create_comparison(
            request=payload,
            user_id=user_id,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except KeyError as key_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(key_err).strip("'"),
        )

    await comparison_repo.save_comparison(record)

    await audit_repo.record_event(
        AuditEventCreate(
            action="comparison.create",
            resource_type="comparison",
            resource_id=record.id,
            outcome="success",
            user_id=user_id,
            metadata={
                "title": record.title,
                "policy_count": len(record.policies),
                "policy_ids": [p.policy_id for p in record.policies],
            },
        )
    )

    return record


@router.get(
    "/{comparison_id}",
    response_model=ComparisonRecord,
    summary="Retrieve saved comparison record by ID",
)
async def get_comparison(
    comparison_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ComparisonRecord:
    """Retrieve saved multi-policy comparison."""
    record = comparison_repo.get_comparison(comparison_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison with ID '{comparison_id}' not found in active session.",
        )
    _check_comparison_access(record, current_user)
    return record


@router.post(
    "/{comparison_id}/simulate-cost",
    response_model=ComparisonCostSimulation,
    summary="Recalculate illustrative cost simulation under explicit user assumptions",
)
async def recalculate_comparison_cost(
    comparison_id: str,
    assumptions: CostSimulationAssumption,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> ComparisonCostSimulation:
    """
    Recalculate illustrative costs for all policies in a comparison using explicit assumptions.
    Integer-cents deterministic rules engine calculations.
    """
    record = comparison_repo.get_comparison(comparison_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison with ID '{comparison_id}' not found.",
        )
    _check_comparison_access(record, current_user)

    cost_sim = comparison_service._simulate_costs(assumptions, record.policies)
    record.cost_simulation = cost_sim
    await comparison_repo.save_comparison(record)

    user_id = current_user.id if current_user else record.user_id
    await audit_repo.record_event(
        AuditEventCreate(
            action="comparison.simulate_cost",
            resource_type="comparison",
            resource_id=record.id,
            outcome="success",
            user_id=user_id,
            metadata={
                "billed_charges_cents": assumptions.billed_charges_cents,
                "policies_simulated": len(record.policies),
            },
        )
    )

    return cost_sim


@router.get(
    "/{comparison_id}/pdf",
    summary="Export side-by-side multi-policy comparison report as styled PDF",
)
async def export_comparison_pdf(
    comparison_id: str,
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> Response:
    """
    Generate and stream a styled Multi-Policy Comparison Report PDF.
    Enforces authorization and returns standard PDF download headers.
    """
    record = comparison_repo.get_comparison(comparison_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison with ID '{comparison_id}' not found.",
        )
    _check_comparison_access(record, current_user)

    pdf_bytes = pdf_export_service.generate_comparison_pdf(record)

    user_id = current_user.id if current_user else record.user_id
    await audit_repo.record_event(
        AuditEventCreate(
            action="comparison.export_pdf",
            resource_type="comparison",
            resource_id=record.id,
            outcome="success",
            user_id=user_id,
            metadata={
                "title": record.title,
                "policy_count": len(record.policies),
                "pdf_size_bytes": len(pdf_bytes),
            },
        )
    )

    safe_title = "".join(c for c in record.title if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
    filename = f"ClaimWise_Comparison_{safe_title[:24] or record.id[:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


@router.get(
    "",
    response_model=List[ComparisonRecord],
    summary="List all comparisons in active session",
)
async def list_comparisons(
    current_user: Optional[AuthenticatedUser] = Depends(get_current_user_optional),
) -> List[ComparisonRecord]:
    """List comparisons in current session for authorized user."""
    if settings.environment.lower() == "production":
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required in production mode.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return comparison_repo.list_comparisons(user_id=current_user.id)

    if current_user and current_user.id != "dev-user-001":
        return comparison_repo.list_comparisons(user_id=current_user.id)
    return comparison_repo.list_comparisons(user_id=None)
