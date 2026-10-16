"""Offline event replay evaluation; expectations and model recordings live in fixtures.

This exercises extraction, real two-pass retrieval/selection and Stage-2 validation
with recorded structured model output. It does not measure a live LLM's reasoning.
"""
from contextlib import ExitStack
import json
from pathlib import Path
from unittest.mock import patch
import re
import pymupdf
from app.benchmarks.coverage_benchmark_dataset import TABLE_EXTRACTION_FIXTURES, build_table_fixture_pdf
from app.services.document_service import DocumentService
from app.services.coverage_gap_service import CoverageGapService
from app.services.qa_service import qa_service
from app.services.retrieval.bm25_service import BM25RetrievalService
from app.services.retrieval.hybrid_service import HybridRetrievalService
from app.services.policy_extraction_validation import is_clause_evidence_eligible

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/coverage_events.json"


def normalize(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def error_stage(metrics):
    if metrics["extraction_accuracy"] < 1:
        return "extraction"
    if metrics["retrieval_recall"] < 1 or metrics["selection_recall"] < 1:
        return "selection"
    if any(metrics[key] < 1 for key in ("status_accuracy", "amount_accuracy", "citation_accuracy")):
        return "answering"
    return None


def fixture_pdf(fixture):
    if fixture.get("table_detector_miss"):
        return build_table_fixture_pdf(TABLE_EXTRACTION_FIXTURES[0])
    document = pymupdf.open()
    for heading, text in fixture["sections"]:
        page = document.new_page()
        page.insert_text((50, 50), heading)
        assert page.insert_textbox(pymupdf.Rect(50, 95, 540, 700), text, fontsize=11) >= 0
    data = document.tobytes(); document.close()
    return data


def evaluate_event(fixture):
    quotes = fixture["required_quotes"]
    metrics = dict.fromkeys(("extraction_accuracy", "retrieval_recall", "selection_recall",
                             "status_accuracy", "amount_accuracy", "citation_accuracy"), 0.0)
    details = {}
    with ExitStack() as stack:
        if fixture.get("table_detector_miss"):
            stack.enter_context(patch.object(DocumentService, "_extract_page_tables", return_value=[]))
        try:
            policy = DocumentService.process_pdf(fixture_pdf(fixture), "evaluation.pdf")
            eligible = [c for c in policy.clauses if is_clause_evidence_eligible(c)]
            sources = {quote: next((c for c in eligible if normalize(quote) in normalize(c.text)), None) for quote in quotes}
            metrics["extraction_accuracy"] = sum(c is not None for c in sources.values()) / len(quotes)
            details["detected_tables"] = sum(bool(c.table_rows) for c in policy.clauses)
            retriever = HybridRetrievalService(lexical_engine=BM25RetrievalService())
            stack.enter_context(patch.object(retriever._dense, "index_policy", return_value=0))
            stack.enter_context(patch.object(retriever._dense, "is_available", return_value=False))
            retriever.index_policy("evaluation", policy.clauses, policy.document_hash)
            stack.enter_context(patch("app.services.coverage_gap_service.hybrid_retrieval_service", retriever))
            service = CoverageGapService()
            parts = [{"part": fixture["scenario"], "queries": [fixture["scenario"]]}]
            stack.enter_context(patch.object(service, "_plan_scenario_parts", return_value=parts))
            citations = [{"clause_id": c.clause_id, "page_number": c.page_number,
                          "policy_id": "evaluation", "exact_quote": quote}
                         for quote, c in sources.items() if c is not None]
            component = {"part": fixture["scenario"], "explanation": "Recorded interpretation of supplied evidence.",
                         "citations": citations, **fixture["model_output"]}
            response = {"overall_explanation": "Recorded evaluation response.", "components": [component]}
            stack.enter_context(patch.object(qa_service, "_call_gemini_api", return_value=json.dumps(response)))
            trace = []
            evidence, limitations = service._retrieve_scenario_evidence(parts, "evaluation", policy.clauses, trace)
            retrieved_ids = {hit["clause_id"] for entry in trace for hit in entry.get("top_chunks", [])}
            selected_ids = {cid for entry in trace for cid in entry.get("selected_clause_ids", [])}
            metrics["retrieval_recall"] = sum(c is not None and c.clause_id in retrieved_ids for c in sources.values()) / len(quotes)
            metrics["selection_recall"] = sum(c is not None and c.clause_id in selected_ids for c in sources.values()) / len(quotes)
            stack.enter_context(patch.object(service, "_retrieve_scenario_evidence", return_value=(evidence, limitations)))
            result = service._analyze_with_gemini("evaluation", fixture["scenario"], None, None,
                                                policy.clauses, policy.document_hash, trace)
            finding = result.components[0]
            metrics["status_accuracy"] = float(finding.verdict.value == fixture["expected_status"])
            metrics["amount_accuracy"] = float(finding.payable_amount == fixture["expected_amount"])
            metrics["citation_accuracy"] = sum(any(c.verified and c.policy_id == "evaluation" and
                normalize(quote) in normalize(c.exact_quote) for c in finding.citations) for quote in quotes) / len(quotes)
            details.update(actual_status=finding.verdict.value, actual_amount=finding.payable_amount,
                           sections=result.selection_diagnostics)
        except Exception as exc:
            details["error"] = type(exc).__name__
    return {"event": fixture["id"], "metrics": metrics, "error_stage": error_stage(metrics), "details": details}


def run_event_evaluation(fixtures_path=FIXTURES):
    fixtures = json.loads(Path(fixtures_path).read_text())
    events = [evaluate_event(fixture) for fixture in fixtures]
    return {"mode": "offline_recorded_model_output", "events": events,
            "metrics": {key: sum(e["metrics"][key] for e in events) / len(events) for key in events[0]["metrics"]},
            "passed": sum(e["error_stage"] is None for e in events), "total": len(events)}
