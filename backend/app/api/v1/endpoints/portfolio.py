"""Aggregate Portfolio Management API endpoints (F4).

Endpoints:
- POST /api/v1/portfolio/analyze: Evaluates 2-4 policies for cross-policy overlaps, collective gaps, and COB priority.
- GET /api/v1/portfolio/sample: Returns pre-configured aggregate analysis for Sample Policy A + Sample Policy B.
- GET /api/v1/portfolio/rules: Returns reference NAIC model coordination rules and statutory guidelines.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AuthenticatedUser, get_current_user_optional, require_authenticated_user
from app.db.audit_repo import audit_repo
from app.schemas.audit import AuditEventCreate
from app.schemas.portfolio import (
    EmploymentStatus,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResult,
    SubscriberProfile,
    SubscriberRelationship,
)
from app.services.portfolio_service import portfolio_service

logger = logging.getLogger("claimwise.api.portfolio")

router = APIRouter(prefix="/portfolio", tags=["Portfolio Management & COB Optimizer"])


@router.post(
    "/analyze",
    response_model=PortfolioAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate aggregate coverage portfolio, cross-policy overlaps, collective gaps, and COB priority",
)
async def analyze_portfolio_endpoint(
    payload: PortfolioAnalysisRequest,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> PortfolioAnalysisResult:
    """
    Evaluates 2 to 4 health insurance policies held simultaneously:
    1. Cross-Policy Overlap Detection (redundant benefits, cost-sharing differentials, prior auth asymmetries)
    2. Aggregate Gap Detection (clinical services completely uninsurable across all portfolio policies)
    3. Coordination of Benefits (COB) Optimization (NAIC Subscriber, Birthday, and Active/Inactive rules)
    4. Executive Health Scorecard (Protection Score % and Redundancy Index %)
    """
    from app.core.config import get_settings
    from app.api.v1.endpoints.policies import _dev_policy_store, SHARED_USER_IDS

    settings = get_settings()
    if settings.environment.lower() == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required on protected production routes.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.api.v1.endpoints.policies import check_policy_access
    authorized_policies = {}
    for pid in payload.policy_ids:
        pol = _dev_policy_store.get(pid)
        if not pol:
            raise HTTPException(status_code=404, detail="Selected policy not found.")
        check_policy_access(pol, current_user)
        authorized_policies[pid] = pol

    try:
        result = portfolio_service.analyze_portfolio(payload, authorized_policy_store=authorized_policies)

        # Log audit trail event
        user_id = current_user.id if current_user else "dev-user-001"
        await audit_repo.record_event(
            AuditEventCreate(
                action="portfolio.analyze",
                resource_type="portfolio",
                resource_id=result.id,
                user_id=user_id,
                payload={
                    "policy_ids": payload.policy_ids,
                    "total_policies": len(result.analyzed_policies),
                    "overlaps_detected": len(result.overlaps),
                    "aggregate_gaps_detected": len(result.aggregate_gaps),
                    "cob_primary_policy": result.cob_guidance.primary_policy_id,
                    "protection_score": result.scorecard.protection_score_percent,
                    "redundancy_index": result.scorecard.redundancy_index_percent,
                },
            )
        )

        return result
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))
    except Exception as exc:
        logger.exception("Failed to analyze insurance portfolio")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while evaluating the portfolio. Please check your inputs or try again later.",
        )


@router.get(
    "/sample",
    response_model=PortfolioAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Retrieve pre-configured aggregate analysis for Sample Policy A and Policy B",
)
async def get_sample_portfolio_endpoint(
    patient_relationship: str = "policyholder",
) -> PortfolioAnalysisResult:
    """Demonstrates aggregate portfolio analysis and COB optimization across Sample Policies A & B."""
    from app.core.config import get_settings
    if get_settings().environment == "production":
        raise HTTPException(status_code=403, detail="Sample analysis is disabled in production.")
    request = PortfolioAnalysisRequest(
        policy_ids=["policy_a", "policy_b"],
        patient_relationship=patient_relationship,
        subscribers=[
            SubscriberProfile(
                policy_id="policy_a",
                policy_name="Sample Health Insurance Policy A",
                subscriber_name="Jane Doe (Primary Employee)",
                relationship=SubscriberRelationship.POLICYHOLDER,
                employment_status=EmploymentStatus.ACTIVE,
                birthday_month_day="04-12",
                effective_date="2022-01-01",
            ),
            SubscriberProfile(
                policy_id="policy_b",
                policy_name="Sample Health Insurance Policy B",
                subscriber_name="John Doe (Spouse)",
                relationship=SubscriberRelationship.DEPENDENT_SPOUSE,
                employment_status=EmploymentStatus.ACTIVE,
                birthday_month_day="09-28",
                effective_date="2023-01-01",
            ),
        ],
    )
    return portfolio_service.analyze_portfolio(request)


@router.get(
    "/rules",
    summary="Retrieve NAIC Model Regulation Coordination of Benefits statutory reference rules",
)
async def get_cob_rules_reference() -> Dict[str, Any]:
    """Provides reference documentation on NAIC model rules for secondary coordination."""
    return {
        "title": "NAIC Model Regulation #120 Coordination of Benefits (COB) Rules",
        "description": "Statutory priority order determining which group health plan pays first when an individual has duplicate health insurance.",
        "rules": [
            {
                "rule_name": "Subscriber / Employee vs. Dependent Rule",
                "code": "subscriber_employee_rule",
                "priority": 1,
                "summary": "The plan that covers the patient directly as an employee, member, or policyholder pays PRIMARY before a plan that covers the person as a dependent.",
            },
            {
                "rule_name": "Active Employee vs. Inactive / Retired / COBRA Rule",
                "code": "active_vs_inactive_rule",
                "priority": 2,
                "summary": "A plan that covers the person as an active employee pays PRIMARY over a plan covering the person under COBRA continuation or retiree benefits.",
            },
            {
                "rule_name": "Dependent Child / Birthday Rule",
                "code": "birthday_rule",
                "priority": 3,
                "summary": "When a dependent child is covered by both parents' non-separated plans, the plan of the parent whose birthday (month and day, ignoring year) falls earlier in the calendar year is PRIMARY. If both parents have the same birthday, the plan covering the parent longer is primary.",
            },
            {
                "rule_name": "Longer vs. Shorter Length of Coverage Rule",
                "code": "longer_vs_shorter_rule",
                "priority": 4,
                "summary": "If none of the preceding rules establish priority, the plan that has covered the individual for the longer continuous period pays PRIMARY.",
            },
        ],
        "non_duplication_warning": "Most group plans enforce 'Non-Duplication of Benefits' (Carve-Out) coordination, which caps secondary payout to the difference between secondary plan allowable charges and primary payments. Secondary plans will not pay if primary payment equals or exceeds secondary allowable.",
    }
