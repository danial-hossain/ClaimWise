"""Deterministic Insurance Rules Engine endpoints."""

import logging
from fastapi import APIRouter, HTTPException, status

from app.services.rules_engine import (
    CalculationValidationError,
    CostCalculationInput,
    CostCalculationResult,
    rules_engine,
)

logger = logging.getLogger("claimwise.api.rules")

router = APIRouter(prefix="/rules", tags=["Deterministic Rules Engine"])


@router.post(
    "/calculate",
    response_model=CostCalculationResult,
    status_code=status.HTTP_200_OK,
    summary="Calculate deterministic insurance cost-sharing breakdown",
)
async def calculate_cost_sharing(
    payload: CostCalculationInput,
) -> CostCalculationResult:
    """
    Execute deterministic pure-Python financial cost calculations.
    
    Calculates exact amounts for:
    - Member deductible contribution
    - Remaining deductible balance
    - Member coinsurance portion
    - Insurer coinsurance portion
    - Out-of-pocket maximum threshold reached flag
    - Policy coverage limit interactions
    
    All calculations operate on integer cents.
    This is an educational simulation, not an authoritative legal determination of actual insurer payouts.
    """
    try:
        result = rules_engine.calculate_cost_sharing(
            eligible_expense_cents=payload.eligible_expense_cents,
            remaining_deductible_cents=payload.remaining_deductible_cents,
            member_coinsurance_percentage=payload.member_coinsurance_percentage,
            remaining_out_of_pocket_max_cents=payload.remaining_out_of_pocket_max_cents,
            policy_coverage_limit_cents=payload.policy_coverage_limit_cents,
            deductible_counts_towards_oop=payload.deductible_counts_towards_oop,
        )
        return result
    except CalculationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed for field '{exc.field_name or 'input'}': {exc.message}",
        )
    except Exception as exc:
        logger.error("Unexpected calculation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error during cost calculation: {str(exc)}",
        )
