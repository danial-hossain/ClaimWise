"""Pydantic schemas for Security & Compliance Engine.

Defines schemas for:
- 5-Tier Permission Security Model (Tiers 0–4)
- Automated PII & PHI Detection and Masking Engine
- Security & Compliance Self-Assessment Report
"""

from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PermissionTier(IntEnum):
    """
    Formal 5-Tier Permission Security Model for ClaimWise.
    Establishes deterministic boundary gates preventing unauthorized actions,
    unreviewed drafting, or external API leakage.
    """
    TIER_0_READ_ONLY = 0      # Read-only policy inspection; no suggestions or drafting.
    TIER_1_SUGGEST_MODE = 1    # Grounded Q&A, suggestions, and gap analysis with citations; cannot alter records.
    TIER_2_DRAFT_MODE = 2      # AI draft generation (appeals, checklists); requires human-in-the-loop review.
    TIER_3_SANDBOX_SUBMIT = 3   # Local EDI 837P simulation; requires explicit user confirmation dialog.
    TIER_4_BLOCKED = 4         # Prohibited: Live carrier EDI transmission & cross-tenant access strictly blocked.


class PIICategory(str, Enum):
    """Categories of Personally Identifiable Information (PII) and PHI."""
    SSN = "ssn"
    MEMBER_ID = "member_id"
    DOB = "date_of_birth"
    PHONE = "phone_number"
    EMAIL = "email_address"
    CREDIT_CARD = "credit_card"
    NPI = "npi_provider_id"
    PATIENT_NAME = "patient_name"


class PermissionTierDetail(BaseModel):
    """Detailed specification of a single permission tier."""
    tier: int = Field(..., ge=0, le=4, description="Permission tier number (0-4)")
    name: str = Field(..., description="Machine identifier, e.g. suggest_mode")
    title: str = Field(..., description="Human-readable title, e.g. 'Tier 1: Suggest Mode'")
    description: str = Field(..., description="Operational boundaries and safety scope")
    allowed_actions: List[str] = Field(default_factory=list, description="Permitted operations in this tier")
    prohibited_actions: List[str] = Field(default_factory=list, description="Blocked operations in this tier")
    requires_human_confirmation: bool = Field(default=False, description="Whether human confirmation is mandated")
    is_autonomous_external_transmission_allowed: bool = Field(
        default=False,
        description="Whether live external network transmission is permitted (always False)",
    )

    model_config = ConfigDict(from_attributes=True)


class PIIDetectionItem(BaseModel):
    """Individual PII/PHI detection record."""
    category: PIICategory = Field(..., description="Type of PII detected")
    masked_value: str = Field(..., description="Sanitized masked representation")
    start_pos: int = Field(..., ge=0, description="Start character index in source string")
    end_pos: int = Field(..., ge=0, description="End character index in source string")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence of detection")

    model_config = ConfigDict(from_attributes=True)


class PIIMaskRequest(BaseModel):
    """Input request to detect and redact sensitive PII/PHI."""
    text: str = Field(..., min_length=1, max_length=50000, description="Text to scan and mask")
    preserve_last_4: bool = Field(
        default=True,
        description="If true, keeps last 4 characters of SSN/cards (e.g. '***-**-1234'); if false, fully redacts",
    )
    categories: Optional[List[PIICategory]] = Field(
        default=None,
        description="Optional list of specific categories to mask. Defaults to all categories if None.",
    )

    model_config = ConfigDict(from_attributes=True)


class PIIMaskResult(BaseModel):
    """Sanitized text output and detection telemetry."""
    original_char_count: int = Field(..., ge=0, description="Length of source string")
    masked_text: str = Field(..., description="Sanitized string with PII replaced by tokens or masks")
    pii_detected_count: int = Field(..., ge=0, description="Total count of PII entities detected")
    categories_detected: List[PIICategory] = Field(
        default_factory=list,
        description="List of unique PII categories identified in the text",
    )
    detections: List[PIIDetectionItem] = Field(
        default_factory=list,
        description="Granular detection details",
    )

    model_config = ConfigDict(from_attributes=True)


class SecuritySelfAssessmentReport(BaseModel):
    """Formal security and regulatory compliance self-assessment scorecard."""
    assessment_title: str = Field(..., description="Title of the compliance audit")
    assessment_version: str = Field(default="1.0.0", description="Audit report specification version")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of self-assessment audit",
    )
    overall_compliance_score_pct: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Overall compliance readiness score (0-100%)",
    )
    frameworks_evaluated: List[str] = Field(
        default_factory=list,
        description="Standard regulatory frameworks assessed",
    )
    subsystem_evaluations: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Detailed control evaluations across all security subsystems",
    )
    permission_tiers: List[PermissionTierDetail] = Field(
        default_factory=list,
        description="Formal specifications of Tiers 0 through 4",
    )
    test_verification_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Automated pytest verification suite results",
    )
    compliance_officer_statement: str = Field(
        ...,
        description="Executive compliance assertion and boundary guarantees",
    )

    model_config = ConfigDict(from_attributes=True)
