"""Request and response contracts for evidence-grounded policy overlaps."""
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.qa import VerifiedCitation


class OverlapRequest(BaseModel):
    policy_ids: list[str] = Field(min_length=2, max_length=4)


class OverlapFinding(BaseModel):
    benefit: str = Field(min_length=1, max_length=200)
    explanation: str = Field(min_length=1, max_length=2000)
    qualifications: str = Field(min_length=1, max_length=2000)
    citations: list[VerifiedCitation] = Field(min_length=2)


class OverlapReview(BaseModel):
    policy_id: str
    policy_name: str
    reviewed_clauses: int
    total_clauses: int
    complete: bool


class OverlapResult(BaseModel):
    status: Literal['overlaps_found', 'no_verified_overlaps', 'incomplete']
    overlaps: list[OverlapFinding]
    policies: list[OverlapReview]
    rejected_findings: int
    model_used: str


