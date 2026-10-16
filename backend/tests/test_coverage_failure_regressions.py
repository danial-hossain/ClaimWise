"""Generic regressions for the multi-event policy failure; no document-specific rules."""
import json
from pathlib import Path
from unittest.mock import patch
import pymupdf
import pytest
from app.schemas.policy import PolicyExtractionResult
from app.schemas.qa import RetrievedClause
from app.services.document_service import document_service, EXTRACTION_VERSION
from app.services.policy_evidence_refresh import refresh_policy_evidence
from app.services.coverage_gap_service import CoverageGapService
from app.services.qa_service import qa_service
from app.services.retrieval.evidence_context import select_section_bundles
from tests.test_evidence_context import make_clause

FIXTURES = json.loads((Path(__file__).parent / "fixtures/coverage_events.json").read_text())


def test_large_diagnostics_do_not_invalidate_a_valid_model_answer(monkeypatch):
    fixture = FIXTURES[0]
    heading, wording = fixture["sections"][0]
    source = make_clause("source", [heading], wording)
    evidence = RetrievedClause(**source.model_dump(), policy_id="p", fused_rank=1, rrf_score=1)
    service = CoverageGapService()
    event = fixture["scenario"]
    limitations = [f"Event {event}: complete section bundle omitted by context budget: group {i}" for i in range(20)]
    monkeypatch.setattr(service, "_plan_scenario_parts", lambda *args: [{"part":event,"queries":[event]}])
    monkeypatch.setattr(service, "_retrieve_scenario_evidence", lambda *args: ([evidence], limitations))
    payload = {"components":[{"part":event,"verdict":"covered","explanation":"Recorded interpretation.",
        "citations":[{"policy_id":"p","clause_id":"source","page_number":1,"exact_quote":wording}]}]}
    monkeypatch.setattr(qa_service,"_call_gemini_api",lambda **kwargs:json.dumps(payload))
    trace = []
    result = service._analyze_with_gemini("p", event, None, None, [source], source.document_hash, trace)
    assert result.components[0].verdict.value == "uncertain"
    assert len(result.components[0].dropped_material) == 20
    assert not any(entry.get("stage") == "answering" for entry in trace)


def test_malformed_response_cannot_infer_blanket_exclusion_from_mixed_evidence(monkeypatch):
    fixture = FIXTURES[0]
    sources = [make_clause(str(i), [heading], wording) for i,(heading,wording) in enumerate(fixture["sections"])]
    evidence = [RetrievedClause(**c.model_dump(),policy_id="p",fused_rank=i+1,rrf_score=1) for i,c in enumerate(sources)]
    service = CoverageGapService()
    monkeypatch.setattr(service,"_plan_scenario_parts",lambda *args:[{"part":fixture["scenario"],"queries":[]}])
    monkeypatch.setattr(service,"_retrieve_scenario_evidence",lambda *args:(evidence,[]))
    monkeypatch.setattr(qa_service,"_call_gemini_api",lambda **kwargs:'{"components":"malformed"}')
    result = service._analyze_with_gemini("p",fixture["scenario"],None,None,sources,sources[0].document_hash,[])
    assert all(c.verdict.value == "uncertain" and c.payable_amount != "0.00" for c in result.components)
    assert not result.clauses


def test_unrelated_reference_to_global_terms_does_not_change_section_scope():
    kind, scope = document_service._classify_clause_metadata(
        "This benefit covers accidental loss. Also refer to: General exclusions - pages 7-8.",
        "Property benefit", ["Property benefit"])
    assert scope == "section"


def test_whole_section_includes_sibling_subsections():
    first = make_clause("1",["Root","Benefit"],"Affirmative provision.")
    other = make_clause("2",["Root","Restrictions"],"Applicable restrictions.")
    selected, _ = select_section_bundles({"event":[first]},[first,other])
    assert selected == [first,other]
    selected, _ = select_section_bundles({"event":[first]},[first,other],max_chars=500)
    assert selected == []


def test_budget_gives_each_event_its_primary_section_before_extras():
    a = make_clause("a",["A"],"A benefit")
    extra = make_clause("extra",["Extra"],"Extra source")
    b = make_clause("b",["B"],"B benefit")
    selected, _ = select_section_bundles({"first":[a,extra],"second":[b]},[a,extra,b],max_chars=650)
    assert selected == [a,b]


def test_running_furniture_is_not_a_repeated_contract_heading():
    document = pymupdf.open()
    for number in range(3):
        page = document.new_page()
        page.insert_text((565,650),"PART 7",rotate=90)
        page.insert_text((50,60),"Section 1: Property")
        page.insert_text((50,110),"Accidental loss to insured property is covered.")
    result = document_service.process_pdf(document.tobytes(),"synthetic.pdf")
    document.close()
    assert result.clauses and not any("PART 7" in c.text for c in result.clauses)
    assert all(c.section_path[0] == "1 Property" for c in result.clauses if c.section_path)


def test_stale_extraction_refresh_preserves_identity_and_rejects_wrong_pdf():
    document = pymupdf.open(); page = document.new_page()
    page.insert_text((50,60),"Section 1: Property")
    page.insert_text((50,110),"Accidental loss to insured property is covered.")
    data = document.tobytes(); document.close()
    record = document_service.process_pdf(data,"synthetic.pdf").model_copy(update={"extraction_version":0,"policy_id":"owner-policy","user_id":"owner","persistence_mode":"persistent_db"})
    fresh = refresh_policy_evidence(record,data)
    assert fresh.extraction_version == EXTRACTION_VERSION
    assert (fresh.policy_id,fresh.user_id,fresh.uploaded_at,fresh.persistence_mode) == (record.policy_id,record.user_id,record.uploaded_at,record.persistence_mode)
    with pytest.raises(ValueError,match="hash"):
        refresh_policy_evidence(record,data+b"changed")


def test_truncated_gemini_json_is_retried_with_a_larger_output_budget():
    import httpx
    from app.services.qa_service import QAService
    fixture = json.loads((Path(__file__).parent / "fixtures/gemini_truncation.json").read_text())
    calls = []
    def transport(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200,json=fixture["partial" if len(calls)==1 else "complete"])
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        answer = QAService(http_client=client)._call_gemini_api("input","gemini-3-flash-preview","synthetic-key")
    assert answer == '{"ok":true}'
    assert calls[1]["generationConfig"]["maxOutputTokens"] > calls[0]["generationConfig"]["maxOutputTokens"]
    assert calls[0]["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "minimal"
