"""Automated Pytest Suite for F4 Aggregate Portfolio Management Engine & COB Optimizer.

Tests:
- Cross-Policy Overlap Detection & Cost Sharing Differentials
- Aggregate Gap Detection (Collective uninsurable domains across all policies)
- NAIC Coordination of Benefits (COB) Order of Determination Rules:
  * Subscriber / Employee vs. Dependent Rule
  * Dependent Child Birthday Rule
  * Active Employee vs. COBRA / Inactive Rule
  * Longer vs. Shorter Length of Coverage Rule
- Executive Health Scorecard (Protection Score %, Redundancy Index %)
- FastAPI Endpoints: POST /portfolio/analyze, GET /portfolio/sample, GET /portfolio/rules
- Validation constraints and audit logging
"""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.schemas.portfolio import (
    AggregateGapSeverity,
    COBRuleType,
    EmploymentStatus,
    OverlapRedundancyDegree,
    PortfolioAnalysisRequest,
    SubscriberProfile,
    SubscriberRelationship,
)
from app.services.portfolio_service import portfolio_service


@pytest.fixture
def client():
    return TestClient(app, headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "tests@example.test")})


def test_authorized_policy_map_never_falls_back_to_global_store(monkeypatch):
    def forbidden_lookup(policy_id):
        pytest.fail("An authorized policy map must be the complete access boundary")
    monkeypatch.setattr("app.api.v1.endpoints.coverage.get_policy_record", forbidden_lookup)
    with pytest.raises(KeyError):
        portfolio_service._resolve_policy("another-users-policy", {})


def test_authorized_policy_map_returns_owned_record(sample_policy_records):
    policy = sample_policy_records["policy_a"]
    assert portfolio_service._resolve_policy("policy_a", {"policy_a": policy}) is policy


@pytest.fixture(autouse=True)
def portfolio_fixtures(request):
    if not request.node.get_closest_marker("database"):
        request.getfixturevalue("sample_policy_records")


def test_portfolio_service_analysis_sample_policies():
    """Verify core analysis across Sample Policy A and Policy B."""
    req = PortfolioAnalysisRequest(
        policy_ids=["policy_a", "policy_b"],
        patient_relationship="policyholder",
        subscribers=[
            SubscriberProfile(
                policy_id="policy_a",
                relationship=SubscriberRelationship.POLICYHOLDER,
                employment_status=EmploymentStatus.ACTIVE,
            ),
            SubscriberProfile(
                policy_id="policy_b",
                relationship=SubscriberRelationship.DEPENDENT_SPOUSE,
                employment_status=EmploymentStatus.ACTIVE,
            ),
        ],
    )

    result = portfolio_service.analyze_portfolio(req)

    assert result.id.startswith("port-")
    assert len(result.analyzed_policies) == 2

    # 1. Overlaps Verification
    overlap_services = [o.service_name for o in result.overlaps]
    assert any("Primary Care" in s for s in overlap_services)
    assert any("Emergency Room" in s for s in overlap_services)
    assert any("Inpatient Hospital" in s for s in overlap_services)
    assert any("Prescription Medications" in s for s in overlap_services)

    # Check PCP differential cost sharing
    pcp_overlap = next(o for o in result.overlaps if "Primary Care" in o.service_name)
    assert pcp_overlap.redundancy_degree == OverlapRedundancyDegree.DIFFERENTIAL_COST_SHARING
    assert "$25" in pcp_overlap.policies[0].cost_sharing_summary

    # Check Inpatient dual prior auth mandate
    inpatient_overlap = next(o for o in result.overlaps if "Inpatient" in o.service_name)
    assert inpatient_overlap.redundancy_degree == OverlapRedundancyDegree.PRIOR_AUTH_ASYMMETRY
    assert all(p.prior_auth_required for p in inpatient_overlap.policies)

    # 2. Collective Aggregate Gaps Verification
    gap_services = [g.service_name for g in result.aggregate_gaps]
    assert any("Adult Routine Dental" in s for s in gap_services)
    assert any("Adult Vision Hardware" in s for s in gap_services)
    assert any("Acupuncture" in s for s in gap_services)
    assert any("Cosmetic" in s for s in gap_services)
    assert any("Long-Term Custodial" in s for s in gap_services)

    dental_gap = next(g for g in result.aggregate_gaps if "Adult Routine Dental" in g.service_name)
    assert dental_gap.severity == AggregateGapSeverity.CRITICAL
    assert len(dental_gap.silence_or_exclusion_proof) > 0
    assert any("CL-A-8.5" in cit.exact_quote or "CL-B-8.4" in cit.exact_quote or "P3-C20" in cit.clause_id or "P3-C9" in cit.clause_id for cit in dental_gap.silence_or_exclusion_proof)

    # 3. Scorecard Verification
    assert 60 <= result.scorecard.protection_score_percent <= 85
    assert 70 <= result.scorecard.redundancy_index_percent <= 100
    assert result.scorecard.total_policies == 2
    assert result.scorecard.aggregate_in_network_deductible_cents == 150000
    assert result.scorecard.aggregate_in_network_oop_max_cents == 500000

    # 4. Citations & Non-Guarantee Disclaimer
    assert "Notice: This portfolio evaluation is an informational advisory tool" in result.non_guarantee_disclaimer


def test_cob_subscriber_employee_rule():
    """Verify that employee/subscriber plan is designated Primary over dependent plan."""
    req = PortfolioAnalysisRequest(
        policy_ids=["policy_a", "policy_b"],
        patient_relationship="policyholder",
        subscribers=[
            SubscriberProfile(
                policy_id="policy_a",
                relationship=SubscriberRelationship.POLICYHOLDER,
                employment_status=EmploymentStatus.ACTIVE,
            ),
            SubscriberProfile(
                policy_id="policy_b",
                relationship=SubscriberRelationship.DEPENDENT_SPOUSE,
                employment_status=EmploymentStatus.ACTIVE,
            ),
        ],
    )
    result = portfolio_service.analyze_portfolio(req)
    assert result.cob_guidance.rule_applied == COBRuleType.SUBSCRIBER_EMPLOYEE_RULE
    assert result.cob_guidance.primary_policy_id == "policy_a"
    assert result.cob_guidance.secondary_policy_id == "policy_b"
    assert "pays PRIMARY before the plan that covers the patient as a Dependent" in result.cob_guidance.determination_reason


def test_cob_birthday_rule_dependent_child():
    """Verify NAIC Birthday Rule when claimant is a dependent child."""
    # Parent 1 (Policy A) birthday: April 10 ("04-10")
    # Parent 2 (Policy B) birthday: August 20 ("08-20")
    # Parent 1 has earlier calendar birthday -> Policy A is Primary
    req1 = PortfolioAnalysisRequest(
        policy_ids=["policy_a", "policy_b"],
        patient_relationship="dependent_child",
        subscribers=[
            SubscriberProfile(
                policy_id="policy_a",
                relationship=SubscriberRelationship.DEPENDENT_CHILD,
                birthday_month_day="04-10",
            ),
            SubscriberProfile(
                policy_id="policy_b",
                relationship=SubscriberRelationship.DEPENDENT_CHILD,
                birthday_month_day="08-20",
            ),
        ],
    )
    res1 = portfolio_service.analyze_portfolio(req1)
    assert res1.cob_guidance.rule_applied == COBRuleType.BIRTHDAY_RULE
    assert res1.cob_guidance.primary_policy_id == "policy_a"
    assert "Birthday Rule" in res1.cob_guidance.determination_reason

    # Reverse: Parent 1 (Policy A) birthday: November 15 ("11-15")
    # Parent 2 (Policy B) birthday: February 03 ("02-03")
    # Parent 2 has earlier calendar birthday -> Policy B is Primary
    req2 = PortfolioAnalysisRequest(
        policy_ids=["policy_a", "policy_b"],
        patient_relationship="dependent_child",
        subscribers=[
            SubscriberProfile(
                policy_id="policy_a",
                relationship=SubscriberRelationship.DEPENDENT_CHILD,
                birthday_month_day="11-15",
            ),
            SubscriberProfile(
                policy_id="policy_b",
                relationship=SubscriberRelationship.DEPENDENT_CHILD,
                birthday_month_day="02-03",
            ),
        ],
    )
    res2 = portfolio_service.analyze_portfolio(req2)
    assert res2.cob_guidance.rule_applied == COBRuleType.BIRTHDAY_RULE
    assert res2.cob_guidance.primary_policy_id == "policy_b"


def test_cob_active_vs_cobra_rule():
    """Verify Active employee plan is designated Primary over COBRA continuation."""
    req = PortfolioAnalysisRequest(
        policy_ids=["policy_a", "policy_b"],
        patient_relationship="policyholder",
        subscribers=[
            SubscriberProfile(
                policy_id="policy_a",
                relationship=SubscriberRelationship.POLICYHOLDER,
                employment_status=EmploymentStatus.COBRA,
            ),
            SubscriberProfile(
                policy_id="policy_b",
                relationship=SubscriberRelationship.POLICYHOLDER,
                employment_status=EmploymentStatus.ACTIVE,
            ),
        ],
    )
    result = portfolio_service.analyze_portfolio(req)
    assert result.cob_guidance.rule_applied == COBRuleType.ACTIVE_VS_INACTIVE_RULE
    assert result.cob_guidance.primary_policy_id == "policy_b"
    assert result.cob_guidance.secondary_policy_id == "policy_a"


def test_cob_longer_vs_shorter_rule():
    """Verify Longer vs Shorter Length of Coverage rule when other rules do not resolve."""
    req = PortfolioAnalysisRequest(
        policy_ids=["policy_a", "policy_b"],
        patient_relationship="policyholder",
        subscribers=[
            SubscriberProfile(
                policy_id="policy_a",
                relationship=SubscriberRelationship.POLICYHOLDER,
                employment_status=EmploymentStatus.ACTIVE,
                effective_date="2020-01-01",
            ),
            SubscriberProfile(
                policy_id="policy_b",
                relationship=SubscriberRelationship.POLICYHOLDER,
                employment_status=EmploymentStatus.ACTIVE,
                effective_date="2023-06-01",
            ),
        ],
    )
    result = portfolio_service.analyze_portfolio(req)
    assert result.cob_guidance.rule_applied == COBRuleType.LONGER_VS_SHORTER_RULE
    assert result.cob_guidance.primary_policy_id == "policy_a"


@pytest.mark.database
def test_portfolio_api_analyze_endpoint(client, persisted_sample_policy_records):
    """Test POST /api/v1/portfolio/analyze endpoint."""
    payload = {
        "policy_ids": ["policy_a", "policy_b"],
        "patient_relationship": "policyholder",
        "subscribers": [
            {
                "policy_id": "policy_a",
                "relationship": "policyholder",
                "employment_status": "active",
                "birthday_month_day": "05-15",
            },
            {
                "policy_id": "policy_b",
                "relationship": "dependent_spouse",
                "employment_status": "active",
                "birthday_month_day": "09-10",
            },
        ],
    }

    response = client.post("/api/v1/portfolio/analyze", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert "id" in data
    assert "scorecard" in data
    assert "cob_guidance" in data
    assert "overlaps" in data
    assert "aggregate_gaps" in data
    assert "key_takeaways" in data
    assert len(data["overlaps"]) >= 5
    assert len(data["aggregate_gaps"]) >= 4
    assert data["cob_guidance"]["primary_policy_id"] == "policy_a"


def test_portfolio_api_sample_endpoint(client):
    """Test GET /api/v1/portfolio/sample endpoint."""
    response = client.get("/api/v1/portfolio/sample")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["scorecard"]["total_policies"] == 2
    assert data["cob_guidance"]["rule_applied"] == "subscriber_employee_rule"
    assert len(data["key_takeaways"]) >= 3


def test_portfolio_api_rules_endpoint(client):
    """Test GET /api/v1/portfolio/rules reference endpoint."""
    response = client.get("/api/v1/portfolio/rules")
    assert response.status_code == 200, response.text
    data = response.json()

    assert "rules" in data
    assert len(data["rules"]) == 4
    rule_codes = [r["code"] for r in data["rules"]]
    assert "subscriber_employee_rule" in rule_codes
    assert "birthday_rule" in rule_codes
    assert "active_vs_inactive_rule" in rule_codes
    assert "longer_vs_shorter_rule" in rule_codes


def test_portfolio_validation_constraints(client):
    """Test rejection of insufficient policies (<2) or missing policies."""
    # Less than 2 policies
    res1 = client.post("/api/v1/portfolio/analyze", json={"policy_ids": ["policy_a"]})
    assert res1.status_code == 422 or res1.status_code == 400

    # Nonexistent policy
    res2 = client.post("/api/v1/portfolio/analyze", json={"policy_ids": ["policy_a", "nonexistent_999"]})
    assert res2.status_code == 404
