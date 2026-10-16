"""Coverage report custom scenarios and Analysis must use the same real evaluator."""
import pytest
from app.schemas.coverage import CoverageScenarioRequest
from app.core.security import AuthenticatedUser
from app.services.coverage_gap_service import coverage_gap_service
from app.services.qa_service import qa_service
from app.api.v1.endpoints import coverage


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["A", "B"])
async def test_analysis_matches_report_for_actual_policy_and_scenario(suffix, parsed_sample_policy_records, monkeypatch):
    policy = parsed_sample_policy_records[f"policy_{suffix.lower()}"]
    scenario = "Routine primary care office visit"
    notes = "Current incident details supplied by the policyholder."
    monkeypatch.setattr(qa_service, "is_configured", lambda: True)
    def unavailable(**kwargs):
        raise RuntimeError("Synthetic model unavailable")
    monkeypatch.setattr(qa_service, "_call_gemini_api", unavailable)
    report = coverage_gap_service.generate_policy_coverage_report(
        policy.policy_id, policy.document_name, policy.clauses, policy.document_hash,
        custom_scenarios=[dict(situation=scenario, description=notes)], use_live_llm=False,
    )
    expected = report.scenarios[-1]
    monkeypatch.setattr(coverage, "get_policy_record", lambda policy_id: policy)
    saved = []
    monkeypatch.setattr(coverage.workflow_repo, "save", lambda result, user_id: saved.append((result, user_id)))
    async def audit(*args, **kwargs): pass
    monkeypatch.setattr(coverage.audit_repo, "record_event", audit)
    result = await coverage.analyze_coverage_scenario(
        CoverageScenarioRequest(policy_id=policy.policy_id, situation=scenario, description=notes),
        AuthenticatedUser(id=policy.user_id, email="synthetic@example.test", role="authenticated", tier=1),
    )
    assert result.verdict == expected.verdict
    assert result.explanation == expected.explanation
    assert result.clauses == expected.clauses
    assert result.evidence_limitations == expected.evidence_limitations
    assert result.situation == scenario and result.description == notes
    assert saved[0][1] == policy.user_id
