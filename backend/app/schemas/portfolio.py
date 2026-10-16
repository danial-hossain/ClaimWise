"""Pydantic schemas for F4 Aggregate Portfolio Management Engine.

Provides schemas for:
- Cross-Policy Overlap Detection (redundancy and cost-sharing divergence across multiple held policies)
- Aggregate Gap Detection (services collectively omitted or excluded across all portfolio policies)
- Coordination of Benefits (COB) Optimization Guidance (NAIC model rules: Active Employee, Birthday Rule, Longer/Shorter)
- Portfolio Health Metric & Executive Scorecard (Protection Score %, Redundancy Index %)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.qa import VerifiedCitation


class PolicyRole(str, Enum):
    """Designated role of a policy within the member's insurance portfolio."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUPPLEMENTAL = "supplemental"
    UNSPECIFIED = "unspecified"


class OverlapRedundancyDegree(str, Enum):
    """Degree of coverage redundancy between multiple policies for a specific benefit."""
    FULL_DUPLICATE = "full_duplicate"
    PARTIAL_COMPLEMENTARY = "partial_complementary"
    DIFFERENTIAL_COST_SHARING = "differential_cost_sharing"
    PRIOR_AUTH_ASYMMETRY = "prior_auth_asymmetry"


class AggregateGapSeverity(str, Enum):
    """Clinical and financial exposure severity when a service is uncovered across the portfolio."""
    CRITICAL = "critical"      # Essential healthcare domain with high unexpected out-of-pocket exposure
    MODERATE = "moderate"      # Specialized, high-cost, or elective care with universal exclusions
    ADVISORY = "advisory"      # Auxiliary/transport/experimental service with strict limitations across all policies


class COBRuleType(str, Enum):
    """NAIC Model Regulation determination rule applied for Coordination of Benefits."""
    SUBSCRIBER_EMPLOYEE_RULE = "subscriber_employee_rule"  # Patient as employee/subscriber is primary over dependent
    BIRTHDAY_RULE = "birthday_rule"                        # Dependent child: parent with earlier birth month/day is primary
    ACTIVE_VS_INACTIVE_RULE = "active_vs_inactive_rule"    # Active employee coverage is primary over COBRA/retiree
    LONGER_VS_SHORTER_RULE = "longer_vs_shorter_rule"      # Plan in effect longer is primary if other rules draw
    DEFAULT_ORDER = "default_order"                        # Baseline fallback order


class SubscriberRelationship(str, Enum):
    """Relationship of the patient to the subscriber on a given policy."""
    POLICYHOLDER = "policyholder"        # Self / primary subscriber
    DEPENDENT_SPOUSE = "dependent_spouse"
    DEPENDENT_CHILD = "dependent_child"
    OTHER_DEPENDENT = "other_dependent"


class EmploymentStatus(str, Enum):
    """Employment status of the policy subscriber."""
    ACTIVE = "active"
    RETIRED = "retired"
    COBRA = "cobra"
    OTHER = "other"


class SubscriberProfile(BaseModel):
    """Subscriber metadata used for Coordination of Benefits (COB) order determination."""
    policy_id: str = Field(..., description="Unique policy identifier")
    policy_name: Optional[str] = Field(None, description="Policy title or carrier name")
    subscriber_name: Optional[str] = Field(None, description="Name of the insured subscriber")
    relationship: SubscriberRelationship = Field(
        default=SubscriberRelationship.POLICYHOLDER,
        description="Claimant relationship to the subscriber (policyholder, dependent_spouse, dependent_child)",
    )
    employment_status: EmploymentStatus = Field(
        default=EmploymentStatus.ACTIVE,
        description="Employment status of subscriber (active, retired, cobra)",
    )
    birthday_month_day: Optional[str] = Field(
        None,
        description="Birthday formatted as MM-DD (e.g. '04-15' for April 15) for Birthday Rule evaluation",
    )
    effective_date: Optional[str] = Field(
        None,
        description="Policy inception/effective date formatted as YYYY-MM-DD for Longer/Shorter rule",
    )

    model_config = ConfigDict(from_attributes=True)


class PolicyBenefitSnapshot(BaseModel):
    """Summary of coverage and cost-sharing terms for a single policy within a category."""
    policy_id: str = Field(..., description="Identifier of the policy")
    policy_name: str = Field(..., description="Name or label of the policy")
    covered: bool = Field(..., description="True if service is covered (subject to terms)")
    cost_sharing_summary: str = Field(..., description="Copay, coinsurance, or deductible description")
    prior_auth_required: bool = Field(default=False, description="True if precertification/prior auth is mandated")
    citations: List[VerifiedCitation] = Field(
        default_factory=list,
        description="Verified contract citations supporting this benefit snapshot",
    )

    model_config = ConfigDict(from_attributes=True)


class CoverageOverlapItem(BaseModel):
    """Cross-policy redundancy analysis for an overlapping benefit category."""
    category: str = Field(..., description="Care category, e.g. Primary Care, Emergency Services, Rx")
    service_name: str = Field(..., description="Specific medical service or care need")
    redundancy_degree: OverlapRedundancyDegree = Field(
        ...,
        description="Redundancy classification: full_duplicate, partial_complementary, differential_cost_sharing, prior_auth_asymmetry",
    )
    policies: List[PolicyBenefitSnapshot] = Field(
        ...,
        description="Coverage snapshots across all policies in the portfolio that cover this service",
    )
    coordination_strategy: str = Field(
        ...,
        description="Actionable coordination strategy (how to file claims to minimize patient liability)",
    )
    notes: str = Field(..., description="Clinical or economic analysis of the overlap")

    model_config = ConfigDict(from_attributes=True)


class AggregateGapItem(BaseModel):
    """Critical medical service uncovered or severely restricted across the entire portfolio."""
    category: str = Field(..., description="Healthcare domain, e.g. Adult Routine Dental, Vision Hardware")
    service_name: str = Field(..., description="Specific uncovered care procedure or equipment")
    severity: AggregateGapSeverity = Field(
        ...,
        description="Severity: critical (high risk), moderate, or advisory",
    )
    status_summary: str = Field(
        ...,
        description="Summary of portfolio-wide status, e.g. 'Excluded across all 2 policies in your portfolio.'",
    )
    policies: List[PolicyBenefitSnapshot] = Field(
        ...,
        description="Findings across each policy showing lack of coverage or explicit exclusion",
    )
    exposure_analysis: str = Field(
        ...,
        description="Financial exposure analysis and member risk explanation",
    )
    recommended_mitigation: str = Field(
        ...,
        description="Recommended mitigation strategy (e.g. standalone dental rider, HSA/FSA allocation)",
    )
    silence_or_exclusion_proof: List[VerifiedCitation] = Field(
        default_factory=list,
        description="Verified citations of explicit contract exclusions or proof of silence",
    )

    model_config = ConfigDict(from_attributes=True)


class COBDetermination(BaseModel):
    """Coordination of Benefits (COB) order and claim filing guidelines."""
    primary_policy_id: str = Field(..., description="Designated Primary Payer policy ID")
    primary_policy_name: str = Field(..., description="Designated Primary Payer title")
    secondary_policy_id: Optional[str] = Field(None, description="Designated Secondary Payer policy ID")
    secondary_policy_name: Optional[str] = Field(None, description="Designated Secondary Payer title")
    rule_applied: COBRuleType = Field(..., description="NAIC determination rule applied")
    determination_reason: str = Field(..., description="Detailed explanation of why this payer is primary")
    step_by_step_filing_guide: List[str] = Field(
        default_factory=list,
        description="Sequential claim submission instructions for dual-policy coordination",
    )
    non_duplication_clause_alert: str = Field(
        ...,
        description="Explanation of carve-out or non-duplication rules that prevent double reimbursement",
    )
    financial_benefit_estimate: str = Field(
        ...,
        description="Explanation of how secondary coordination reduces out-of-pocket expenses",
    )

    model_config = ConfigDict(from_attributes=True)


class PortfolioScorecard(BaseModel):
    """Executive portfolio health scorecard metrics."""
    protection_score_percent: int = Field(
        ...,
        ge=0,
        le=100,
        description="Portfolio Protection Score (0-100%): breadth of coverage across essential healthcare domains",
    )
    redundancy_index_percent: int = Field(
        ...,
        ge=0,
        le=100,
        description="Redundancy Index (0-100%): proportion of benefits duplicated across held policies",
    )
    total_policies: int = Field(..., ge=2, le=4, description="Count of policies evaluated in this portfolio")
    total_overlaps_detected: int = Field(..., ge=0, description="Count of overlapping benefit categories")
    total_aggregate_gaps_detected: int = Field(..., ge=0, description="Count of uncovered collective gaps")
    aggregate_in_network_deductible_cents: Optional[int] = Field(
        None,
        description="Lowest single in-network deductible available in the portfolio (cents)",
    )
    aggregate_in_network_oop_max_cents: Optional[int] = Field(
        None,
        description="Lowest single in-network out-of-pocket maximum available in the portfolio (cents)",
    )

    model_config = ConfigDict(from_attributes=True)


class PortfolioAnalysisRequest(BaseModel):
    """Input request to evaluate an aggregate portfolio of 2 to 4 policies."""
    policy_ids: List[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="List of 2 to 4 policy IDs belonging to the user's coverage portfolio",
    )
    subscribers: Optional[List[SubscriberProfile]] = Field(
        default=None,
        description="Optional subscriber relationships and demographic profiles for COB determination",
    )
    patient_relationship: Optional[str] = Field(
        default="policyholder",
        description="Claimant relationship context: 'policyholder', 'dependent_spouse', or 'dependent_child'",
    )

    model_config = ConfigDict(from_attributes=True)


class PortfolioAnalysisResult(BaseModel):
    """Complete portfolio evaluation output including overlaps, collective gaps, and COB guidance."""
    id: str = Field(..., description="Unique portfolio evaluation identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Analysis timestamp",
    )
    analyzed_policies: List[Dict[str, Any]] = Field(
        ...,
        description="Metadata of analyzed policies (policy_id, policy_name, insurer_name, document_hash)",
    )
    scorecard: PortfolioScorecard = Field(..., description="Executive health metrics and protection scores")
    cob_guidance: COBDetermination = Field(..., description="Coordination of Benefits priority and filing protocol")
    overlaps: List[CoverageOverlapItem] = Field(
        default_factory=list,
        description="Identified cross-policy coverage overlaps and cost-sharing differentials",
    )
    aggregate_gaps: List[AggregateGapItem] = Field(
        default_factory=list,
        description="Identified collective portfolio gaps uncovered across all held policies",
    )
    key_takeaways: List[str] = Field(
        default_factory=list,
        description="Executive bullet points summarizing portfolio strengths and vulnerabilities",
    )
    non_guarantee_disclaimer: str = Field(
        default="Notice: This portfolio evaluation is an informational advisory tool based strictly on extracted contract language. It does not constitute a legal determination or guarantee of claim payment. Final claim adjudication is governed by each carrier's Master Policy Contract and Coordination of Benefits provisions.",
        description="Strict non-guarantee legal advisory disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)
