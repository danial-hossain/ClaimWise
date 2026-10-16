"""Generalization regression tests for evidence-grounded policy retrieval and Q&A.

Validates that:
1. General policy retrieval finds relevant benefit and scope clauses without hardcoding.
2. The motor policy booklet retrieves Summary of Benefits and Section I clauses.
3. Different natural phrasing of own-vehicle damage retrieves the same evidence.
4. A completely different policy (e.g. Student Health Cover) retrieves its own clauses with the same general engine.
5. Unsupported questions honestly abstain without hallucinations.
6. Multi-tier booklets explain that the Policy Schedule must be checked.
7. Cross-user document isolation is strictly preserved.
8. Page references and verbatim citations accurately correspond to retrieved source text.
"""

import json
import os
import pytest
from app.api.v1.endpoints.qa import _retrieve_qa_evidence
from app.models.domain import PolicyStatus, PolicyType
from app.schemas.policy import PolicyResponse
from app.schemas.qa import PolicyEvidenceStatus
from app.services.document_service import DocumentService
from app.services.qa_service import qa_service
from app.services.retrieval.hybrid_service import HybridRetrievalService, hybrid_retrieval_service


LIBERTY_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "policy_pdfs", "71936d117932e2994eccbd7c355cd48af34bf1860c45277800a74e79f4a56d85.pdf"
)

HEALTH_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "policy_pdfs", "0005dcd962dfdb66098e5b8bc439ca332895bf43a50b8647db6d3280202e5c00.pdf"
)


@pytest.fixture(scope="module")
def motor_policy_extraction():
    """Extract motor policy booklet once for tests."""
    with open(LIBERTY_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()
    return DocumentService.process_pdf(pdf_bytes, filename="private_car_policy.pdf", policy_id="policy-motor-001")


@pytest.fixture(scope="module")
def health_policy_extraction():
    """Extract student health cover policy booklet once for tests."""
    with open(HEALTH_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()
    return DocumentService.process_pdf(pdf_bytes, filename="student_health.pdf", policy_id="policy-health-002")


def test_motor_policy_retrieves_summary_of_benefits_and_section_i(motor_policy_extraction):
    """Verify that 'Does my policy cover accidental damage to my own car?' retrieves Summary of Benefits and Section I."""
    retriever = HybridRetrievalService()
    retriever.index_policy(
        policy_id="policy-motor-001",
        clauses=motor_policy_extraction.clauses,
        document_hash=motor_policy_extraction.document_hash,
    )

    question = "Does my policy cover accidental damage to my own car?"
    retrieved, mode = retriever.retrieve(query=question, policy_ids=["policy-motor-001"], top_k=8)

    assert len(retrieved) > 0
    # Must retrieve Section I (Page 4) and/or Summary of Benefits (Page 3)
    retrieved_pages = {c.page_number for c in retrieved}
    assert 4 in retrieved_pages or 3 in retrieved_pages, f"Expected Page 3 or Page 4 in retrieved pages: {retrieved_pages}"

    # Verify that Section I content is retrieved
    sec1_found = any("Section I" in c.text or "indemnify the Insured against accidental loss" in c.text for c in retrieved)
    sob_found = any("Scope of Cover" in c.text or "Summary of Benefits" in c.text or "Your car" in c.text for c in retrieved)
    assert sec1_found or sob_found, "Expected Section I or Summary of Benefits to be retrieved."


def test_motor_policy_alternative_wording_retrieves_evidence(motor_policy_extraction):
    """Verify that different natural phrasing of own-vehicle damage also retrieves the relevant evidence."""
    retriever = HybridRetrievalService()
    retriever.index_policy(
        policy_id="policy-motor-001",
        clauses=motor_policy_extraction.clauses,
        document_hash=motor_policy_extraction.document_hash,
    )

    alt_questions = [
        "Is damage to my own vehicle from an accident covered under this policy?",
        "Will the insurer pay for accidental vehicle damage if I crash?",
        "Does this contract indemnify against accidental collision damage to the car?",
    ]

    for q in alt_questions:
        retrieved, _ = retriever.retrieve(query=q, policy_ids=["policy-motor-001"], top_k=8)
        assert len(retrieved) > 0, f"No clauses retrieved for: {q}"
        retrieved_pages = {c.page_number for c in retrieved}
        assert 4 in retrieved_pages or 3 in retrieved_pages, f"Expected Page 3 or 4 for '{q}', got {retrieved_pages}"


def test_separate_health_policy_retrieves_own_clauses(health_policy_extraction):
    """Verify a separate policy (Health) retrieves its own clauses with the general engine without motor logic."""
    retriever = HybridRetrievalService()
    retriever.index_policy(
        policy_id="policy-health-002",
        clauses=health_policy_extraction.clauses,
        document_hash=health_policy_extraction.document_hash,
    )

    question = "Are emergency ambulance services covered under this policy?"
    retrieved, _ = retriever.retrieve(query=question, policy_ids=["policy-health-002"], top_k=8)

    assert len(retrieved) > 0
    # Must retrieve ambulance clause
    ambulance_clause = next((c for c in retrieved if "ambulance" in c.text.lower()), None)
    assert ambulance_clause is not None, "Ambulance benefit clause should be retrieved from Health Policy"
    assert ambulance_clause.page_number == 4


def test_cross_user_isolation(motor_policy_extraction, health_policy_extraction):
    """Verify users cannot retrieve clauses from another user's policy."""
    retriever = HybridRetrievalService()
    retriever.index_policy(
        policy_id="user1-motor",
        clauses=motor_policy_extraction.clauses,
        document_hash=motor_policy_extraction.document_hash,
    )
    retriever.index_policy(
        policy_id="user2-health",
        clauses=health_policy_extraction.clauses,
        document_hash=health_policy_extraction.document_hash,
    )

    # User 1 queries their motor policy for ambulance (unrelated)
    retrieved_user1, _ = retriever.retrieve(
        query="Ambulance services",
        policy_ids=["user1-motor"],
        top_k=8,
    )
    for c in retrieved_user1:
        assert c.policy_id == "user1-motor", f"Leaked clause from another policy: {c.policy_id}"
        assert "policy-health" not in c.policy_id

    # User 2 queries their health policy for motor accident
    retrieved_user2, _ = retriever.retrieve(
        query="accidental damage to my own car",
        policy_ids=["user2-health"],
        top_k=8,
    )
    for c in retrieved_user2:
        assert c.policy_id == "user2-health", f"Leaked clause from another policy: {c.policy_id}"


def test_unsupported_question_honestly_abstains(motor_policy_extraction):
    """Verify that a genuinely unsupported topic (cosmetic surgery in motor policy) honestly abstains."""
    retriever = HybridRetrievalService()
    retriever.index_policy(
        policy_id="policy-motor-001",
        clauses=motor_policy_extraction.clauses,
        document_hash=motor_policy_extraction.document_hash,
    )

    unsupported_question = "Does this policy cover elective cosmetic rhinoplasty?"
    retrieved, mode = retriever.retrieve(query=unsupported_question, policy_ids=["policy-motor-001"], top_k=5)

    response = qa_service.generate_grounded_answer(
        question=unsupported_question,
        retrieved_clauses=retrieved,
        authorized_policy_ids=["policy-motor-001"],
        retrieval_mode=mode,
        policy_clauses=motor_policy_extraction.clauses,
        extraction_status=motor_policy_extraction.status,
        has_extractable_text=motor_policy_extraction.has_extractable_text,
    )

    assert response.evidence_sufficient is False
    assert response.evidence_status in {
        PolicyEvidenceStatus.NOT_SPECIFIED,
        PolicyEvidenceStatus.EVIDENCE_UNAVAILABLE,
        PolicyEvidenceStatus.EXPLICITLY_EXCLUDED,
    }
    assert response.abstention_reason is not None


def test_schedule_dependency_and_grounded_answer(motor_policy_extraction):
    """Verify that answering motor policy question explains coverage and Policy Schedule requirement."""
    hybrid_retrieval_service.index_policy(
        policy_id="policy-motor-001",
        clauses=motor_policy_extraction.clauses,
        document_hash=motor_policy_extraction.document_hash,
    )

    question = "Does my policy cover accidental damage to my own car?"
    retrieved, mode = _retrieve_qa_evidence(
        question=question,
        search_query=question,
        policy_ids=["policy-motor-001"],
        top_k=8,
    )

    # Retrieval check: must include Section I (Page 4) or Summary of Benefits (Page 3)
    retrieved_pages = {c.page_number for c in retrieved}
    assert 4 in retrieved_pages or 3 in retrieved_pages

    sec1_clause = next((c for c in retrieved if c.page_number == 4 and "accidental loss of or damage" in c.text), None)
    assert sec1_clause is not None, "Retrieved evidence must contain Section I clause"

    def mock_llm_synthesis(prompt: str) -> str:
        # Prompt must contain the untrusted evidence excerpt from Section I
        assert sec1_clause.clause_id in prompt
        assert "accidental loss of or damage" in prompt
        return json.dumps({
            "answer": (
                "Under Section I (Insurance on the Motor Vehicle), the policy provides indemnity against "
                "accidental loss of or damage to the Motor Vehicle. However, coverage applies depending on the "
                "cover type chosen (such as Comprehensive vs Third Party), so you must verify your Policy Schedule "
                "to confirm your specific plan tier."
            ),
            "evidence_sufficient": True,
            "evidence_status": "supported",
            "abstention_reason": None,
            "clarification_question": None,
            "citations": [
                {
                    "clause_id": sec1_clause.clause_id,
                    "page_number": sec1_clause.page_number,
                    "exact_quote": "indemnify the Insured against accidental loss of or damage to the Motor Vehicle",
                    "policy_id": "policy-motor-001",
                }
            ],
        })

    response = qa_service.generate_grounded_answer(
        question=question,
        retrieved_clauses=retrieved,
        authorized_policy_ids=["policy-motor-001"],
        retrieval_mode=mode,
        policy_clauses=motor_policy_extraction.clauses,
        extraction_status=motor_policy_extraction.status,
        has_extractable_text=motor_policy_extraction.has_extractable_text,
        mock_generator=mock_llm_synthesis,
    )

    assert response.evidence_sufficient is True
    assert response.evidence_status == PolicyEvidenceStatus.SUPPORTED
    assert len(response.citations) > 0

    # Citations must match source text and have valid page numbers
    for cit in response.citations:
        assert cit.page_number in {3, 4, 5, 7}
        assert cit.verified is True
        # Quote must exist in retrieved clauses
        matching_clause = next((c for c in retrieved if c.clause_id == cit.clause_id and c.page_number == cit.page_number), None)
        assert matching_clause is not None, f"Cited clause {cit.clause_id} on page {cit.page_number} must exist in retrieved evidence"

    # Answer must distinguish comprehensive cover from other tiers or mention checking schedule
    answer_lower = response.answer.lower()
    has_tier_distinction = "comprehensive" in answer_lower or "schedule" in answer_lower
    assert has_tier_distinction, f"Answer should mention Comprehensive cover or Policy Schedule: {response.answer}"
