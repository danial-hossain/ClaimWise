"""Recorded replay of the reported events against verified source sections.

This is a deterministic contract test, not a live-model accuracy claim.
"""
import json
import re
from pathlib import Path
from app.schemas.policy import ExtractedClause
from app.services.coverage_gap_service import CoverageGapService
from app.services.qa_service import qa_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service

ROOT = Path(__file__).parent / "fixtures"
FIXTURE = json.loads((ROOT / "travel_multi_event.json").read_text(encoding="utf-8"))
SOURCE = json.loads((ROOT / "travel_policy_sections.json").read_text(encoding="utf-8"))


def normalized(text):
    return re.sub(r"\s+"," ",text).strip()


def test_reported_multi_event_scenario_uses_separate_provisions_and_code_amounts(monkeypatch):
    sources = [ExtractedClause.model_validate(c) for c in SOURCE["clauses"]]
    parts = [{"part":event["part"],"queries":event["queries"]} for event in FIXTURE["events"]]
    service = CoverageGapService()
    monkeypatch.setattr(service,"_plan_scenario_parts",lambda *args:parts)
    monkeypatch.setattr(hybrid_retrieval_service._dense,"index_policy",lambda *args:0)
    monkeypatch.setattr(hybrid_retrieval_service._dense,"is_available",lambda:False)
    hybrid_retrieval_service.index_policy("p",sources,SOURCE["document_hash"])
    components = []
    for event in FIXTURE["events"]:
        citations = []
        for quote in event["expected_quotes"]:
            source = next(c for c in sources if normalized(quote) in normalized(c.text))
            citations.append({"policy_id":"p","clause_id":source.clause_id,
                              "page_number":source.page_number,"exact_quote":quote})
        components.append({"part":event["part"],"verdict":event["expected_verdict"],
            "explanation":"Recorded application of the cited provision to this event.",
            "payable_inputs":event["payable_inputs"],"citations":citations})
    monkeypatch.setattr(qa_service,"_call_gemini_api",lambda **kwargs:json.dumps({"components":components}))
    trace = []
    result = service._analyze_with_gemini("p",FIXTURE["scenario"],None,None,sources,SOURCE["document_hash"],trace)
    assert len(result.components) == len(FIXTURE["events"])
    assert not result.evidence_limitations
    for event, finding in zip(FIXTURE["events"],result.components):
        assert finding.verdict.value == event["expected_verdict"]
        assert finding.payable_amount == event["expected_amount"]
        assert finding.citations and all(c.verified for c in finding.citations)
    assert len({tuple(c.clause_id for c in f.citations) for f in result.components}) == len(result.components)
    assert all(result.selection_diagnostics[event["part"]]["kept"] for event in FIXTURE["events"])
