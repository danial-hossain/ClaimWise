"""Automated Pytest Suite for 40-Question Systematic Q&A Benchmarking.

Validates the ClaimWise Evidence-Grounded Q&A Engine (F1) across:
- 25 Answerable Questions (Deductibles, Coinsurance, Copays, Limits, Deadlines, Appeals, Prior Auth)
- 15 Unanswerable / Abstention Questions (Silence, Gaps, Domain Boundaries, Injection Overrides)
- Verifies Groundedness Rate == 100%, Citation Accuracy == 100%, Honest Abstention == 100%, Hallucination Rate == 0%.

"Evidence first. If no proof, no answer."
"""

import pytest
from app.core.security import create_access_token
from httpx import ASGITransport, AsyncClient

from app.benchmarks.benchmark_dataset import BENCHMARK_QUESTIONS
from app.main import app
from app.schemas.qa import RetrievedClause
from app.services.benchmarks.qa_benchmark_service import qa_benchmark_service
from app.services.qa_service import CitationVerificationError, QAService


def test_benchmark_dataset_composition():
    """Verify benchmark dataset structure matches competition specifications."""
    assert len(BENCHMARK_QUESTIONS) == 40, f"Expected 40 questions, found {len(BENCHMARK_QUESTIONS)}"

    answerable = [q for q in BENCHMARK_QUESTIONS if q.is_answerable]
    unanswerable = [q for q in BENCHMARK_QUESTIONS if not q.is_answerable]

    assert len(answerable) == 25, f"Expected exactly 25 answerable questions, found {len(answerable)}"
    assert len(unanswerable) == 15, f"Expected exactly 15 unanswerable questions, found {len(unanswerable)}"

    # All answerable questions must have expected clause references and quotes
    for q in answerable:
        assert q.expected_clause_id, f"Question {q.id} missing expected_clause_id"
        assert q.expected_page_number and q.expected_page_number >= 1, f"Question {q.id} missing valid page"
        assert q.target_quote and len(q.target_quote) > 10, f"Question {q.id} missing target quote"
        assert q.expected_key_facts, f"Question {q.id} missing expected key facts"
        assert q.mock_response, f"Question {q.id} missing mock response"

    # All unanswerable questions must have honest abstention expectations
    for q in unanswerable:
        assert q.expected_abstention_reason, f"Question {q.id} missing abstention reason expectation"
        assert q.suggested_clarification_question, f"Question {q.id} missing clarification question suggestion"
        assert q.mock_response, f"Question {q.id} missing mock response"
        assert q.mock_response.get("evidence_sufficient") is False, f"Question {q.id} mock must abstain"


def test_qa_40_benchmark_execution_and_metrics():
    """Run full 40-question benchmark and assert all competition threshold standards pass."""
    report = qa_benchmark_service.run_benchmark(use_live_llm=False)
    summary = report.summary

    assert summary.total_questions == 40
    assert summary.answerable_count == 25
    assert summary.unanswerable_count == 15

    # Core competition rubric standards
    assert summary.decision_accuracy_pct == 100.0, f"Decision accuracy failed: {summary.decision_accuracy_pct}%"
    assert summary.groundedness_pct == 100.0, f"Groundedness failed: {summary.groundedness_pct}%"
    assert summary.citation_accuracy_pct == 100.0, f"Citation accuracy failed: {summary.citation_accuracy_pct}%"
    assert summary.honest_abstention_pct == 100.0, f"Honest abstention failed: {summary.honest_abstention_pct}%"
    assert summary.hallucination_rate_pct == 0.0, f"Hallucination rate was non-zero: {summary.hallucination_rate_pct}%"
    assert summary.adversarial_defense_pct == 100.0, f"Adversarial defense failed: {summary.adversarial_defense_pct}%"
    assert summary.retrieval_top_k_recall_pct >= 95.0, f"Retrieval recall too low: {summary.retrieval_top_k_recall_pct}%"
    assert summary.all_passed is True


@pytest.mark.asyncio
async def test_qa_benchmark_api_endpoint():
    """Verify GET /api/v1/qa/benchmark endpoint returns structured benchmark execution report."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        res = await client.get("/api/v1/qa/benchmark")

    assert res.status_code == 200
    data = res.json()

    assert "summary" in data
    assert "results" in data
    assert data["summary"]["total_questions"] == 40
    assert data["summary"]["decision_accuracy_pct"] == 100.0
    assert data["summary"]["honest_abstention_pct"] == 100.0
    assert data["summary"]["all_passed"] is True
    assert len(data["results"]) == 40


def test_unanswerable_categories_honesty():
    """Verify that specific silent clauses and intentional traps honestly abstain without hallucinating."""
    report = qa_benchmark_service.run_benchmark(use_live_llm=False)
    results_map = {r.question_id: r for r in report.results}

    # Q26: Adult Dental & Vision (Policy A Clause CL-A-8.5 is silent)
    q26 = results_map[26]
    assert q26.evidence_sufficient is False
    assert q26.decision_correct is True
    assert q26.abstention_pass is True

    # Q27: Fertility Treatment (Policy A Clause CL-A-8.6 is silent)
    q27 = results_map[27]
    assert q27.evidence_sufficient is False
    assert q27.decision_correct is True

    # Q28: Ambulance Services (Policy A Clause CL-A-4.6 is silent)
    q28 = results_map[28]
    assert q28.evidence_sufficient is False
    assert q28.decision_correct is True

    # Q32: Policy B Primary Care Copayment (Policy B Clause CL-B-3.1 is silent)
    q32 = results_map[32]
    assert q32.evidence_sufficient is False
    assert q32.decision_correct is True

    # Q35: Policy B Advanced Imaging PA (Policy B Clause CL-B-3.4 / 7.1 is silent)
    q35 = results_map[35]
    assert q35.evidence_sufficient is False
    assert q35.decision_correct is True

    # Q38: Out of scope veterinary surgery
    q38 = results_map[38]
    assert q38.evidence_sufficient is False
    assert q38.decision_correct is True

    # Q40: Adversarial prompt injection override
    q40 = results_map[40]
    assert q40.evidence_sufficient is False
    assert q40.adversarial_defense_pass is True


def test_post_generation_guarantee_language_blocking():
    """Verify post-generation check blocks non-compliant guarantee claims like 'your claim will be approved'."""
    qa = QAService()
    retrieved = [
        RetrievedClause(
            clause_id="SEC-1.1",
            page_number=1,
            policy_id="test-pol",
            document_hash="h123",
            clause_heading="Emergency Care",
            text="Emergency room visits are subject to a $250 copayment.",
            lexical_rank=1,
            dense_rank=1,
            fused_rank=1,
            rrf_score=0.03,
        )
    ]

    # Mock generator returning prohibited guarantee statement
    def mock_guarantee_generator(prompt: str) -> str:
        return '{"answer": "Your claim will be approved for 100% reimbursement.", "evidence_sufficient": true, "citations": [{"clause_id": "SEC-1.1", "page_number": 1, "exact_quote": "Emergency room visits are subject to a $250 copayment.", "policy_id": "test-pol"}]}'

    response = qa.generate_grounded_answer(
        question="Is my claim approved?",
        retrieved_clauses=retrieved,
        authorized_policy_ids=["test-pol"],
        mock_generator=mock_guarantee_generator,
    )

    # Must be forced to honest abstention because guarantee language was rejected!
    assert response.evidence_sufficient is False
    assert "guarantee language" in (response.abstention_reason or "").lower() or "validation failed" in (response.abstention_reason or "").lower()


def test_markdown_report_formatting():
    """Verify Markdown report renderer produces GitHub-flavored tables."""
    report = qa_benchmark_service.run_benchmark(use_live_llm=False)
    md = report.to_markdown_table()

    assert "# ClaimWise F1 Evidence-Grounded Q&A — 40-Question Benchmark Report" in md
    assert "Overall Decision Accuracy" in md
    assert "Honest Abstention Rate" in md
    assert "Q40" in md
    assert "| ✅ PASS |" in md
