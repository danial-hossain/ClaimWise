"""Deterministic reproductions of incomplete policy evidence and unsafe citations."""
import pytest
import json
import pymupdf
from app.schemas.policy import ExtractedClause
from app.schemas.qa import RetrievedClause
from app.services.coverage_gap_service import coverage_gap_service
from app.services.qa_service import QAService, CitationVerificationError
from app.services.document_service import document_service
from app.services.retrieval.hybrid_service import HybridRetrievalService
from app.services.retrieval.bm25_service import BM25RetrievalService
from app.services.retrieval.evidence_context import select_complete_evidence


@pytest.fixture
def motor_policy():
    doc = pymupdf.open()
    page = doc.new_page()
    lines = [
        "General Exclusions",
        "The Company shall not be liable in respect of:",
        "x) damage while in the care, custody and control of a motor trader including without",
        "limitation servicing, testing and repairs, except as expressly endorsed in the Schedule.",
        "xi) loss while the vehicle is left unattended after an accident without reasonable safeguards.",
        "xii) further or extended damage caused by driving before necessary repairs are completed;",
        "the original accident damage remains subject to the affirmative cover and conditions.",
        "xiii) damage caused by lack of maintenance or use in an unroadworthy condition.",
        "xiv) loss arising from an excluded competition.",
        "xv) damage occurring during a prohibited journey including",
    ]
    for index, line in enumerate(lines):
        page.insert_text((30, 35 + index * 38), line, fontsize=9)
    page = doc.new_page()
    for index, line in enumerate([
        "any resulting loss of use, subject to the conditions in the Schedule.",
        "xvi) loss caused by intentional damage.",
        "xvii) loss outside the agreed territorial limits.",
        "SECTION 2 - Insuring Agreement",
        "We cover accidental physical damage to your vehicle, subject to exclusions and the Schedule.",
    ]):
        page.insert_text((30, 35 + index * 38), line, fontsize=9)
    doc.set_page_labels([{"startpage": 0, "prefix": "Policy-", "style": "D", "firstpagenum": 7}])
    result = document_service.process_pdf(doc.tobytes(), "Synthetic_motor_wording.pdf")
    doc.close()
    assert result.status == "success"
    return result


@pytest.fixture
def search(motor_policy):
    engine = HybridRetrievalService(lexical_engine=BM25RetrievalService())
    engine.index_policy("owned", motor_policy.clauses, motor_policy.document_hash)
    return engine


def source(text, **kwargs):
    return ExtractedClause(clause_id="SEC-9", page_number=3, document_hash="synthetic", text=text, **kwargs)


def test_long_exclusion_report_preserves_entire_source_clause():
    text = "General Exclusions: The Company shall not be liable for damage. " + (
        "This condition includes the stated exceptions and associated requirements. " * 30
    ) + "xvii) Additional damage from driving before repairs is excluded; original damage is assessed separately."
    results = coverage_gap_service._policy_scenarios_from_clauses("owned", [source(text)])
    assert results
    assert results[0].clauses[0].exact_quote == text


def test_deterministic_quote_does_not_cut_off_conditions_at_240_characters():
    text = "Routine primary care office visits are covered with a $25 copayment per visit. " + (
        "The benefit remains subject to the following eligibility requirements and exceptions. " * 8
    ) + "The Schedule and endorsements determine the applicable insured period."
    clause = source(text, clause_heading="Primary Care")
    evidence = RetrievedClause(**clause.model_dump(), policy_id="owned", fused_rank=1, rrf_score=1)
    result = coverage_gap_service._deterministic_eval("Routine primary care office visit", "Member need", "", "owned", [evidence])
    assert result.clauses and result.clauses[0].exact_quote == text


def test_citation_rejects_valid_prefix_with_invented_tail():
    text = "Damage occurring during repairs is excluded subject to the express exception in the Schedule."
    evidence = RetrievedClause(**source(text).model_dump(), policy_id="owned", fused_rank=1, rrf_score=1)
    with pytest.raises(CitationVerificationError):
        QAService().validate_citations([dict(clause_id="SEC-9", page_number=3, policy_id="owned",
            exact_quote=text[:45] + " and the insurer guarantees full payment.")], [evidence], ["owned"])


def test_citation_rejects_wrong_document_even_if_clause_id_is_same():
    text = "A valid source quotation about damage and the applicable policy conditions."
    evidence = RetrievedClause(**source(text).model_dump(), policy_id="owned", fused_rank=1, rrf_score=1)
    with pytest.raises(CitationVerificationError):
        QAService().validate_citations([dict(clause_id="SEC-9", page_number=3, policy_id="foreign",
            exact_quote=text)], [evidence], ["owned"])


@pytest.mark.parametrize("query,expected", [
    ("My vehicle was damaged at a motor workshop", "limitation servicing, testing and repairs"),
    ("Damage at a garage", "limitation servicing, testing and repairs"),
    ("car left unattended after an accident", "reasonable safeguards"),
    ("vehicle abandoned after a collision", "reasonable safeguards"),
    ("driving before repairs", "original accident damage"),
    ("unsafe vehicle maintenance", "unroadworthy condition"),
])
def test_real_pdf_retrieval_preserves_operating_words(search, query, expected):
    hits, _ = search.retrieve(query, ["owned"], top_k=8)
    assert any(expected in hit.text for hit in hits)
    assert all(hit.policy_id == "owned" for hit in hits)


def test_roman_items_are_not_lost_or_merged_into_one_search_hit(motor_policy):
    for marker in ("x)", "xi)", "xii)", "xiii)", "xiv)", "xv)", "xvi)", "xvii)"):
        assert any(marker in c.text for c in motor_policy.clauses)
    workshop = next(c for c in motor_policy.clauses if "x) damage" in c.text)
    assert "limitation servicing" in workshop.text
    assert "xi)" not in workshop.text


def test_source_fragments_retrieved_across_pages_without_inventing_joined_quote(search, motor_policy):
    hits, _ = search.retrieve("prohibited journey", ["owned"], top_k=1)
    assert [hit.page_number for hit in hits] == [1, 2]
    assert "including" in hits[0].text
    assert "resulting loss of use" in hits[1].text
    for hit in hits:
        assert any(hit.text == c.text and hit.page_number == c.page_number for c in motor_policy.clauses)
    assert hits[0].printed_page_label == "Policy-7"
    assert hits[1].printed_page_label == "Policy-8"


def test_scope_and_no_match_do_not_invent_evidence(search):
    assert search.retrieve("motor workshop", ["foreign"])[0] == []
    assert search.retrieve("quasar neutrino spectroscopy", ["owned"])[0] == []


def test_new_extraction_reindexes_same_pdf_hash(search, motor_policy):
    changed = motor_policy.clauses[0].model_copy(update={"text": "Unique revised wording about interplanetary transit."})
    search.index_policy("owned", [changed], motor_policy.document_hash)
    hits, _ = search.retrieve("interplanetary", ["owned"])
    assert len(hits) == 1 and hits[0].text == changed.text


def test_budget_omits_whole_clause_and_discloses_limit():
    long = RetrievedClause(**source("Long operative clause " * 300).model_dump(), policy_id="owned", fused_rank=1, rrf_score=1)
    short = long.model_copy(update={"clause_id": "second", "text": "A complete short clause."})
    selected, limitations = select_complete_evidence([long, short, short], max_chars=500)
    assert selected == [short]
    assert limitations and "SEC-9" in limitations[0]
    assert long.text == "Long operative clause " * 300


def test_another_policy_and_language_works_without_document_specific_logic():
    engine = HybridRetrievalService(lexical_engine=BM25RetrievalService())
    clause = source("We do not pay for an automobile in a garage's custody during servicing, unless the endorsement says otherwise.")
    engine.index_policy("different", [clause], "different-file")
    hits, _ = engine.retrieve("vehicle workshop", ["different"])
    assert hits and hits[0].text == clause.text


@pytest.mark.parametrize("question", ["Workshop damage?", "Unattended after an accident?", "Driving before repairs?", "Is original damage covered subject to this exclusion?"])
def test_ask_uses_actual_retrieved_quotes_and_requires_schedule(search, question):
    hits, mode = search.retrieve(question, ["owned"], top_k=8)
    assert hits
    chosen = hits[0]
    def generator(prompt):
        assert chosen.text in prompt
        return json.dumps({"answer": "The available wording establishes conditions, but the Schedule and incident facts are required to assess cover.",
            "evidence_sufficient": False, "evidence_status": "evidence_unavailable",
            "citations": [{"clause_id": chosen.clause_id, "page_number": chosen.page_number,
                "policy_id": chosen.policy_id, "exact_quote": chosen.text}]})
    result = QAService().generate_grounded_answer(question, hits, ["owned"], retrieval_mode=mode, mock_generator=generator)
    assert not result.evidence_sufficient
    assert result.citations[0].exact_quote == chosen.text
    assert result.citations[0].page_number == chosen.page_number
    assert "Schedule" in result.answer


def test_budget_limitation_cannot_become_a_definitive_model_answer():
    huge = RetrievedClause(**source("Entire long clause. " * 2500).model_dump(), policy_id="owned", fused_rank=1, rrf_score=1)
    def no_model(prompt):
        pytest.fail("No model call is allowed when no whole clause fits")
    result = QAService().generate_grounded_answer("What is covered?", [huge], ["owned"], mock_generator=no_model)
    assert not result.evidence_sufficient and result.evidence_limitations


def test_malformed_model_boolean_is_not_truthy_evidence(search):
    hits, _ = search.retrieve("workshop", ["owned"])
    result = QAService().generate_grounded_answer("workshop", hits, ["owned"],
        mock_generator=lambda prompt: json.dumps({"answer": "Covered", "evidence_sufficient": "false", "citations": []}))
    assert not result.evidence_sufficient


def test_coverage_and_exclusion_are_both_available_for_mixed_question(search):
    hits, _ = search.retrieve("accidental vehicle damage at workshop", ["owned"], top_k=8)
    assert any("We cover accidental physical damage" in hit.text for hit in hits)
    assert any("motor trader" in hit.text for hit in hits)


def test_unsupported_ask_qualifies_missing_retrieval_without_claiming_policy_silence(search):
    hits, _ = search.retrieve("quasar neutrino spectroscopy", ["owned"])
    result = QAService().generate_grounded_answer("quasar neutrino spectroscopy", hits, ["owned"])
    assert not result.evidence_sufficient and not result.citations
    assert result.evidence_status.value == "evidence_unavailable"
    assert "does not specify" not in result.answer


def test_legacy_analysis_defaults_to_separate_empty_guidance():
    from app.schemas.coverage import CoverageGapAnalysisResult
    result = CoverageGapAnalysisResult(id="legacy", policy_id="owned", category="General",
        situation="Incident", description="", verdict="uncertain", explanation="Policy interpretation.")
    assert result.guidance == []
    assert result.model_dump()["explanation"] == "Policy interpretation."


@pytest.mark.parametrize("mode", ["valid", "uncertain", "malformed_guidance", "invented_quote"])
def test_analysis_and_guidance_model_fields_are_validated_and_saved_separately(monkeypatch, search, motor_policy, mode):
    from app.services.qa_service import qa_service
    monkeypatch.setattr("app.services.coverage_gap_service.hybrid_retrieval_service", search)
    monkeypatch.setattr(qa_service, "is_configured", lambda: True)
    hits, _ = search.retrieve("workshop vehicle damage", ["owned"], top_k=8)
    selected = next(h for h in hits if "motor trader" in h.text)
    citation = dict(clause_id=selected.clause_id, page_number=selected.page_number,
        policy_id="owned", exact_quote=selected.text)
    def generate(**kwargs):
        assert selected.text in kwargs["prompt"]
        output = {"verdict": "conditional", "explanation": "The quoted custody exclusion and Schedule exception require confirmation.",
            "conditions_summary": "Schedule endorsement required.", "insurer_questions": ["Which endorsement applies?"],
            "citations": [citation], "guidance": [{"text": "Ask your insurer to confirm the applicable Schedule endorsement.", "citations": [citation]}]}
        if mode == "uncertain": output["verdict"] = "uncertain"
        if mode == "malformed_guidance": output["guidance"] = "wrong structure"
        if mode == "invented_quote": output["citations"] = [{**citation, "exact_quote": citation["exact_quote"] + " Invented exception."}]
        return json.dumps(output)
    monkeypatch.setattr(qa_service, "_call_gemini_api", generate)
    result = coverage_gap_service.analyze_scenario("owned", "workshop vehicle damage", policy_clauses=motor_policy.clauses,
        document_hash=motor_policy.document_hash, use_live_llm=True)
    if mode in {"malformed_guidance", "invented_quote"}:
        assert result.verdict.value == "uncertain" and result.evidence_limitations
        assert not result.guidance
        return
    if mode == "uncertain":
        assert result.verdict.value == "uncertain"
    assert result.guidance and result.guidance[0].text != result.explanation
    assert result.guidance[0].citations[0].exact_quote == selected.text
    restored = type(result).model_validate_json(result.model_dump_json())
    assert restored.guidance == result.guidance
