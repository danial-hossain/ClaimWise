"""Unit and API tests for Multi-Policy Comparison Engine.

Tests:
- Compare 2, 3, and 4 authorized policies
- Reject < 2 policies and > 4 policies
- Reject duplicate policy IDs
- Reject unauthorized/missing policy IDs
- Missing deductible/coinsurance remain 'unknown' (never zero)
- Conflicting clauses flagged as 'conflicting'
- Citations validated against policy source chunks
- Illustrative cost simulations reconcile mathematically with rules engine
- Unknown allowed amounts marked incomplete / illustrative
- API endpoints: POST /comparisons, GET /comparisons/{id}, POST /comparisons/{id}/simulate-cost
"""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from app.api.v1.endpoints.policies import _dev_policy_store
from app.main import app
from app.schemas.comparison import (
    AttributeStatus,
    ComparisonCreateRequest,
    CostSimulationAssumption,
)
from app.schemas.policy import ExtractedClause, PolicyExtractionResult
from app.services.comparison_service import comparison_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service


def _create_mock_policy(
    policy_id: str,
    name: str,
    deductible_text: str,
    coinsurance_text: str,
    oop_text: str,
    extra_clauses: list = None,
) -> PolicyExtractionResult:
    """Helper creating mock policy extraction with synthetic clauses."""
    clauses = [
        ExtractedClause(
            clause_id="SEC-DED",
            page_number=1,
            clause_heading="Deductible Schedule",
            text=deductible_text,
            token_count=20,
            document_hash=f"hash-{policy_id}",
        ),
        ExtractedClause(
            clause_id="SEC-COINS",
            page_number=2,
            clause_heading="Coinsurance Provisions",
            text=coinsurance_text,
            token_count=20,
            document_hash=f"hash-{policy_id}",
        ),
        ExtractedClause(
            clause_id="SEC-OOP",
            page_number=2,
            clause_heading="Out of Pocket Limit",
            text=oop_text,
            token_count=20,
            document_hash=f"hash-{policy_id}",
        ),
    ]
    if extra_clauses:
        clauses.extend(extra_clauses)

    result = PolicyExtractionResult(
        document_name=f"{name}.pdf",
        document_hash=f"hash-{policy_id}",
        file_size_bytes=10240,
        total_pages=3,
        total_clauses=len(clauses),
        is_scanned=False,
        has_extractable_text=True,
        status="success",
        message="Mock parsed policy",
        pages=[],
        clauses=clauses,
        persistence_mode="development_preview",
        policy_id=policy_id,
        uploaded_at=datetime.now(timezone.utc),
    )
    # Index in hybrid retrieval
    hybrid_retrieval_service.index_policy(policy_id, clauses, result.document_hash)
    _dev_policy_store[policy_id] = result
    return result


@pytest.fixture(autouse=True)
def setup_mock_policies():
    """Populate sample policies in dev store for comparison tests."""
    p1 = _create_mock_policy(
        policy_id="test-pol-alpha",
        name="Alpha Comprehensive Silver",
        deductible_text="The individual calendar year deductible is $1,500. Family deductible is $3,000.",
        coinsurance_text="After meeting the deductible, member pays 20% coinsurance for covered services.",
        oop_text="The annual out-of-pocket maximum is $5,000 per individual.",
    )
    p2 = _create_mock_policy(
        policy_id="test-pol-beta",
        name="Beta Premium Gold",
        deductible_text="Individual annual deductible of $500 applies to all major medical services.",
        coinsurance_text="Plan pays 90%, member responsibility is 10% coinsurance.",
        oop_text="Maximum out-of-pocket limit is $3,000 per policy year.",
    )
    p3 = _create_mock_policy(
        policy_id="test-pol-gamma",
        name="Gamma Value Bronze",
        deductible_text="Individual deductible is $4,000 per calendar year.",
        coinsurance_text="Member coinsurance rate is 30% for all medical care.",
        oop_text="Out-of-pocket maximum is $8,000.",
    )
    p4 = _create_mock_policy(
        policy_id="test-pol-delta",
        name="Delta Catastrophic Basic",
        deductible_text="Annual deductible: $7,000 per member.",
        coinsurance_text="Coinsurance: 0% member pays 0% once deductible met.",
        oop_text="Out-of-pocket maximum: $7,000.",
    )
    yield
    # Cleanup
    for pid in ["test-pol-alpha", "test-pol-beta", "test-pol-gamma", "test-pol-delta", "test-pol-missing", "test-pol-conflict"]:
        _dev_policy_store.pop(pid, None)


def test_compare_two_to_four_policies():
    """Verify comparing 2, 3, and 4 authorized policies succeeds."""
    # 2 policies
    req2 = ComparisonCreateRequest(policy_ids=["test-pol-alpha", "test-pol-beta"])
    res2 = comparison_service.create_comparison(req2)
    assert len(res2.policies) == 2
    assert res2.policy_ids == ["test-pol-alpha", "test-pol-beta"]

    # 3 policies
    req3 = ComparisonCreateRequest(policy_ids=["test-pol-alpha", "test-pol-beta", "test-pol-gamma"])
    res3 = comparison_service.create_comparison(req3)
    assert len(res3.policies) == 3

    # 4 policies
    req4 = ComparisonCreateRequest(policy_ids=["test-pol-alpha", "test-pol-beta", "test-pol-gamma", "test-pol-delta"])
    res4 = comparison_service.create_comparison(req4)
    assert len(res4.policies) == 4
    assert len(res4.tradeoff_summary) > 0


def test_reject_invalid_policy_counts():
    """Verify rejection of empty lists, single policy, > 4 policies, or duplicates."""
    # < 2 policies (caught by Pydantic min_length=2)
    with pytest.raises(ValueError, match="at least 2"):
        ComparisonCreateRequest(policy_ids=["test-pol-alpha"])

    # > 4 policies (caught by Pydantic max_length=4)
    with pytest.raises(ValueError, match="at most 4"):
        ComparisonCreateRequest(
            policy_ids=["test-pol-alpha", "test-pol-beta", "test-pol-gamma", "test-pol-delta", "extra-5"]
        )

    # Duplicates reducing distinct count below 2 (caught by comparison_service)
    with pytest.raises(ValueError, match="at least 2 distinct policies"):
        comparison_service.create_comparison(
            ComparisonCreateRequest(policy_ids=["test-pol-alpha", "test-pol-alpha"])
        )


def test_reject_unauthorized_missing_policy():
    """Verify unauthorized or non-existent policy ID is rejected with KeyError."""
    with pytest.raises(KeyError, match="not found or unauthorized"):
        comparison_service.create_comparison(
            ComparisonCreateRequest(policy_ids=["test-pol-alpha", "nonexistent-policy-999"])
        )


def test_missing_values_remain_unknown_never_zero():
    """Verify policy without deductible or coinsurance clauses has status UNKNOWN (not 0)."""
    # Policy with no financial terms mentioned
    no_terms_policy = PolicyExtractionResult(
        document_name="General Notice Only.pdf",
        document_hash="hash-missing-terms",
        file_size_bytes=5000,
        total_pages=1,
        total_clauses=1,
        is_scanned=False,
        has_extractable_text=True,
        status="success",
        message="Only administrative notices",
        pages=[],
        clauses=[
            ExtractedClause(
                clause_id="SEC-ADMIN",
                page_number=1,
                clause_heading="General Disclaimer",
                text="This document provides general informational guidelines regarding membership records.",
                token_count=15,
                document_hash="hash-missing-terms",
            )
        ],
        persistence_mode="development_preview",
        policy_id="test-pol-missing",
        uploaded_at=datetime.now(timezone.utc),
    )
    _dev_policy_store["test-pol-missing"] = no_terms_policy

    res = comparison_service.create_comparison(
        ComparisonCreateRequest(policy_ids=["test-pol-alpha", "test-pol-missing"])
    )

    missing_card = next(c for c in res.policies if c.policy_id == "test-pol-missing")
    ded_attr = missing_card.attributes["deductible_individual"]
    coins_attr = missing_card.attributes["coinsurance_percentage"]

    # Must remain UNKNOWN and None, NEVER silently converted to 0
    assert ded_attr.status == AttributeStatus.UNKNOWN
    assert ded_attr.numeric_value_cents is None
    assert ded_attr.raw_value is None

    assert coins_attr.status == AttributeStatus.UNKNOWN
    assert coins_attr.numeric_value_cents is None


def test_conflicting_clauses_flagged_as_conflicting():
    """Verify opposing clauses in same policy produce CONFLICTING status."""
    conflicting_policy = PolicyExtractionResult(
        document_name="Conflicting Terms Policy.pdf",
        document_hash="hash-conflict",
        file_size_bytes=6000,
        total_pages=2,
        total_clauses=2,
        is_scanned=False,
        has_extractable_text=True,
        status="success",
        message="Policy with contradictory clauses",
        pages=[],
        clauses=[
            ExtractedClause(
                clause_id="SEC-DED-1",
                page_number=1,
                clause_heading="Section 1 Deductible",
                text="The annual individual deductible is $1,000 for all in-network care.",
                token_count=15,
                document_hash="hash-conflict",
            ),
            ExtractedClause(
                clause_id="SEC-DED-2",
                page_number=2,
                clause_heading="Section 2 Deductible Schedule",
                text="The individual deductible is $2,500 under the master schedule.",
                token_count=15,
                document_hash="hash-conflict",
            ),
        ],
        persistence_mode="development_preview",
        policy_id="test-pol-conflict",
        uploaded_at=datetime.now(timezone.utc),
    )
    _dev_policy_store["test-pol-conflict"] = conflicting_policy

    res = comparison_service.create_comparison(
        ComparisonCreateRequest(policy_ids=["test-pol-alpha", "test-pol-conflict"])
    )

    conflict_card = next(c for c in res.policies if c.policy_id == "test-pol-conflict")
    ded_attr = conflict_card.attributes["deductible_individual"]

    assert ded_attr.status == AttributeStatus.CONFLICTING
    assert "Conflicting" in (ded_attr.raw_value or "")
    assert len(ded_attr.citations) >= 2


def test_citations_validated_against_source():
    """Verify citations contain valid clause ID, page number, exact quote, and policy ID."""
    res = comparison_service.create_comparison(
        ComparisonCreateRequest(policy_ids=["test-pol-alpha", "test-pol-beta"])
    )

    alpha_card = next(c for c in res.policies if c.policy_id == "test-pol-alpha")
    ded_attr = alpha_card.attributes["deductible_individual"]
    assert ded_attr.status == AttributeStatus.VERIFIED
    assert len(ded_attr.citations) == 1

    cit = ded_attr.citations[0]
    assert cit.clause_id == "SEC-DED"
    assert cit.page_number == 1
    assert cit.policy_id == "test-pol-alpha"
    assert "1,500" in cit.exact_quote


def test_illustrative_cost_simulation_mathematical_reconciliation():
    """Verify deterministic cost modeling reconciles member + insurer = allowed amount."""
    assumptions = CostSimulationAssumption(
        service_type="Outpatient Care",
        billed_charges_cents=500000,  # $5,000.00
        allowed_amount_cents=400000,  # $4,000.00
        is_allowed_amount_known=True,
    )
    req = ComparisonCreateRequest(
        policy_ids=["test-pol-alpha", "test-pol-beta"],
        cost_assumptions=assumptions,
    )
    res = comparison_service.create_comparison(req)

    assert res.cost_simulation is not None
    sim = res.cost_simulation
    assert len(sim.policy_estimates) == 2

    # Alpha: $4,000 allowed. Ded $1,500 -> remaining $2,500 * 20% = $500 coins. Member total: $2,000 ($200,000 cents). Insurer: $2,000.
    est_alpha = next(e for e in sim.policy_estimates if e.policy_id == "test-pol-alpha")
    assert est_alpha.is_complete is True
    assert est_alpha.member_responsibility_cents == 200000
    assert est_alpha.insurer_responsibility_cents == 200000
    assert est_alpha.member_responsibility_cents + est_alpha.insurer_responsibility_cents == 400000

    # Beta: $4,000 allowed. Ded $500 -> remaining $3,500 * 10% = $350 coins. Member total: $850 ($85,000 cents). Insurer: $3,150.
    est_beta = next(e for e in sim.policy_estimates if e.policy_id == "test-pol-beta")
    assert est_beta.is_complete is True
    assert est_beta.member_responsibility_cents == 85000
    assert est_beta.insurer_responsibility_cents == 315000
    assert est_beta.member_responsibility_cents + est_beta.insurer_responsibility_cents == 400000


def test_unknown_allowed_amount_marked_incomplete():
    """Verify that when allowed amount is unknown, is_complete is False and caveats explain it."""
    assumptions = CostSimulationAssumption(
        service_type="Emergency Visit",
        billed_charges_cents=600000,
        allowed_amount_cents=None,  # Unknown
        is_allowed_amount_known=False,
    )
    req = ComparisonCreateRequest(
        policy_ids=["test-pol-alpha", "test-pol-beta"],
        cost_assumptions=assumptions,
    )
    res = comparison_service.create_comparison(req)

    assert res.cost_simulation is not None
    for est in res.cost_simulation.policy_estimates:
        assert est.is_complete is False
        assert any("allowed amount is unknown" in c.lower() for c in est.caveats_and_assumptions)


def test_comparison_api_endpoints():
    """Test FastAPI HTTP endpoints for comparison creation, retrieval, and cost recalculation."""
    client = TestClient(app)

    # 1. POST /api/v1/comparisons
    payload = {
        "policy_ids": ["test-pol-alpha", "test-pol-beta"],
        "title": "Alpha vs Beta Gold",
        "cost_assumptions": {
            "service_type": "Specialist Visit",
            "billed_charges_cents": 300000,
            "allowed_amount_cents": 250000,
            "is_allowed_amount_known": True,
        },
    }
    resp = client.post("/api/v1/comparisons", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    comp_id = data["id"]
    assert len(data["policies"]) == 2

    # 2. GET /api/v1/comparisons/{id}
    get_resp = client.get(f"/api/v1/comparisons/{comp_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == comp_id

    # 3. POST /api/v1/comparisons/{id}/simulate-cost
    new_assumptions = {
        "service_type": "Major Surgery",
        "billed_charges_cents": 1000000,
        "allowed_amount_cents": 800000,
        "is_allowed_amount_known": True,
        "network_status": "in_network",
        "prior_deductible_paid_cents": 0,
        "prior_oop_paid_cents": 0,
    }
    sim_resp = client.post(f"/api/v1/comparisons/{comp_id}/simulate-cost", json=new_assumptions)
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert len(sim_data["policy_estimates"]) == 2

    # 4. Error test: < 2 policies
    bad_resp = client.post("/api/v1/comparisons", json={"policy_ids": ["test-pol-alpha"]})
    assert bad_resp.status_code == 422 or bad_resp.status_code == 400

    # 5. Error test: Non-existent policy
    missing_resp = client.post("/api/v1/comparisons", json={"policy_ids": ["test-pol-alpha", "nonexistent-99"]})
    assert missing_resp.status_code == 404
