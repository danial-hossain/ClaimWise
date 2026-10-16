"""Pydantic schemas for F2 Coverage-Gap Analysis Engine.

Evaluates user medical situations and needs against insurance policy language,
determining deterministic and grounded verdicts:
- COVERED: Service is an included benefit with standard cost-sharing.
- CONDITIONAL: Service requires Prior Authorization, step therapy, or specific clinical criteria.
- EXCLUDED: Service is barred under explicit contract exclusions.
- UNCERTAIN: Policy language is silent or ambiguous (honest abstention).
"""

from datetime import datetime, timezone
from enum import Enum
from decimal import Decimal
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.qa import PolicyEvidenceStatus, VerifiedCitation


class CoverageVerdict(str, Enum):
    """Core 4-way determination for policy coverage gaps."""
    COVERED = "covered"
    CONDITIONAL = "conditional"
    EXCLUDED = "excluded"
    UNCERTAIN = "uncertain"
    PARTIALLY_COVERED = "partially_covered"

class CoverageAssessment(str, Enum):
    POTENTIALLY_COVERED = "potentially_covered"
    PARTIALLY_COVERED = "partially_covered"
    CONDITIONAL_OR_LIMITED = "conditional_or_limited"
    POTENTIALLY_EXCLUDED = "potentially_excluded"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CoverageComponentKind(str, Enum):
    INSURED_LOSS = "insured_loss"
    POLICY_REQUIREMENT = "policy_requirement"
    SUPPORTING_DOCUMENT = "supporting_document"
    UNRESOLVED_FACT = "unresolved_fact"


class CoverageFactStatus(str, Enum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class PresetScenarioItem(BaseModel):
    """Standard predefined scenario for quick coverage evaluation."""
    id: str = Field(..., description="Unique scenario slug or ID")
    category: str = Field(..., description="Healthcare category, e.g. Emergency, Inpatient, Pharmacy")
    situation: str = Field(..., description="Human-readable title of the procedure or care need")
    description: str = Field(..., description="Detailed clinical situation description")
    keywords: List[str] = Field(default_factory=list, description="Keywords for retrieval matching")

    model_config = ConfigDict(from_attributes=True)


class CoverageScenarioRequest(BaseModel):
    """Input request to analyze a specific medical situation against a policy."""
    policy_id: str = Field(..., description="ID of the insurance policy document")
    situation: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Care situation, procedure, or relevant user context to evaluate against policy evidence",
    )
    category: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional category, e.g. 'Diagnostic', 'Surgery', 'Pharmacy'",
    )
    description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Additional clinical context or user notes (treated strictly as untrusted data)",
    )

    model_config = ConfigDict(from_attributes=True)


class GuidanceAction(BaseModel):
    """A next step tied to source evidence, separate from coverage interpretation."""
    text: str = Field(..., min_length=1)
    citations: List[VerifiedCitation] = Field(default_factory=list)

class PayableInputs(BaseModel):
    """Amounts share a currency; rate is an annual fraction, age is in years.

    Zero must be stated explicitly for a deduction that does not apply.
    """
    depreciation_method: Literal["annual", "flat", "not_applicable"] = "annual"
    claimed_amount: Optional[Decimal] = Field(None, ge=0, allow_inf_nan=False)
    item_age: Optional[Decimal] = Field(None, ge=0, allow_inf_nan=False)
    limit: Optional[Decimal] = Field(None, ge=0, allow_inf_nan=False)
    depreciation_rate: Optional[Decimal] = Field(None, ge=0, le=1, allow_inf_nan=False)
    excess: Optional[Decimal] = Field(None, ge=0, allow_inf_nan=False)
    model_config = ConfigDict(extra="forbid")


class CoverageComponentFinding(BaseModel):
    """A separately assessed material part of a user's scenario."""
    part: str = Field(..., min_length=1, max_length=500)
    kind: CoverageComponentKind = CoverageComponentKind.INSURED_LOSS
    verdict: Optional[CoverageVerdict] = None
    fact_status: Optional[CoverageFactStatus] = None
    explanation: str = Field(..., min_length=1, max_length=4000)
    coverage_provision: Optional[str] = Field(None, max_length=2000)
    restrictions: List[str] = Field(default_factory=list, max_length=12)
    conditions_and_limits: List[str] = Field(default_factory=list, max_length=12)
    missing_facts: List[str] = Field(default_factory=list, max_length=12)
    payable_amount: Optional[str] = Field(None, max_length=2000, description="Evidence-stated payable amount, limit, excess, copay, or rate")
    payable_inputs: Optional[PayableInputs] = None
    calculation: Optional[str] = Field(None, max_length=4000, description="Step-by-step payable amount calculation or deduction explanation")
    dropped_material: List[str] = Field(default_factory=list, description="Explicit diagnostics on related policy clauses or section bundles omitted from context")
    citations: List[VerifiedCitation] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_component_kind(self):
        if self.kind == CoverageComponentKind.INSURED_LOSS and self.verdict is None:
            raise ValueError("Insured-loss components require a coverage verdict")
        if self.kind != CoverageComponentKind.INSURED_LOSS and self.verdict is not None:
            raise ValueError("Requirements and facts must not receive a loss coverage verdict")
        if self.kind != CoverageComponentKind.INSURED_LOSS and self.fact_status is None:
            raise ValueError("Requirements and facts require a factual status")
        return self

    model_config = ConfigDict(from_attributes=True)


class CoverageGapAnalysisResult(BaseModel):
    """Detailed evaluation result for a medical situation against policy terms."""
    id: str = Field(..., description="Unique result identifier")
    evidence_limitations: List[str] = Field(default_factory=list)
    dropped_material: List[str] = Field(default_factory=list, description="Explicit diagnostics on omitted section bundles or clauses")
    selection_diagnostics: dict = Field(default_factory=dict)
    guidance: List[GuidanceAction] = Field(default_factory=list)
    policy_id: str = Field(..., description="ID of the analyzed policy")
    policy_name: Optional[str] = Field(None, description="Original title of the selected policy document")
    category: str = Field(..., description="Healthcare category")
    situation: str = Field(..., description="Evaluated situation title")
    description: str = Field(..., description="Context of the evaluated scenario")
    verdict: CoverageVerdict = Field(
        ...,
        description="Determination: covered, conditional, excluded, or uncertain",
    )
    evidence_status: PolicyEvidenceStatus = Field(
        default=PolicyEvidenceStatus.NOT_SPECIFIED,
        description="Evidence state; absence of evidence is not proof of exclusion",
    )
    explanation: str = Field(
        ...,
        description="Plain-language explanation grounded in contract evidence",
    )
    conditions_summary: Optional[str] = Field(
        None,
        description="Summary of prior authorization, step therapy, or limitations if conditional",
    )
    cost_sharing_summary: Optional[str] = Field(
        None,
        description="Copay, coinsurance, or deductible requirements if covered or conditional",
    )
    prior_auth_required: bool = Field(
        default=False,
        description="True if prior authorization or precertification is mandated",
    )
    clauses: List[VerifiedCitation] = Field(
        default_factory=list,
        description="Verified clause citations grounding the verdict",
    )
    insurer_questions: List[str] = Field(
        default_factory=list,
        description="High-value clarifying questions to ask the insurer",
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score of the evidence grounding",
    )
    overall_assessment: Optional[CoverageAssessment] = None
    components: List[CoverageComponentFinding] = Field(default_factory=list)
    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of evaluation",
    )

    @model_validator(mode="before")
    @classmethod
    def infer_evidence_status(cls, values):
        if not isinstance(values, dict) or "evidence_status" in values:
            return values
        verdict = values.get("verdict")
        clauses = values.get("clauses") or []
        verdict_value = verdict.value if isinstance(verdict, CoverageVerdict) else verdict
        if clauses and verdict_value == CoverageVerdict.EXCLUDED.value:
            values["evidence_status"] = PolicyEvidenceStatus.EXPLICITLY_EXCLUDED
        elif clauses and verdict_value in {CoverageVerdict.COVERED.value, CoverageVerdict.CONDITIONAL.value}:
            values["evidence_status"] = PolicyEvidenceStatus.SUPPORTED
        elif verdict_value == CoverageVerdict.UNCERTAIN.value:
            values["evidence_status"] = PolicyEvidenceStatus.NOT_SPECIFIED
        else:
            values["evidence_status"] = PolicyEvidenceStatus.EVIDENCE_UNAVAILABLE
        return values

    model_config = ConfigDict(from_attributes=True)


class CoverageGapReportResponse(BaseModel):
    """Aggregate coverage audit report across multiple standard and custom scenarios."""
    policy_id: str = Field(..., description="Policy identifier")
    policy_name: str = Field(..., description="Human-readable policy document name")
    document_hash: str = Field(..., description="SHA-256 integrity hash of policy PDF")
    total_scenarios_evaluated: int = Field(..., ge=0)
    covered_count: int = Field(..., ge=0)
    conditional_count: int = Field(..., ge=0)
    excluded_count: int = Field(..., ge=0)
    uncertain_count: int = Field(..., ge=0)
    coverage_score_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of evaluated scenarios with affirmative or conditional coverage",
    )
    scenarios: List[CoverageGapAnalysisResult] = Field(
        default_factory=list,
        description="List of scenario determinations",
    )
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
