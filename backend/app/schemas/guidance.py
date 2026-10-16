"""Pydantic schemas for Claims Guidance and Interactive Incident Questioning Workflow (F3)."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.qa import VerifiedCitation


class IncidentCategory(str, Enum):
    """Healthcare service setting or incident classification."""
    EMERGENCY_ROOM = "emergency_room"
    INPATIENT_HOSPITAL = "inpatient_hospital"
    OUTPATIENT_SURGERY = "outpatient_surgery"
    DIAGNOSTIC_IMAGING = "diagnostic_imaging"
    SPECIALIST_CONSULT = "specialist_consult"
    PHYSICAL_THERAPY = "physical_therapy"
    PRESCRIPTION_DRUG = "prescription_drug"
    ACCIDENT_INJURY = "accident_injury"
    ROUTINE_PREVENTATIVE = "routine_preventative"
    OTHER = "other"


class NetworkStatus(str, Enum):
    """Contractual provider network tier status."""
    IN_NETWORK = "in_network"
    OUT_OF_NETWORK = "out_of_network"
    EMERGENCY_OUT_OF_NETWORK = "emergency_out_of_network"
    UNSURE = "unsure"


class PriorAuthStatus(str, Enum):
    """Pre-service precertification or prior authorization status."""
    OBTAINED = "obtained"
    NOT_OBTAINED = "not_obtained"
    EMERGENCY_WAIVED = "emergency_waived"
    NOT_APPLICABLE = "not_applicable"
    UNSURE = "unsure"


class ReferralStatus(str, Enum):
    """Primary Care Physician (PCP) formal referral status."""
    YES_REFERRED = "yes_referred"
    NO_SELF_REFERRAL = "no_self_referral"
    NOT_REQUIRED = "not_required"


class LiabilityType(str, Enum):
    """Third-party liability or coordination of benefits (COB)."""
    NONE_STANDARD = "none_standard"
    MOTOR_VEHICLE = "motor_vehicle"
    WORKPLACE_INJURY = "workplace_injury"
    THIRD_PARTY_LIABILITY = "third_party_liability"
    SECONDARY_INSURANCE = "secondary_insurance"


class GuidanceRiskLevel(str, Enum):
    """Aggregate risk level of claim denial or processing delay."""
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"


class DocumentStatus(str, Enum):
    """Status of required documentation item."""
    PROVIDED = "provided"
    MISSING = "missing"
    RECOMMENDED = "recommended"


# ==============================================================================
# QUESTIONNAIRE STRUCTURE SCHEMAS
# ==============================================================================

class QuestionnaireOption(BaseModel):
    """Selectable option within an incident questionnaire field."""
    id: str
    label: str
    description: Optional[str] = None
    risk_implication: Optional[str] = None


class QuestionnaireField(BaseModel):
    """A structured question presented to the user during incident intake."""
    id: str
    title: str
    description: str
    field_type: str = Field(
        ...,
        description="'single_select', 'multi_select', 'date', 'checkbox_group', or 'text'",
    )
    required: bool = True
    options: Optional[List[QuestionnaireOption]] = None
    help_text: Optional[str] = None


class IncidentPresetTemplate(BaseModel):
    """Pre-configured incident scenario template for rapid intake."""
    id: str
    title: str
    description: str
    category: IncidentCategory
    default_answers: Dict[str, Any]


class IncidentQuestionnaireSchema(BaseModel):
    """Complete questionnaire specification with fields and preset templates."""
    version: str = "1.0"
    title: str = "Interactive Incident Intake & Claims Guidance Interview"
    description: str = (
        "Evidence-grounded questionnaire to identify filing deadlines, prior authorization "
        "requirements, network rules, and required documentation before submitting your claim."
    )
    fields: List[QuestionnaireField]
    presets: List[IncidentPresetTemplate]


# ==============================================================================
# EVALUATION REQUEST & RESPONSE SCHEMAS
# ==============================================================================

class IncidentQuestionnaireRequest(BaseModel):
    """User responses to the incident intake questionnaire."""
    policy_id: str = Field(..., description="Target policy ID to evaluate against")
    incident_date: Optional[str] = Field(
        default=None,
        description="Date of healthcare service in YYYY-MM-DD format (defaults to 14 days ago)",
    )
    deadline_reference_date: Optional[str] = Field(default=None, description="Date explicitly named by the filing clause as the start of its deadline, such as the trip return date")
    estimated_loss_cents: Optional[int] = Field(default=None, ge=0, description="User-entered estimated amount of the loss")
    incident_category: IncidentCategory = Field(
        default=IncidentCategory.EMERGENCY_ROOM,
        description="Type of care or medical setting",
    )
    network_status: NetworkStatus = Field(
        default=NetworkStatus.IN_NETWORK,
        description="Provider network affiliation",
    )
    prior_auth_status: PriorAuthStatus = Field(
        default=PriorAuthStatus.UNSURE,
        description="Status of pre-service authorization",
    )
    referral_status: ReferralStatus = Field(
        default=ReferralStatus.NOT_REQUIRED,
        description="PCP referral status",
    )
    liability_type: LiabilityType = Field(
        default=LiabilityType.NONE_STANDARD,
        description="Third-party liability or COB involvement",
    )
    # Available Documentation Checklist
    has_itemized_bill: bool = Field(default=False, description="Legacy compatibility field; prefer provided_document_titles")
    has_medical_records: bool = Field(default=False, description="Physician clinical notes or operative report provided")
    has_prior_auth_letter: bool = Field(default=False, description="Written prior authorization letter provided")
    has_referral_letter: bool = Field(default=False, description="PCP referral document provided")
    has_accident_report: bool = Field(default=False, description="Police or workplace incident report provided")
    has_receipt_of_payment: bool = Field(default=False, description="Proof of payment or copay receipt provided")
    provided_document_titles: List[str] = Field(
        default_factory=list,
        max_length=50,
        description="Documents the member says they already have, matched against policy-stated requirements",
    )
    user_notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Additional context, provider details, or specific member questions",
    )


class TimelyFilingAnalysis(BaseModel):
    """Evaluation of the policy's timely filing deadline vs incident date."""
    incident_date: str
    evaluation_date: str
    days_elapsed: int
    timely_filing_limit_days: Optional[int] = None
    days_remaining: Optional[int] = None
    is_timely: Optional[bool] = None
    filing_deadline_date: Optional[str] = None
    warning_message: Optional[str] = None
    deadline_anchor: Optional[str] = None
    citation: Optional[VerifiedCitation] = None


class DocumentChecklistItem(BaseModel):
    """Dynamic document requirement based on incident classification."""
    item_id: str
    title: str
    description: str
    is_mandatory: bool
    status: DocumentStatus
    why_needed: str
    policy_citation: Optional[VerifiedCitation] = None


class IdentifiedObstacle(BaseModel):
    """Contractual obstacle, exclusion risk, or prior auth hurdle."""
    id: str
    title: str
    severity: str = Field(..., description="'critical', 'warning', or 'advisory'")
    description: str
    mitigation_strategy: str
    citation: Optional[VerifiedCitation] = None


class ProviderInquiry(BaseModel):
    """Targeted question to ask the provider, facility, or insurer."""
    target: str = Field(..., description="e.g. 'Hospital Billing', 'Treating Surgeon', 'Payer Member Services'")
    question: str
    rationale: str


class IncidentGuidanceResult(BaseModel):
    """Comprehensive claims guidance report grounded in policy text."""
    guidance_id: str
    policy_id: str
    policy_name: str
    readiness_score_pct: int = Field(..., ge=0, le=100, description="Readiness score from 0 to 100%")
    risk_level: GuidanceRiskLevel
    readiness_summary: str
    incident_category: IncidentCategory
    timely_filing: TimelyFilingAnalysis
    document_checklist: List[DocumentChecklistItem]
    obstacles: List[IdentifiedObstacle]
    action_plan_steps: List[str]
    provider_inquiries: List[ProviderInquiry]
    claimability_status: str = Field(default="cannot_determine", description="Potentially claimable, not supported by extracted policy text, or cannot determine")
    claimability_reason: str = ""
    claimability_citations: List[VerifiedCitation] = Field(default_factory=list)
    claim_amount_cents: Optional[int] = Field(default=None, ge=0, description="User-entered estimate; not an insurer payout calculation")
    potential_claim_clauses: List[VerifiedCitation] = Field(
        default_factory=list,
        description="Policy clauses relevant to the described incident that may be a basis to discuss a claim; not a coverage determination",
    )
    verified_citations: List[VerifiedCitation] = Field(default_factory=list)
    disclaimer: str = (
        "ClaimWise provides educational guidance grounded in policy contract language. "
        "Guidance does not constitute legal or financial advice and does not guarantee insurance claim approval."
    )
    evaluated_at: datetime
