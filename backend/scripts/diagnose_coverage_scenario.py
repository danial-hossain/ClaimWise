"""Reproduce a fixture against its original uploaded PDF, with optional live Gemini.

Run from backend: python scripts/diagnose_coverage_scenario.py --live
No persistence writes are performed. Policy text is sent to Gemini only with --live.
"""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas.policy import PolicyExtractionResult
from app.services.document_service import document_service
from app.services.coverage_gap_service import coverage_gap_service
from app.services.qa_service import qa_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/travel_multi_event.json"))
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    path = Path("data/policy_pdfs") / (fixture["document_hash"] + ".pdf")
    policy = document_service.process_pdf(path.read_bytes(), "uploaded-policy.pdf")
    hybrid_retrieval_service.index_policy("diagnostic", policy.clauses, policy.document_hash)
    trace = []
    output = Path("data/coverage-debug"); output.mkdir(exist_ok=True)
    (output / "extraction.json").write_text(policy.model_dump_json(indent=2), encoding="utf-8")
    if args.live:
        original = qa_service._call_gemini_api
        def capture(**kwargs):
            stage = "planning" if "Prepare a retrieval plan" in kwargs["prompt"] else "selection" if "Select relevant policy sections" in kwargs["prompt"] else "answering"
            print("calling", stage, "chars", len(kwargs["prompt"]), flush=True)
            raw = original(**kwargs)
            (output / (stage + ".json")).write_text(raw, encoding="utf-8")
            return raw
        with patch.object(qa_service, "_call_gemini_api", capture):
            try:
                result = coverage_gap_service.analyze_scenario(policy_id="diagnostic", situation=fixture["scenario"],
                    policy_clauses=policy.clauses, document_hash=policy.document_hash, use_live_llm=True, retrieval_trace=trace)
            finally:
                (output / "trace.json").write_text(json.dumps(trace,indent=2),encoding="utf-8")
        (output / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        for component in result.components:
            print(json.dumps({"part":component.part,"status":component.verdict,"amount":component.payable_amount,
                "sources":[[c.clause_id,c.page_number] for c in component.citations],"explanation":component.explanation},ensure_ascii=True))
        print("limitation_count", len(result.evidence_limitations))
    else:
        parts = [{"part":event["part"], "queries":event["queries"]} for event in fixture["events"]]
        with patch.object(qa_service, "is_configured", return_value=False):
            evidence, limitations = coverage_gap_service._retrieve_scenario_evidence(parts,"diagnostic",policy.clauses,trace)
        for event in fixture["events"]:
            print(event["key"], {text: any(text.casefold() in c.text.casefold() for c in evidence) for text in event["required_text"]})
        print("selected",len(evidence),"limitations",len(limitations))
    (output / "trace.json").write_text(json.dumps(trace,indent=2),encoding="utf-8")

if __name__ == "__main__":
    main()
