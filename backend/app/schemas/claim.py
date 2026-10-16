"""Pydantic schemas for Claim entities, Bill Parsing, Adjudication, EOB, and Mock Sandbox Gateway."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import ClaimStatus, DocumentType
from app.schemas.qa import VerifiedCitation


class LineItemDecisionStatus(str, Enum):
    """Evidence-based adjudication decision status for a single bill line item."""
    POTENTIALLY_COVERED = "potentially_covered"
    POTENTIALLY_EXCLUDED = "potentially_excluded"
    REQUIRES_REVIEW = "requires_review"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_EVALUATED = "not_evaluated"


class SandboxOutcomeStatus(str, Enum):
    """Simulated payer gateway status."""
    APPROVED_SIMULATION = "APPROVED_SIMULATION"
    PARTIALLY_APPROVED_SIMULATION = "PARTIALLY_APPROVED_SIMULATION"
    DENIED_EXCLUSION_SIMULATION = "DENIED_EXCLUSION_SIMULATION"
    PENDING_ADDITIONAL_INFO = "PENDING_ADDITIONAL_INFO"
    SIMULATED_TRANSMISSION_ERROR = "SIMULATED_TRANSMISSION_ERROR"


# ==============================================================================
# BILL INTAKE & LINE ITEM SCHEMAS
# ==============================================================================

class BillLineItem(BaseModel):
    """Extracted line item from an uploaded medical bill or invoice."""
    line_id: str = Field(..., description="Stable line item identifier, e.g. LINE-01")
    service_date: Optional[str] = Field(None, description="Date of service in YYYY-MM-DD or MM/DD/YYYY format")
    description: str = Field(..., description="Procedure or service description")
    cpt_code: Optional[str] = Field(None, description="5-character CPT/HCPCS code (e.g. 99284, 80053)")
    billed_charge_cents: int = Field(..., ge=0, description="Billed charge amount in integer cents")
    quantity: int = Field(default=1, ge=1, description="Quantity / unit count of service")
    provider_name: Optional[str] = Field(None, description="Provider / facility name if identified")
    source_page_number: int = Field(..., ge=1, description="1-based PDF page where line item appears")
    raw_text_excerpt: str = Field(..., description="Exact raw text line extracted from the bill")
    is_ambiguous: bool = Field(default=False, description="True if parsed with heuristic uncertainty")
    ambiguity_notes: Optional[str] = Field(None, description="Explanation of ambiguity for user review")


class BillLineItemUpdate(BaseModel):
    """User review / manual correction payload for a line item before adjudication."""
    service_date: Optional[str] = None
    description: Optional[str] = None
    cpt_code: Optional[str] = None
    billed_charge_cents: Optional[int] = Field(None, ge=0)
    quantity: Optional[int] = Field(None, ge=1)
    provider_name: Optional[str] = None


class BillExtractionResult(BaseModel):
    """Response returned upon parsing an uploaded medical bill PDF."""
    bill_id: str
    document_name: str
    document_hash: str
    file_size_bytes: int
    total_pages: int
    total_billed_cents: int
    is_scanned: bool
    has_extractable_text: bool
    line_items: List[BillLineItem]
    uploaded_at: datetime
    message: str
    persistence_mode: str = "development_preview"
    user_id: Optional[str] = None


# ==============================================================================
# ADJUDICATION & EOB SCHEMAS
# ==============================================================================

class AdjudicatedLineItem(BaseModel):
    """Line item evaluated against policy clauses and deterministic rules."""
    line_id: str
    service_date: Optional[str]
    description: str
    cpt_code: Optional[str]
    billed_charge_cents: int
    allowed_amount_cents: Optional[int] = Field(
        None,
        description="Negotiated allowed amount in cents. Null if not established by evidence.",
    )
    potentially_covered_cents: int = Field(0, ge=0)
    deductible_applied_cents: int = Field(0, ge=0)
    copay_cents: int = Field(0, ge=0)
    member_coinsurance_cents: int = Field(0, ge=0)
    uncovered_amount_cents: int = Field(0, ge=0)
    uncovered_reason: Optional[str] = None
    illustrative_member_cents: int = Field(0, ge=0)
    illustrative_insurer_cents: int = Field(0, ge=0)
    decision_status: LineItemDecisionStatus
    decision_rationale: str
    evidence_citations: List[VerifiedCitation] = Field(default_factory=list)
    assumptions_and_missing_facts: List[str] = Field(default_factory=list)
    requires_manual_review: bool = False


class ExplanationOfBenefits(BaseModel):
    """Structured, itemized Explanation of Benefits (EOB) calculation."""
    eob_id: str
    claim_id: str
    policy_id: str
    policy_name: Optional[str] = None
    bill_document_hash: str
    policy_document_hash: Optional[str] = None
    created_at: datetime
    simulation_disclaimer: str
    total_billed_cents: int
    total_allowed_cents: Optional[int] = None
    total_deductible_applied_cents: int
    total_copay_cents: int
    total_member_coinsurance_cents: int
    total_uncovered_cents: int
    total_illustrative_member_cents: int
    total_illustrative_insurer_cents: int
    items: List[AdjudicatedLineItem]
    calculation_audit_steps: List[str] = Field(default_factory=list)


# ==============================================================================
# CLAIM RECORDS & API CONTRACTS
# ==============================================================================

class ClaimCreateFromBillRequest(BaseModel):
    """Request to create a claim record from reviewed bill line items."""
    policy_id: str = Field(..., description="Policy ID to evaluate against")
    bill_id: str = Field(..., description="Bill ID from previous /upload-bill step")
    claim_reference: Optional[str] = None
    line_items: Optional[List[BillLineItem]] = Field(
        None,
        description="Optional edited line items. If omitted, uses original extracted items.",
    )


class ClaimChecklistItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    mandatory: bool = False
    completed: bool = False
    source_clause_id: Optional[str] = None


class ClaimTimelineEvent(BaseModel):
    id: str
    event_type: str
    summary: str
    source: str = "internal"
    created_at: datetime


class ClaimFileMeta(BaseModel):
    id: str
    file_name: str
    file_size_bytes: int
    mime_type: str
    uploaded_at: datetime


class ClaimIntakeCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    analysis_id: Optional[str] = Field(default=None, max_length=100)
    policy_id: str
    claim_type: str = Field(..., min_length=2, max_length=100)
    incident_description: str = Field(..., min_length=5, max_length=5000)
    incident_date: date
    incident_location: Optional[str] = Field(default=None, max_length=300)
    estimated_loss_cents: Optional[int] = Field(default=None, ge=0)
    claim_reference: Optional[str] = Field(default=None, max_length=100)
    checklist: List[ClaimChecklistItem] = Field(default_factory=list)


class ClaimIntakeUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    claim_description_draft: Optional[str] = Field(default=None, max_length=10000)
    claim_type: Optional[str] = Field(default=None, min_length=2, max_length=100)
    incident_description: Optional[str] = Field(default=None, min_length=5, max_length=5000)
    incident_date: Optional[date] = None
    incident_location: Optional[str] = Field(default=None, max_length=300)
    estimated_loss_cents: Optional[int] = Field(default=None, ge=0)
    claim_reference: Optional[str] = Field(default=None, max_length=100)
    checklist: Optional[List[ClaimChecklistItem]] = None


class ClaimAdjudicateRequest(BaseModel):
    """Request to run evidence-grounded adjudication on a claim."""
    member_coinsurance_percentage: Optional[float] = Field(
        default=20.0,
        ge=0.0,
        le=100.0,
        description="Policy coinsurance rate (default 20% if not auto-detected)",
    )
    initial_remaining_deductible_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Custom initial deductible balance in cents (defaults to policy deductible)",
    )
    initial_remaining_oop_max_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Custom initial OOP max balance in cents (defaults to policy OOP max)",
    )


class ClaimRecord(BaseModel):
    """Complete claim representation including line items, adjudication, and sandbox state."""
    id: str
    user_id: str
    policy_id: str
    claim_reference: Optional[str] = None
    bill_id: str = ""
    bill_document_name: str = ""
    bill_document_hash: str = ""
    incident_date: date
    total_billed_cents: int
    status: ClaimStatus
    line_items: List[BillLineItem] = Field(default_factory=list)
    adjudicated_items: List[AdjudicatedLineItem] = Field(default_factory=list)
    eob: Optional[ExplanationOfBenefits] = None
    sandbox_submission: Optional[Dict[str, Any]] = None
    claim_type: Optional[str] = None
    incident_description: Optional[str] = None
    incident_location: Optional[str] = None
    estimated_loss_cents: Optional[int] = None
    checklist: List[ClaimChecklistItem] = Field(default_factory=list)
    timeline: List[ClaimTimelineEvent] = Field(default_factory=list)
    analysis_id: Optional[str] = None
    coverage_analysis: Optional[Dict[str, Any]] = None
    claim_description_draft: Optional[str] = None
    documents: List[ClaimFileMeta] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClaimDocumentMeta(BaseModel):
    id: str
    document_type: DocumentType
    file_name: str
    file_size_bytes: Optional[int] = None
    mime_type: str
    created_at: datetime


class ClaimBase(BaseModel):
    policy_id: Optional[str] = None
    claim_reference: Optional[str] = None
    incident_date: date
    claimed_amount_cents: int = Field(..., ge=0, description="Claimed amount in cents")
    insurer_reason_code: Optional[str] = None
    insurer_denial_notes: Optional[str] = None


class ClaimCreate(ClaimBase):
    pass


class ClaimResponse(ClaimBase):
    id: str
    user_id: str
    approved_amount_cents: int
    status: ClaimStatus
    ai_investigation_summary: Optional[str] = None
    documents: List[ClaimDocumentMeta] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)



# ==============================================================================
# MOCK INSURER SANDBOX SCHEMAS
# ==============================================================================

class SandboxSubmitRequest(BaseModel):
    """Payload to simulate submitting a claim to the local mock payer sandbox."""
    user_confirmed: bool = Field(
        ...,
        description="Mandatory user acknowledgment that this is a local simulation with no live transmission.",
    )
    idempotency_key: str = Field(
        ...,
        description="Client-generated unique key to prevent duplicate submissions.",
    )
    requested_scenario: Optional[str] = Field(
        default="auto",
        description="Simulation scenario: 'auto', 'approve', 'deny_exclusion', 'partial', 'request_info', or 'gateway_error'.",
    )


class SandboxPayerOutcome(BaseModel):
    """Simulated response from the local mock insurance gateway."""
    submission_id: str
    claim_id: str
    outcome_status: SandboxOutcomeStatus
    simulated_claim_reference: str
    simulated_payer_name: str
    simulated_remittance_code: str
    simulated_paid_amount_cents: int
    simulated_patient_responsibility_cents: int
    explanation_notes: str
    simulated_edi_batch_id: str
    timestamp: datetime
    is_simulation: bool = True
    disclaimer: str
