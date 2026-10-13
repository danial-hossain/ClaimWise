"""Unit tests for Evidence-Based Claim Adjudication & EOB Generation Service."""

import pytest
from app.schemas.claim import BillLineItem, LineItemDecisionStatus
from app.schemas.policy import ExtractedClause
from app.services.claim_adjudication_service import claim_adjudication_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service


@pytest.fixture(autouse=True)
def setup_test_policy_clauses():
    """Seed hybrid retrieval with synthetic test policy clauses."""
    policy_id = "test-policy-adjudicate-01"
    clauses = [
        ExtractedClause(
            clause_id="SEC-1.1",
            page_number=1,
            clause_heading="Emergency Department Visits",
            heading_confidence="high",
            section_number="1.1",
            text=(
                "Section 1.1: Emergency Department Visits\n"
                "Emergency room visits require a mandatory $250 copayment before standard cost sharing. "
                "Following the copayment, remaining covered expenses are subject to the annual deductible "
                "and standard 20% member coinsurance."
            ),
            token_count=35,
            document_hash="test-policy-hash-01",
        ),
        ExtractedClause(
            clause_id="SEC-2.0",
            page_number=2,
            clause_heading="Exclusions and Limitations",
            heading_confidence="high",
            section_number="2.0",
            text=(
                "Section 2.0: Exclusions and Limitations\n"
                "The following services are explicitly excluded from all coverage: "
                "cosmetic surgery, elective aesthetic treatments, acupuncture, teeth whitening, "
                "and experimental procedures not approved by the FDA."
            ),
            token_count=30,
            document_hash="test-policy-hash-01",
        ),
        ExtractedClause(
            clause_id="SEC-3.1",
            page_number=3,
            clause_heading="Preventive Care Services",
            heading_confidence="high",
            section_number="3.1",
            text=(
                "Section 3.1: Preventive Care Services\n"
                "Routine annual physical exams, routine screening mammograms, and standard immunizations "
                "are covered at 100% in-network with no deductible, copayment, or coinsurance."
            ),
            token_count=28,
            document_hash="test-policy-hash-01",
        ),
        ExtractedClause(
            clause_id="SEC-4.0",
            page_number=4,
            clause_heading="Diagnostic Radiology Services",
            heading_confidence="high",
            section_number="4.0",
            text=(
                "Section 4.0: Diagnostic Radiology Services\n"
                "Outpatient diagnostic scans, X-rays, and imaging procedures are covered in-network "
                "subject to the member annual deductible and standard 20% coinsurance."
            ),
            token_count=32,
            document_hash="test-policy-hash-01",
        ),
    ]

    hybrid_retrieval_service.index_policy(policy_id, clauses, "test-policy-hash-01")
    return policy_id


def test_adjudicate_covered_emergency_visit():
    """Verify emergency room visit evaluation applies $250 copay, deductible, and coinsurance."""
    policy_id = "test-policy-adjudicate-01"
    items = [
        BillLineItem(
            line_id="LINE-01",
            service_date="2026-03-15",
            description="Emergency Dept Visit Level 4",
            cpt_code="99284",
            billed_charge_cents=125000,  # $1,250.00
            quantity=1,
            source_page_number=1,
            raw_text_excerpt="Emergency Dept Visit Level 4 $1,250.00",
        )
    ]

    eob = claim_adjudication_service.adjudicate_claim(
        claim_id="test-claim-01",
        policy_id=policy_id,
        policy_name="Anthem Premier Health",
        bill_document_hash="test-bill-hash-01",
        policy_document_hash="test-policy-hash-01",
        line_items=items,
        member_coinsurance_percentage=20.0,
        initial_remaining_deductible_cents=50000,  # $500.00 remaining deductible
        initial_remaining_oop_max_cents=300000,    # $3,000.00 OOP max
    )

    assert len(eob.items) == 1
    item = eob.items[0]

    assert item.decision_status == LineItemDecisionStatus.POTENTIALLY_COVERED
    assert item.copay_cents == 25000  # $250.00 copay
    assert item.deductible_applied_cents == 50000  # $500.00 deductible
    # Remaining post-deductible: 1250 - 250 - 500 = $500.00. 20% coinsurance = $100.00
    assert item.member_coinsurance_cents == 10000  # $100.00
    # Member total: 250 + 500 + 100 = $850.00
    assert item.illustrative_member_cents == 85000
    # Insurer total: 500 - 100 = $400.00
    assert item.illustrative_insurer_cents == 40000

    # Math reconciliation check
    assert item.illustrative_member_cents + item.illustrative_insurer_cents == item.billed_charge_cents
    assert eob.total_illustrative_member_cents == 85000
    assert eob.total_illustrative_insurer_cents == 40000

    # Check evidence citation
    assert len(item.evidence_citations) >= 1
    assert item.evidence_citations[0].clause_id == "SEC-1.1"
    assert item.evidence_citations[0].page_number == 1


def test_adjudicate_excluded_cosmetic_service():
    """Verify cosmetic procedure is flagged POTENTIALLY_EXCLUDED with 100% member responsibility."""
    policy_id = "test-policy-adjudicate-01"
    items = [
        BillLineItem(
            line_id="LINE-01",
            service_date="2026-03-15",
            description="Elective Cosmetic Surgery Laser Resurfacing",
            cpt_code="17999",
            billed_charge_cents=80000,  # $800.00
            quantity=1,
            source_page_number=1,
            raw_text_excerpt="Elective Cosmetic Surgery $800.00",
        )
    ]

    eob = claim_adjudication_service.adjudicate_claim(
        claim_id="test-claim-02",
        policy_id=policy_id,
        policy_name="Anthem Premier Health",
        bill_document_hash="test-bill-hash-02",
        policy_document_hash="test-policy-hash-01",
        line_items=items,
    )

    item = eob.items[0]
    assert item.decision_status == LineItemDecisionStatus.POTENTIALLY_EXCLUDED
    assert item.uncovered_amount_cents == 80000
    assert item.illustrative_member_cents == 80000
    assert item.illustrative_insurer_cents == 0
    assert item.evidence_citations[0].clause_id == "SEC-2.0"
    assert item.evidence_citations[0].page_number == 2


def test_adjudicate_preventive_care_100_percent():
    """Verify preventive routine physical is covered 100% by insurer ($0 member share)."""
    policy_id = "test-policy-adjudicate-01"
    items = [
        BillLineItem(
            line_id="LINE-01",
            service_date="2026-03-15",
            description="Routine Annual Physical Exam",
            cpt_code="99396",
            billed_charge_cents=25000,  # $250.00
            quantity=1,
            source_page_number=1,
            raw_text_excerpt="Routine Annual Physical Exam $250.00",
        )
    ]

    eob = claim_adjudication_service.adjudicate_claim(
        claim_id="test-claim-03",
        policy_id=policy_id,
        policy_name="Anthem Premier Health",
        bill_document_hash="test-bill-hash-03",
        policy_document_hash="test-policy-hash-01",
        line_items=items,
        initial_remaining_deductible_cents=100000,
    )

    item = eob.items[0]
    assert item.decision_status == LineItemDecisionStatus.POTENTIALLY_COVERED
    assert item.deductible_applied_cents == 0
    assert item.copay_cents == 0
    assert item.illustrative_member_cents == 0
    assert item.illustrative_insurer_cents == 25000
    assert item.evidence_citations[0].clause_id == "SEC-3.1"


def test_adjudicate_insufficient_evidence_unsupported_service():
    """Verify unknown or unsupported service triggers honest INSUFFICIENT_EVIDENCE status."""
    policy_id = "test-policy-adjudicate-01"
    items = [
        BillLineItem(
            line_id="LINE-01",
            service_date="2026-03-15",
            description="Specialty Equine Therapy Session",
            cpt_code="97799",
            billed_charge_cents=35000,
            quantity=1,
            source_page_number=1,
            raw_text_excerpt="Equine Therapy $350.00",
        )
    ]

    # Temporarily query against a policy ID with no matching clauses
    empty_policy_id = "policy-with-no-clauses"
    eob = claim_adjudication_service.adjudicate_claim(
        claim_id="test-claim-04",
        policy_id=empty_policy_id,
        policy_name="Empty Policy",
        bill_document_hash="test-bill-hash-04",
        policy_document_hash="test-policy-hash-01",
        line_items=items,
    )

    item = eob.items[0]
    assert item.decision_status == LineItemDecisionStatus.INSUFFICIENT_EVIDENCE
    assert item.requires_manual_review is True
    assert item.uncovered_amount_cents == 35000
    assert item.illustrative_member_cents == 35000
    assert item.illustrative_insurer_cents == 0


def test_adjudicate_sequential_deductible_conservation():
    """Verify multi-item claim drains deductible sequentially without double-counting."""
    policy_id = "test-policy-adjudicate-01"
    items = [
        BillLineItem(
            line_id="LINE-01",
            service_date="2026-03-15",
            description="Emergency Dept Visit Level 4",
            cpt_code="99284",
            billed_charge_cents=60000,  # $600.00 (copay $250 -> $350 rem charge)
            quantity=1,
            source_page_number=1,
            raw_text_excerpt="ER Visit $600.00",
        ),
        BillLineItem(
            line_id="LINE-02",
            service_date="2026-03-15",
            description="Outpatient Diagnostic Radiology Scan",
            cpt_code="71046",
            billed_charge_cents=40000,  # $400.00
            quantity=1,
            source_page_number=1,
            raw_text_excerpt="Scan $400.00",
        ),
    ]

    eob = claim_adjudication_service.adjudicate_claim(
        claim_id="test-claim-05",
        policy_id=policy_id,
        policy_name="Anthem Premier Health",
        bill_document_hash="test-bill-hash-05",
        policy_document_hash="test-policy-hash-01",
        line_items=items,
        member_coinsurance_percentage=20.0,
        initial_remaining_deductible_cents=50000,  # $500.00 deductible
    )

    # Item 1: charge 600. Copay 250 -> post-copay 350.
    # Deductible paid: min(350, 500) = 350. Remaining deductible = 150.
    assert eob.items[0].deductible_applied_cents == 35000
    assert eob.items[0].copay_cents == 25000

    # Item 2: charge 400. (no copay since not ER visit)
    # Deductible paid: min(400, 150) = 150. Remaining deductible = 0.
    # Post-deductible expense: 400 - 150 = 250.
    # Coinsurance: 20% of 250 = 50. Insurer coinsurance = 200.
    assert eob.items[1].deductible_applied_cents == 15000
    assert eob.items[1].member_coinsurance_cents == 5000
    assert eob.items[1].illustrative_insurer_cents == 20000

    # Total deductible applied across items: 350 + 150 = $500.00 (exact initial deductible balance)
    assert eob.total_deductible_applied_cents == 50000

    # Total conservation:
    assert eob.total_illustrative_member_cents + eob.total_illustrative_insurer_cents == eob.total_billed_cents
