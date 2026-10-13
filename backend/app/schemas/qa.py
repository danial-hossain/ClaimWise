"""Pydantic schemas for Hybrid Retrieval and Evidence-Grounded Q&A."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RetrievedClause(BaseModel):
    """Granular clause retrieved by hybrid or lexical search."""
    clause_id: str = Field(..., description="Clause identifier, e.g. SEC-1.1 or P1-C2")
    page_number: int = Field(..., ge=1, description="One-based document page number")
    policy_id: str = Field(..., description="Unique ID of source policy")
    document_hash: str = Field(..., description="SHA-256 hash of original PDF document")
    clause_heading: Optional[str] = Field(None, description="Heading or title if detected")
    text: str = Field(..., description="Verbatim extracted text of the clause")
    lexical_rank: Optional[int] = Field(None, description="1-based BM25 rank if matched")
    dense_rank: Optional[int] = Field(None, description="1-based dense vector rank if matched")
    fused_rank: int = Field(..., description="1-based Reciprocal Rank Fusion rank")
    rrf_score: float = Field(..., description="Calculated RRF score")

    model_config = ConfigDict(from_attributes=True)


class VerifiedCitation(BaseModel):
    """Citation verified deterministically against source document clauses."""
    clause_id: str = Field(..., description="Cited clause identifier")
    page_number: int = Field(..., ge=1, description="Cited one-based page number")
    exact_quote: str = Field(..., description="Verbatim quoted excerpt from source text")
    policy_id: str = Field(..., description="Source policy ID")
    clause_heading: Optional[str] = Field(None, description="Clause section heading")
    verified: bool = Field(default=True, description="Whether citation passed post-generation verification")

    model_config = ConfigDict(from_attributes=True)


class QARequest(BaseModel):
    """Request payload for evidence-grounded policy inquiry."""
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Insurance coverage or policy inquiry question",
    )
    policy_id: str = Field(..., description="ID of the policy document to query")

    model_config = ConfigDict(from_attributes=True)


class QAResponse(BaseModel):
    """Response containing grounded answer and verified citations."""
    question: str
    answer: str
    evidence_sufficient: bool = Field(
        ...,
        description="True if policy evidence definitively answered the question; False if abstained",
    )
    abstention_reason: Optional[str] = Field(
        None,
        description="Explanation when evidence is insufficient, conflicting, or missing",
    )
    clarification_question: Optional[str] = Field(
        None,
        description="Suggested follow-up question for the insurer or user when proof is absent",
    )
    citations: List[VerifiedCitation] = Field(
        default_factory=list,
        description="Verified citations with exact clause quotes and page numbers",
    )
    retrieval_mode: str = Field(
        ...,
        description="Retrieval engine mode: 'hybrid' (BM25 + dense) or 'degraded_bm25_only'",
    )
    retrieved_evidence: List[RetrievedClause] = Field(
        default_factory=list,
        description="Top-ranked evidence clauses evaluated by the system",
    )
    model_used: str = Field(..., description="Name of LLM model used for synthesis")
    latency_ms: int = Field(..., ge=0, description="Total request latency in milliseconds")
    created_at: datetime = Field(..., description="UTC timestamp of response generation")

    model_config = ConfigDict(from_attributes=True)
