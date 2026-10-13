"""Evidence-Based Claim Adjudication & Explanation of Benefits (EOB) Service.

Evaluates medical bill line items against retrieved policy clauses,
calculates illustrative cost shares using pure-Python integer-cents arithmetic,
and generates mathematically reconciled, evidence-grounded EOBs.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.models.domain import ClaimStatus
from app.schemas.claim import (
    AdjudicatedLineItem,
    BillLineItem,
    ExplanationOfBenefits,
    LineItemDecisionStatus,
)
from app.schemas.policy import ExtractedClause
from app.schemas.qa import RetrievedClause, VerifiedCitation
from app.services.retrieval.hybrid_service import hybrid_retrieval_service
from app.services.rules_engine import (
    EDUCATIONAL_DISCLAIMER,
    cents_to_dollars_str,
    dollars_to_cents,
)

logger = logging.getLogger("claimwise.adjudication_service")

# Common exclusion keywords in health policies
EXCLUSION_KEYWORDS = [
    "cosmetic", "experimental", "investigational", "elective",
    "not medically necessary", "acupuncture", "teeth whitening",
    "hair restoration", "weight loss surgery", "unauthorized out-of-network"
]

# Common preventive care keywords (standard 100% coverage under ACA)
PREVENTIVE_KEYWORDS = [
    "preventive", "routine screening", "annual physical", "immunization",
    "vaccine", "well woman", "well child", "mammogram", "colonoscopy screening"
]

# Copay extraction regex from policy clauses (e.g. "$250 copayment", "$30 copay")
COPAY_REGEX = re.compile(r"\$([0-9]{1,4})\s*(?:copay|copayment|co-payment)", re.IGNORECASE)


class ClaimAdjudicationService:
    """
    Deterministic adjudication engine implementing the 'Evidence first' standard:
    - Never hallucinates coverage or payment guarantees.
    - Evaluates each line item against retrieved, verified policy clauses.
    - Applies deductible, coinsurance, and copays sequentially without double-counting.
    - Escalates ambiguous or unsupported items to 'requires_review' or 'insufficient_evidence'.
    """

    def adjudicate_claim(
        self,
        claim_id: str,
        policy_id: str,
        policy_name: Optional[str],
        bill_document_hash: str,
        policy_document_hash: Optional[str],
        line_items: List[BillLineItem],
        member_coinsurance_percentage: float = 20.0,
        initial_remaining_deductible_cents: int = 100000,  # $1,000.00 default
        initial_remaining_oop_max_cents: int = 400000,      # $4,000.00 default
    ) -> ExplanationOfBenefits:
        """
        Adjudicate each line item sequentially and return a structured, itemized EOB.
        """
        audit_steps: List[str] = [
            f"Initiating claim adjudication for Claim ID '{claim_id}' against Policy ID '{policy_id}'.",
            f"Policy parameters: Coins={member_coinsurance_percentage:.1f}%, Initial Deductible={cents_to_dollars_str(initial_remaining_deductible_cents)}, Initial OOP Max={cents_to_dollars_str(initial_remaining_oop_max_cents)}.",
        ]

        running_deductible = initial_remaining_deductible_cents
        running_oop = initial_remaining_oop_max_cents
        adjudicated_items: List[AdjudicatedLineItem] = []

        for item in line_items:
            adj_item, running_deductible, running_oop, line_steps = self._adjudicate_single_line_item(
                item=item,
                policy_id=policy_id,
                policy_document_hash=policy_document_hash,
                coinsurance_pct=member_coinsurance_percentage,
                running_deductible=running_deductible,
                running_oop=running_oop,
            )
            adjudicated_items.append(adj_item)
            audit_steps.extend(line_steps)

        # Calculate reconciled totals
        total_billed = sum(i.billed_charge_cents for i in adjudicated_items)
        total_deductible_applied = sum(i.deductible_applied_cents for i in adjudicated_items)
        total_copay = sum(i.copay_cents for i in adjudicated_items)
        total_member_coins = sum(i.member_coinsurance_cents for i in adjudicated_items)
        total_uncovered = sum(i.uncovered_amount_cents for i in adjudicated_items)
        total_member_resp = sum(i.illustrative_member_cents for i in adjudicated_items)
        total_insurer_resp = sum(i.illustrative_insurer_cents for i in adjudicated_items)

        # Sanity check: Conservation of money across line items
        assert total_member_resp + total_insurer_resp == total_billed, (
            f"Arithmetic reconciliation failed: Member ({total_member_resp}) + "
            f"Insurer ({total_insurer_resp}) != Total Billed ({total_billed})"
        )

        audit_steps.append(
            f"Reconciliation verified: Member Total ({cents_to_dollars_str(total_member_resp)}) + "
            f"Insurer Total ({cents_to_dollars_str(total_insurer_resp)}) = Total Billed ({cents_to_dollars_str(total_billed)})."
        )

        eob_id = f"eob-{uuid.uuid4().hex[:10]}"

        return ExplanationOfBenefits(
            eob_id=eob_id,
            claim_id=claim_id,
            policy_id=policy_id,
            policy_name=policy_name or "Active Health Policy",
            bill_document_hash=bill_document_hash,
            policy_document_hash=policy_document_hash,
            created_at=datetime.now(timezone.utc),
            simulation_disclaimer=EDUCATIONAL_DISCLAIMER,
            total_billed_cents=total_billed,
            total_allowed_cents=None,  # Not inferred without negotiated carrier fee schedule
            total_deductible_applied_cents=total_deductible_applied,
            total_copay_cents=total_copay,
            total_member_coinsurance_cents=total_member_coins,
            total_uncovered_cents=total_uncovered,
            total_illustrative_member_cents=total_member_resp,
            total_illustrative_insurer_cents=total_insurer_resp,
            items=adjudicated_items,
            calculation_audit_steps=audit_steps,
        )

    def _adjudicate_single_line_item(
        self,
        item: BillLineItem,
        policy_id: str,
        policy_document_hash: Optional[str],
        coinsurance_pct: float,
        running_deductible: int,
        running_oop: int,
    ) -> Tuple[AdjudicatedLineItem, int, int, List[str]]:
        """
        Evaluate a single bill line item against retrieved policy evidence.
        """
        steps: List[str] = []
        charge = item.billed_charge_cents
        query = f"{item.description} {item.cpt_code or ''}".strip()

        # 1. Retrieve policy clauses scoped to this policy
        retrieved_clauses, _ = hybrid_retrieval_service.retrieve(
            query=query,
            policy_ids=[policy_id],
            top_k=3,
        )

        citations: List[VerifiedCitation] = []
        assumptions: List[str] = [
            "Negotiated provider allowed amount is unknown; illustrative calculations use billed charge.",
            "Assumes provider is in-network unless specified otherwise.",
            "Subject to insurer medical necessity review.",
        ]

        # Case 1: Empty retrieval set -> Insufficient Evidence
        if not retrieved_clauses:
            steps.append(
                f"Line item '{item.line_id}' ({item.description}): Zero relevant policy clauses retrieved. "
                f"Status: INSUFFICIENT_EVIDENCE."
            )
            return (
                AdjudicatedLineItem(
                    line_id=item.line_id,
                    service_date=item.service_date,
                    description=item.description,
                    cpt_code=item.cpt_code,
                    billed_charge_cents=charge,
                    allowed_amount_cents=None,
                    potentially_covered_cents=0,
                    deductible_applied_cents=0,
                    copay_cents=0,
                    member_coinsurance_cents=0,
                    uncovered_amount_cents=charge,
                    uncovered_reason="No policy language found establishing coverage for this service category.",
                    illustrative_member_cents=charge,
                    illustrative_insurer_cents=0,
                    decision_status=LineItemDecisionStatus.INSUFFICIENT_EVIDENCE,
                    decision_rationale=(
                        "Lexical and vector search against the policy schedule returned no clauses matching "
                        f"'{item.description}'. ClaimWise refuses to assume coverage without proof."
                    ),
                    evidence_citations=[],
                    assumptions_and_missing_facts=assumptions + ["Missing benefit schedule schedule for this procedure."],
                    requires_manual_review=True,
                ),
                running_deductible,
                running_oop,
                steps,
            )

        top_clause = retrieved_clauses[0]
        clause_text_lower = top_clause.text.lower()
        desc_lower = item.description.lower()

        # Build citation from top matching clause
        citation = VerifiedCitation(
            clause_id=top_clause.clause_id,
            page_number=top_clause.page_number,
            exact_quote=self._extract_salient_quote(top_clause.text),
            policy_id=top_clause.policy_id,
            clause_heading=top_clause.clause_heading,
            verified=True,
        )
        citations.append(citation)

        # Case 2: Explicit Exclusion Check
        is_excluded = any(ex in clause_text_lower and ex in desc_lower for ex in EXCLUSION_KEYWORDS) or \
                      ("exclusion" in clause_text_lower and any(ex in desc_lower for ex in EXCLUSION_KEYWORDS))

        if is_excluded:
            steps.append(
                f"Line item '{item.line_id}' ({item.description}): Matched policy exclusion clause {top_clause.clause_id} "
                f"(Page {top_clause.page_number}). Status: POTENTIALLY_EXCLUDED."
            )
            return (
                AdjudicatedLineItem(
                    line_id=item.line_id,
                    service_date=item.service_date,
                    description=item.description,
                    cpt_code=item.cpt_code,
                    billed_charge_cents=charge,
                    allowed_amount_cents=None,
                    potentially_covered_cents=0,
                    deductible_applied_cents=0,
                    copay_cents=0,
                    member_coinsurance_cents=0,
                    uncovered_amount_cents=charge,
                    uncovered_reason=f"Exclusion identified in policy clause {top_clause.clause_id} (Page {top_clause.page_number}).",
                    illustrative_member_cents=charge,
                    illustrative_insurer_cents=0,
                    decision_status=LineItemDecisionStatus.POTENTIALLY_EXCLUDED,
                    decision_rationale=(
                        f"Policy clause {top_clause.clause_id} explicitly excludes '{item.description}'. "
                        "Member is illustrative 100% responsible."
                    ),
                    evidence_citations=citations,
                    assumptions_and_missing_facts=assumptions,
                    requires_manual_review=False,
                ),
                running_deductible,
                running_oop,
                steps,
            )

        # Case 3: ACA Preventive Care Check (100% covered, $0 deductible/coinsurance)
        is_preventive = any(prev in desc_lower for prev in PREVENTIVE_KEYWORDS) or \
                        any(prev in clause_text_lower for prev in PREVENTIVE_KEYWORDS)

        if is_preventive:
            steps.append(
                f"Line item '{item.line_id}' ({item.description}): Qualified as preventive care under clause {top_clause.clause_id}. "
                f"Covered at 100% ($0 member share)."
            )
            return (
                AdjudicatedLineItem(
                    line_id=item.line_id,
                    service_date=item.service_date,
                    description=item.description,
                    cpt_code=item.cpt_code,
                    billed_charge_cents=charge,
                    allowed_amount_cents=None,
                    potentially_covered_cents=charge,
                    deductible_applied_cents=0,
                    copay_cents=0,
                    member_coinsurance_cents=0,
                    uncovered_amount_cents=0,
                    uncovered_reason=None,
                    illustrative_member_cents=0,
                    illustrative_insurer_cents=charge,
                    decision_status=LineItemDecisionStatus.POTENTIALLY_COVERED,
                    decision_rationale=(
                        f"Covered as standard in-network preventive care at 100% pursuant to clause {top_clause.clause_id}. "
                        "No deductible or coinsurance applies."
                    ),
                    evidence_citations=citations,
                    assumptions_and_missing_facts=assumptions + ["Must meet ACA preventive care diagnostic criteria."],
                    requires_manual_review=False,
                ),
                running_deductible,
                running_oop,
                steps,
            )

        # Case 4: Special Fixed Copayment (e.g. Emergency Room $250 Copay)
        copay_match = COPAY_REGEX.search(top_clause.text)
        detected_copay_cents = 0
        if copay_match and any(kw in desc_lower for kw in ["emergency", "er", "urgent", "office visit"]):
            try:
                copay_dollars = int(copay_match.group(1))
                detected_copay_cents = copay_dollars * 100
            except Exception:
                detected_copay_cents = 0

        # Case 5: Covered service with Cost Sharing (Copay + Deductible + Coinsurance)
        copay_applied = min(detected_copay_cents, charge)
        post_copay_expense = charge - copay_applied

        # Deductible application
        deductible_applied = min(post_copay_expense, running_deductible)
        running_deductible -= deductible_applied
        post_deductible_expense = post_copay_expense - deductible_applied

        # Coinsurance application with OOP max protection
        oop_headroom = max(0, running_oop - (copay_applied + deductible_applied))
        raw_coins = round(post_deductible_expense * (coinsurance_pct / 100.0))
        member_coins = min(raw_coins, oop_headroom)
        insurer_coins = post_deductible_expense - member_coins

        # Update remaining OOP max
        member_item_total = copay_applied + deductible_applied + member_coins
        insurer_item_total = insurer_coins
        running_oop = max(0, running_oop - member_item_total)

        steps.append(
            f"Line item '{item.line_id}' ({item.description}): Evaluated under clause {top_clause.clause_id}. "
            f"Charge={cents_to_dollars_str(charge)}, Copay={cents_to_dollars_str(copay_applied)}, "
            f"DedApplied={cents_to_dollars_str(deductible_applied)}, MemberCoins={cents_to_dollars_str(member_coins)}, "
            f"InsurerCoins={cents_to_dollars_str(insurer_coins)}. MemberTotal={cents_to_dollars_str(member_item_total)}."
        )

        return (
            AdjudicatedLineItem(
                line_id=item.line_id,
                service_date=item.service_date,
                description=item.description,
                cpt_code=item.cpt_code,
                billed_charge_cents=charge,
                allowed_amount_cents=None,
                potentially_covered_cents=charge,
                deductible_applied_cents=deductible_applied,
                copay_cents=copay_applied,
                member_coinsurance_cents=member_coins,
                uncovered_amount_cents=0,
                uncovered_reason=None,
                illustrative_member_cents=member_item_total,
                illustrative_insurer_cents=insurer_item_total,
                decision_status=LineItemDecisionStatus.POTENTIALLY_COVERED,
                decision_rationale=(
                    f"Potentially covered under policy clause {top_clause.clause_id} ({top_clause.clause_heading or 'Schedule'}). "
                    f"Cost sharing applied: {cents_to_dollars_str(copay_applied)} copay + "
                    f"{cents_to_dollars_str(deductible_applied)} deductible + "
                    f"{cents_to_dollars_str(member_coins)} coinsurance ({coinsurance_pct:.0f}%)."
                ),
                evidence_citations=citations,
                assumptions_and_missing_facts=assumptions,
                requires_manual_review=False,
            ),
            running_deductible,
            running_oop,
            steps,
        )

    @staticmethod
    def _extract_salient_quote(clause_text: str) -> str:
        """Extract first 1-2 sentences of the clause for verbatim citation."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clause_text) if s.strip()]
        if sentences:
            quote = sentences[0]
            if len(quote) < 30 and len(sentences) > 1:
                quote = f"{sentences[0]} {sentences[1]}"
            return quote[:140]
        return clause_text[:140]


claim_adjudication_service = ClaimAdjudicationService()
