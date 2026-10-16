"""Coverage API integration contracts for Gemini findings and safe retry behavior."""
import json

import pytest

from app.core.security import AuthenticatedUser
from app.schemas.coverage import CoverageScenarioRequest
from app.schemas.qa import RetrievedClause
from app.services.coverage_gap_service import coverage_gap_service
from app.services.qa_service import qa_service
from app.api.v1.endpoints import coverage


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["A", "B"])
async def test_analysis_persists_citation_validated_components_for_selected_policy(suffix, parsed_sample_policy_records, monkeypatch):
    policy = parsed_sample_policy_records[f"policy_{suffix.lower()}"]
    situation = "Routine primary care office visit"
    expected = coverage_gap_service.generate_policy_coverage_report(
        policy.policy_id, policy.document_name, policy.clauses, policy.document_hash,
        custom_scenarios=[{"situation": situation}], use_live_llm=False,
    ).scenarios[-1]
    assert expected.clauses
    source_by_id = {clause.clause_id: clause for clause in policy.clauses}
    retrieved = [RetrievedClause(
        clause_id=citation.clause_id,
        page_number=citation.page_number,
        policy_id=policy.policy_id,
        document_hash=policy.document_hash,
        clause_heading=source_by_id[citation.clause_id].clause_heading,
        text=source_by_id[citation.clause_id].text,
        lexical_rank=None,
        dense_rank=None,
        fused_rank=index + 1,
        rrf_score=0.1,
    ) for index, citation in enumerate(expected.clauses)]
    monkeypatch.setattr(qa_service, "is_configured", lambda: True)
    monkeypatch.setattr(coverage_gap_service, "_plan_scenario_parts", lambda *args: [{"part": situation, "queries": [situation]}])
    monkeypatch.setattr(coverage_gap_service, "_retrieve_scenario_evidence", lambda *args: (retrieved, []))
    monkeypatch.setattr(coverage, "get_policy_record", lambda policy_id: policy)
    model_response = {
        "overall_explanation": expected.explanation,
        "components": [{
            "part": situation,
            "verdict": expected.verdict.value,
            "explanation": expected.explanation,
            "coverage_provision": None,
            "restrictions": [],
            "conditions_and_limits": [],
            "missing_facts": [],
            "citations": [citation.model_dump(mode="json") for citation in expected.clauses],
        }],
        "guidance": [],
        "insurer_questions": [],
        "conditions_summary": None,
        "cost_sharing_summary": None,
        "prior_auth_required": False,
    }
    monkeypatch.setattr(qa_service, "_call_gemini_api", lambda **kwargs: json.dumps(model_response))
    saved = []
    monkeypatch.setattr(coverage.workflow_repo, "save", lambda result, user_id: saved.append((result, user_id)))

    async def audit(*args, **kwargs):
        return None

    monkeypatch.setattr(coverage.audit_repo, "record_event", audit)
    result = await coverage.analyze_coverage_scenario(
        CoverageScenarioRequest(policy_id=policy.policy_id, situation=situation),
        AuthenticatedUser(id=policy.user_id, email="synthetic@example.test", role="authenticated", tier=1),
    )

    assert result.policy_id == policy.policy_id
    assert result.policy_name == policy.document_name
    assert result.components[0].part == situation
    assert result.components[0].citations
    assert all(citation.policy_id == policy.policy_id and citation.verified for citation in result.clauses)
    for finding in result.components:
        for citation in finding.citations:
            source = source_by_id[citation.clause_id]
            assert citation.page_number == source.page_number
            assert citation.clause_heading == source.clause_heading
            assert citation.exact_quote in source.text
    assert saved[0][0].components == result.components


@pytest.mark.asyncio
async def test_analysis_returns_evidence_grounded_result_when_gemini_is_unavailable(parsed_sample_policy_records, monkeypatch):
    policy = parsed_sample_policy_records["policy_a"]
    monkeypatch.setattr(qa_service, "is_configured", lambda: False)
    monkeypatch.setattr(qa_service, "_call_gemini_api", lambda **kwargs: pytest.fail("Gemini must not be called without a configured key"))
    monkeypatch.setattr(coverage, "get_policy_record", lambda policy_id: policy)

    async def audit(*args, **kwargs):
        return None

    monkeypatch.setattr(coverage.workflow_repo, "save", lambda *args: None)
    monkeypatch.setattr(coverage.audit_repo, "record_event", audit)
    result = await coverage.analyze_coverage_scenario(
        CoverageScenarioRequest(policy_id=policy.policy_id, situation="Routine primary care office visit"),
        AuthenticatedUser(id=policy.user_id, email="synthetic@example.test", role="authenticated", tier=1),
    )

    assert result.policy_id == policy.policy_id
    assert result.evidence_limitations
    assert "AI provider did not return" in result.evidence_limitations[-1]
    assert result.clauses
