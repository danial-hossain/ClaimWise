"""Pydantic schemas for Multi-Policy Comparison Engine.

Supports side-by-side evaluation of 2 to 4 insurance policies with transparent
evidence status tracking (verified, unknown, conflicting, not_applicable)
and deterministic integer-cents illustrative cost comparisons.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.qa import VerifiedCitation


class AttributeStatus(str, Enum):
    """Transparent evidence status for an extracted policy attribute."""
    VERIFIED = "verified"          # Supported by a validated source clause
    UNKNOWN = "unknown"            # No adequate evidence (never silently converted to 0)
    CONFLICTING = "conflicting"    # Evidence sources disagree or contradict
    NOT_APPLICABLE = "not_applicable"  # Demonstrably not applicable to this policy


class PriorAuthServiceItem(BaseModel):
    """Specific service requiring or exempt from prior authorization with exact clause citations."""
    service: str = Field(..., description="Service name requiring prior authorization")
    clause_id: str = Field(..., description="Clause ID establishing requirement")
    page: int = Field(..., description="Page number where requirement appears")
    quote: str = Field(..., description="Exact verbatim quotation from policy clause")

    @property
    def page_number(self) -> int:
        return self.page

    @property
    def exact_quote(self) -> str:
        return self.quote

    @property
    def service_name(self) -> str:
        return self.service

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PolicyAttributeEvidence(BaseModel):
    """Individual attribute evaluation with transparent status and source citations."""
    attribute_name: str = Field(..., description="Machine identifier of attribute, e.g. deductible_individual")
    display_name: str = Field(..., description="Human-readable label, e.g. 'Individual In-Network Deductible'")
    raw_value: Optional[str] = Field(None, description="Human-readable extracted value, e.g. '$1,500' or '20%'")
    numeric_value_cents: Optional[int] = Field(
        None,
        ge=0,
        description="Value in integer cents if monetary. Null if unknown or non-monetary.",
    )
    status: AttributeStatus = Field(
        ...,
        description="Evidence status: verified, unknown, conflicting, or not_applicable",
    )
    citations: List[VerifiedCitation] = Field(
        default_factory=list,
        description="Source citations validating this attribute",
    )
    notes: Optional[str] = Field(
        None,
        description="Transparent notes on missing evidence, conflicting clauses, or assumptions",
    )
    required_services: List[PriorAuthServiceItem] = Field(
        default_factory=list,
        description="List of services that explicitly require prior authorization with clause_id, page, and quote",
    )
    not_specified_services: List[str] = Field(
        default_factory=list,
        description="List of services where prior authorization status is explicitly not specified or unknown",
    )

    model_config = ConfigDict(from_attributes=True)


class PolicyComparisonCard(BaseModel):
    """Comprehensive comparison summary for a single policy within a comparison set."""
    policy_id: str
    policy_name: str
    insurer_name: str
    document_hash: str
    attributes: Dict[str, PolicyAttributeEvidence] = Field(
        default_factory=dict,
        description="Map of attribute_name to PolicyAttributeEvidence",
    )

    model_config = ConfigDict(from_attributes=True)


class CostSimulationAssumption(BaseModel):
    """User-provided or default assumptions for illustrative cost modeling."""
    service_type: str = Field(
        default="General Medical / Outpatient Care",
        description="Type of medical service being evaluated",
    )
    billed_charges_cents: int = Field(
        ...,
        ge=0,
        description="Total billed charges in integer cents",
    )
    allowed_amount_cents: Optional[int] = Field(
        None,
        ge=0,
        description="Negotiated insurer allowed amount in cents. Null if unknown.",
    )
    is_allowed_amount_known: bool = Field(
        default=False,
        description="Whether allowed amount is formally known or assumed",
    )
    network_status: str = Field(
        default="in_network",
        description="'in_network' or 'out_of_network'",
    )
    prior_deductible_paid_cents: int = Field(
        default=0,
        ge=0,
        description="Prior deductible already paid in calendar year",
    )
    prior_oop_paid_cents: int = Field(
        default=0,
        ge=0,
        description="Prior out-of-pocket spending already accumulated",
    )


class PolicyCostEstimate(BaseModel):
    """Illustrative cost calculation for a single policy under provided assumptions."""
    policy_id: str
    policy_name: str
    is_complete: bool = Field(
        ...,
        description="False if allowed amount or required policy parameters are unknown",
    )
    member_responsibility_cents: Optional[int] = Field(
        None,
        description="Calculated member payment in cents, or null if incomplete",
    )
    insurer_responsibility_cents: Optional[int] = Field(
        None,
        description="Calculated insurer payout in cents, or null if incomplete",
    )
    deductible_portion_cents: Optional[int] = Field(None)
    coinsurance_portion_cents: Optional[int] = Field(None)
    copay_portion_cents: Optional[int] = Field(None)
    calculation_audit: List[str] = Field(default_factory=list)
    caveats_and_assumptions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ComparisonCostSimulation(BaseModel):
    """Comparative financial modeling across all policies in the comparison set."""
    assumptions: CostSimulationAssumption
    policy_estimates: List[PolicyCostEstimate]
    comparative_analysis: List[str] = Field(
        default_factory=list,
        description="Objective trade-off explanations detailing which assumptions materially affect the result",
    )
    disclaimer: str = Field(
        default=(
            "ILLUSTRATIVE ESTIMATE ONLY: Calculations are educational simulations based on explicit "
            "assumptions and deterministic rules. They do not constitute actual insurer guarantees or legal payout determinations."
        )
    )

    model_config = ConfigDict(from_attributes=True)


class ComparisonCreateRequest(BaseModel):
    """Request payload to create a new multi-policy comparison."""
    policy_ids: List[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="Between 2 and 4 unique policy IDs to compare",
    )
    title: Optional[str] = Field(
        default="Multi-Policy Comparative Analysis",
        description="Optional title for the comparison report",
    )
    cost_assumptions: Optional[CostSimulationAssumption] = Field(
        None,
        description="Optional assumptions for illustrative cost modeling",
    )


class ComparisonRecord(BaseModel):
    """Persisted comparison report entity."""
    id: str
    user_id: str
    title: str
    policy_ids: List[str]
    policies: List[PolicyComparisonCard]
    cost_simulation: Optional[ComparisonCostSimulation] = None
    tradeoff_summary: List[str] = Field(default_factory=list)
    status: str = "completed"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
