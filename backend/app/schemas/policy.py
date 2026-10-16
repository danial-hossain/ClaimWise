"""Pydantic schemas for Policy entity contracts."""

from datetime import date, datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.domain import PolicyStatus, PolicyType


class PolicyBase(BaseModel):
    title: str = Field(..., description="Descriptive title of policy")
    insurer_name: str = Field(..., description="Insurance company name")
    policy_number: Optional[str] = Field(None, description="Policy number / contract ID")
    policy_type: PolicyType = Field(default=PolicyType.HEALTH, description="Category of insurance policy")
    coverage_start_date: Optional[date] = None
    coverage_end_date: Optional[date] = None
    deductible_amount_cents: int = Field(default=0, ge=0, description="Deductible in cents")
    out_of_pocket_max_cents: int = Field(default=0, ge=0, description="Out-of-pocket maximum in cents")
    annual_limit_cents: Optional[int] = Field(None, ge=0, description="Annual cap in cents")


class PolicyCreate(PolicyBase):
    pass


class PolicyResponse(PolicyBase):
    id: str
    user_id: str
    status: PolicyStatus
    raw_document_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyClauseCitation(BaseModel):
    """Evidence citation linking an answer directly to an exact clause and page."""
    clause_identifier: str
    page_number: int
    section_heading: Optional[str] = None
    exact_text: str
    confidence_score: float


class ExtractedClause(BaseModel):
    """Structured clause extraction result preserving verbatim text and page references."""
    clause_id: str = Field(..., description="Stable clause identifier within this policy version")
    page_number: int = Field(..., ge=1, description="One-based page number")
    printed_page_label: Optional[str] = Field(None, description="PDF page label, when explicitly supplied by the source; distinct from PDF index")
    clause_heading: Optional[str] = Field(None, description="Detected or inferred clause heading")
    heading_confidence: str = Field(
        default="none",
        description="Confidence in heading detection: high, heuristic, uncertain, or none",
    )
    section_number: Optional[str] = Field(None, description="Explicit section/article number if detected")
    text: str = Field(..., description="Original extracted verbatim clause text")
    token_count: int = Field(default=0, ge=0, description="Approximate token count for the clause")
    document_hash: str = Field(..., description="SHA-256 hash of the parent document")
    is_clause: bool = Field(default=True, description="True if text represents a genuine contractual clause/provision")

    model_config = ConfigDict(from_attributes=True)


class PolicyHeadingRewriteItem(BaseModel):
    id: str = Field(..., min_length=1, max_length=80)
    heading: str = Field(..., min_length=1, max_length=200)
    context: str = Field(default="", max_length=2400)


class PolicyHeadingRewriteRequest(BaseModel):
    headings: List[PolicyHeadingRewriteItem] = Field(..., min_length=1, max_length=100)


class PolicyHeadingRewriteResponse(BaseModel):
    headings: Dict[str, str] = Field(default_factory=dict)
    ai_used: bool = False


class PageSummary(BaseModel):
    """Summary of extraction metrics for an individual PDF page."""
    page_number: int = Field(..., ge=1, description="One-based page number")
    clause_count: int = Field(default=0, ge=0)
    char_count: int = Field(default=0, ge=0)
    has_images: bool = Field(default=False)
    sample_heading: Optional[str] = None


class PolicyExtractionResult(BaseModel):
    """Complete structured response for policy document ingestion and evidence extraction."""
    document_name: str = Field(..., description="Original uploaded filename")
    document_hash: str = Field(..., description="Cryptographic SHA-256 hash of original PDF")
    file_size_bytes: int = Field(..., ge=0, description="Document byte size")
    total_pages: int = Field(..., ge=0, description="Total number of pages processed")
    total_clauses: int = Field(default=0, ge=0, description="Number of granular clauses extracted")
    is_scanned: bool = Field(default=False, description="Flag indicating scanned/image-only PDF without digital text")
    has_extractable_text: bool = Field(default=True, description="Whether digital extractable text was found")
    status: str = Field(..., description="Status code: success, scanned_ocr_unavailable, empty, malformed, encrypted")
    message: str = Field(..., description="Safe human-readable status or warning message")
    pages: List[PageSummary] = Field(default_factory=list, description="Page-level extraction summaries")
    clauses: List[ExtractedClause] = Field(default_factory=list, description="Extracted clause references")
    persistence_mode: str = Field(
        default="development_preview",
        description="Storage status: development_preview (in-memory demo) or persistent_db",
    )
    policy_id: Optional[str] = Field(None, description="Unique policy identifier if persisted")
    user_id: Optional[str] = Field(None, description="Account user ID that uploaded this policy")
    uploaded_at: datetime = Field(..., description="UTC timestamp of ingestion")

    model_config = ConfigDict(from_attributes=True)
