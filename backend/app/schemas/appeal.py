"""Pydantic schemas for Evidence-Based Denial Appeal Generator.

Manages structured appeal drafts for denied claims, deterministic citation verification,
missing evidence checklists, user edits, and final export packages.
"Evidence first. If no proof, no answer."
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.qa import VerifiedCitation


class AppealStatus(str, Enum):
    """Lifecycle state of an appeal draft."""
    GENERATED = "generated"      # Auto-generated from claim evidence and policy clauses
    USER_EDITED = "user_edited"  # Reviewed and edited by human user
    EXPORTED = "exported"        # Finalized and exported for user records


class AppealChecklistItem(BaseModel):
    """Item on the evidence checklist indicating whether a necessary supporting document is present."""
    item_name: str = Field(..., description="Document or record name, e.g. 'Physician Letter of Medical Necessity'")
    description: str = Field(..., description="Why this evidence is critical for the appeal")
    is_available: bool = Field(..., description="Whether this document exists in the current claim record")
    source: str = Field(
        ...,
        description="'claim_record', 'user_uploaded', or 'missing_action_required'",
    )

    model_config = ConfigDict(from_attributes=True)


class AppealDraftCreateRequest(BaseModel):
    """Payload to trigger appeal draft generation for a denied claim."""
    denial_reason_code: Optional[str] = Field(
        None,
        description="Override or explicit denial code, e.g. 'DENIAL-EXCL-104'. If omitted, detected from claim.",
    )
    user_provided_denial_notes: Optional[str] = Field(
        None,
        description="Explanation from the insurer denial letter or EOB",
    )
    user_additional_facts: Optional[str] = Field(
        None,
        description="Untrusted user-provided factual context (e.g. physician referral details, clinical necessity)",
    )
    supporting_document_names: Optional[List[str]] = Field(
        default_factory=list,
        description="List of supporting document titles available to the user",
    )


class AppealDraftUpdateRequest(BaseModel):
    """Payload for user edits to an appeal draft."""
    statement_of_issue: Optional[str] = Field(None, description="Edited statement of issue")
    factual_background: Optional[str] = Field(None, description="Edited factual background")
    rebuttal_narrative: Optional[str] = Field(None, description="Edited rebuttal argument")
    requested_action: Optional[str] = Field(None, description="Edited requested relief")


class ClaimAppealDraft(BaseModel):
    """Complete structured appeal draft for a denied claim."""
    draft_id: str
    claim_id: str
    policy_id: str
    policy_title: str
    insurer_name: str
    claim_reference: str
    incident_date: str
    denial_reason_code: str
    denial_source: str = Field(..., description="'mock_sandbox_remittance', 'claim_record', or 'user_input'")
    statement_of_issue: str
    factual_background: str
    policy_clauses_cited: List[VerifiedCitation] = Field(
        default_factory=list,
        description="Exact policy clauses supporting member position, verified against policy text",
    )
    rebuttal_narrative: str
    evidence_gaps_identified: List[str] = Field(
        default_factory=list,
        description="Explicit gaps where evidence is insufficient or unverified",
    )
    missing_documents_checklist: List[AppealChecklistItem] = Field(
        default_factory=list,
        description="Checklist of documents needed to maximize likelihood of appeal reconsideration",
    )
    requested_action: str
    status: AppealStatus = AppealStatus.GENERATED
    disclaimer: str = Field(
        default=(
            "AI-GENERATED DRAFT REQUIRING HUMAN REVIEW: This draft is an administrative template generated "
            "by ClaimWise for educational and preparation purposes. It does not constitute legal advice, "
            "statutory advocacy, or a guarantee of claim reversal. All statements must be verified and edited "
            "by the member before submission to an insurance carrier. No claims or appeals are transmitted to insurers."
        )
    )
    is_editable: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppealExportPackage(BaseModel):
    """Finalized appeal package ready for download and offline member submission."""
    export_id: str
    draft_id: str
    claim_id: str
    formatted_markdown_letter: str
    citation_index: List[VerifiedCitation]
    evidence_checklist: List[AppealChecklistItem]
    mandatory_disclaimer: str
    exported_at: datetime

    model_config = ConfigDict(from_attributes=True)
