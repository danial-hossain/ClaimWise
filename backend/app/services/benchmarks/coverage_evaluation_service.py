"""Offline extraction, retrieval, and coverage evaluation for policy clauses."""

from typing import Any

from app.benchmarks.coverage_benchmark_dataset import (
    BENCHMARK_DOCUMENT_HASH,
    BENCHMARK_POLICY_ID,
    COVERAGE_OUTCOME_FIXTURES,
    COVERAGE_POLICY_CLAUSES,
    RETRIEVAL_FIXTURES,
    TABLE_EXTRACTION_FIXTURES,
    build_table_fixture_pdf,
)
from app.schemas.qa import RetrievedClause
from app.services.coverage_gap_service import CoverageGapService
from app.services.document_service import document_service
from app.services.retrieval.bm25_service import BM25RetrievalService
from app.services.retrieval.evidence_context import select_section_bundles
from app.services.retrieval.hybrid_service import HybridRetrievalService


STAGES = ("extraction", "retrieval", "evidence_context", "evaluation", "verification")


def _stage_check(stage: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"stage": stage, "passed": passed, "detail": detail}


def _retrieved_clauses(clauses: list[Any]) -> list[RetrievedClause]:
    return [
        RetrievedClause(
            clause_id=clause.clause_id,
            page_number=clause.page_number,
            printed_page_label=clause.printed_page_label,
            policy_id=BENCHMARK_POLICY_ID,
            document_hash=clause.document_hash or BENCHMARK_DOCUMENT_HASH,
            clause_heading=clause.clause_heading,
            text=clause.text,
            lexical_rank=None,
            dense_rank=None,
            fused_rank=index + 1,
            rrf_score=0.0,
            section_number=clause.section_number,
            section_path=clause.section_path,
            sub_heading=clause.sub_heading,
            clause_type=clause.clause_type,
            scope=clause.scope,
            cross_references=clause.cross_references,
            related_clause_ids=clause.related_clause_ids,
            table_rows=clause.table_rows,
            validation=clause.validation,
        )
        for index, clause in enumerate(clauses)
    ]


class CoverageEvaluationService:
    """Run deterministic checks and attribute each mismatch to its pipeline stage."""

    def run(self) -> dict[str, Any]:
        cases: list[dict[str, Any]] = []
        self._evaluate_extraction(cases)
        self._evaluate_retrieval(cases)
        self._evaluate_outcomes(cases)

        stage_summary = {
            stage: {
                "checks": sum(check["stage"] == stage for case in cases for check in case["checks"]),
                "passed": sum(check["stage"] == stage and check["passed"] for case in cases for check in case["checks"]),
            }
            for stage in STAGES
        }
        for summary in stage_summary.values():
            total = summary["checks"]
            summary["pass_rate_pct"] = round(summary["passed"] * 100 / total, 1) if total else 100.0

        passed = sum(case["passed"] for case in cases)
        return {
            "benchmark": "ClaimWise Coverage Evaluation",
            "case_count": len(cases),
            "passed_cases": passed,
            "failed_cases": len(cases) - passed,
            "pass_rate_pct": round(passed * 100 / len(cases), 1) if cases else 100.0,
            "retrieval_recall_pct": self._retrieval_recall_pct(cases),
            "stage_summary": stage_summary,
            "all_passed": passed == len(cases),
            "cases": cases,
        }

    @staticmethod
    def _retrieval_recall_pct(cases: list[dict[str, Any]]) -> float:
        checks = [
            check for case in cases for check in case["checks"]
            if check["stage"] == "retrieval" and "recall" in check
        ]
        total = sum(check["recall"]["expected"] for check in checks)
        found = sum(check["recall"]["found"] for check in checks)
        return round(found * 100 / total, 1) if total else 100.0

    def _add_case(self, cases: list[dict[str, Any]], case_id: str, checks: list[dict[str, Any]]) -> None:
        failed = next((check["stage"] for check in checks if not check["passed"]), None)
        cases.append({
            "case_id": case_id,
            "passed": failed is None,
            "failure_stage": failed,
            "checks": checks,
        })

    def _evaluate_extraction(self, cases: list[dict[str, Any]]) -> None:
        for fixture in TABLE_EXTRACTION_FIXTURES:
            try:
                extraction = document_service.process_pdf(
                    build_table_fixture_pdf(fixture), filename=f"{fixture.case_id}.pdf"
                )
                source_text = "\n".join(clause.text for clause in extraction.clauses)
                if fixture.expected_rows:
                    table_clauses = [clause for clause in extraction.clauses if clause.clause_type == "table"]
                    actual_rows = tuple(tuple(row) for clause in table_clauses for row in clause.table_rows)
                    passed = extraction.status == "success" and actual_rows == fixture.expected_rows
                    detail = f"Expected {len(fixture.expected_rows)} exact table rows; extracted {len(actual_rows)}."
                else:
                    passed = extraction.status == "success" and all(text in source_text for text in fixture.required_text)
                    detail = "Text-only visual table content retained in extracted text blocks." if passed else "One or more visual table cell values were not extracted."
            except Exception as exc:
                passed = False
                detail = f"Extraction raised {type(exc).__name__}."
            self._add_case(cases, fixture.case_id, [_stage_check("extraction", passed, detail)])

    def _new_retriever(self) -> HybridRetrievalService:
        retriever = HybridRetrievalService(lexical_engine=BM25RetrievalService())
        retriever.index_policy(BENCHMARK_POLICY_ID, list(COVERAGE_POLICY_CLAUSES), BENCHMARK_DOCUMENT_HASH)
        return retriever

    def _evaluate_retrieval(self, cases: list[dict[str, Any]]) -> None:
        for fixture in RETRIEVAL_FIXTURES:
            retriever = self._new_retriever()
            event_hits: dict[str, list[Any]] = {}
            event_checks = []
            event_errors = {}
            for event in fixture.events:
                try:
                    hits, _ = retriever.retrieve(event.query, [BENCHMARK_POLICY_ID], top_k=12)
                except Exception as exc:
                    hits = []
                    event_errors[event.event] = type(exc).__name__
                event_hits[event.event] = hits
                hit_ids = {hit.clause_id for hit in hits}
                expected = set(event.expected_seed_ids)
                found = expected & hit_ids
                event_checks.append((event, found, hit_ids))

            retrieval_recall = sum(len(found) for _, found, _ in event_checks) / max(
                sum(len(event.expected_seed_ids) for event in fixture.events), 1
            )
            expected_seeds = {event.event: event_hits[event.event] for event in fixture.events}
            try:
                selected, limitations = select_section_bundles(
                    expected_seeds,
                    list(COVERAGE_POLICY_CLAUSES),
                    max_chars=30000,
                    document_wide_share=0.3,
                )
            except Exception as exc:
                selected, limitations = [], [f"Evidence selection raised {type(exc).__name__}."]
            selected_ids = {clause.clause_id for clause in selected}
            expected_sections = {identifier for event in fixture.events for identifier in event.expected_section_ids}
            expected_globals = set(fixture.expected_document_wide_ids)
            context_passed = expected_sections <= selected_ids and expected_globals <= selected_ids
            context_detail = (
                "All event section bundles and document-wide clauses were retained."
                if context_passed else
                f"Missing bundle clauses: {sorted((expected_sections | expected_globals) - selected_ids)}; limitations={limitations}."
            )
            self._add_case(cases, fixture.case_id, [
                {
                    **_stage_check(
                        "retrieval",
                        retrieval_recall == 1.0,
                        "All expected event seeds were retrieved." if retrieval_recall == 1.0 and not event_errors else
                        f"Retrieval errors: {event_errors}; at least one expected event seed was not retrieved.",
                    ),
                    "recall": {
                        "found": sum(len(found) for _, found, _ in event_checks),
                        "expected": sum(len(event.expected_seed_ids) for event in fixture.events),
                    },
                },
                _stage_check("evidence_context", context_passed, context_detail),
            ])

    def _evaluate_outcomes(self, cases: list[dict[str, Any]]) -> None:
        service = CoverageGapService()
        source_by_id = {clause.clause_id: clause for clause in COVERAGE_POLICY_CLAUSES}
        for fixture in COVERAGE_OUTCOME_FIXTURES:
            checks: list[dict[str, Any]] = []
            retriever = self._new_retriever()
            expected_ids = set(fixture.expected_citation_ids)
            retrieval_error = None
            try:
                hits, _ = retriever.retrieve(fixture.query, [BENCHMARK_POLICY_ID], top_k=12)
            except Exception as exc:
                hits = []
                retrieval_error = type(exc).__name__
            retrieved_ids = {hit.clause_id for hit in hits}
            retrieval_passed = expected_ids <= retrieved_ids and retrieval_error is None
            checks.append(_stage_check(
                "retrieval", retrieval_passed,
                f"Expected citation sources {sorted(expected_ids)}; retrieved {sorted(retrieved_ids)}; error={retrieval_error}.",
            ))

            context_error = None
            try:
                selected, limitations = select_section_bundles(
                    {fixture.situation: [hit for hit in hits if hit.clause_id in expected_ids]},
                    list(COVERAGE_POLICY_CLAUSES),
                    max_chars=30000,
                    document_wide_share=0.3,
                )
            except Exception as exc:
                selected, limitations = [], []
                context_error = type(exc).__name__
            selected_ids = {clause.clause_id for clause in selected}
            context_passed = expected_ids <= selected_ids and not limitations and context_error is None
            checks.append(_stage_check(
                "evidence_context", context_passed,
                f"Selected {sorted(selected_ids)}; omitted {limitations}; error={context_error}.",
            ))

            try:
                result = service._deterministic_eval(
                    fixture.situation,
                    "Benchmark",
                    None,
                    BENCHMARK_POLICY_ID,
                    _retrieved_clauses(selected),
                )
                actual_verdict = result.verdict.value
                payable = service._calculate_component_payable_amount(fixture.situation, selected)
                calculation = service._explain_component_calculation(fixture.situation, payable, selected) if payable else None
                evaluation_passed = actual_verdict == fixture.expected_verdict
                if fixture.expected_payable_contains:
                    evaluation_passed = evaluation_passed and bool(payable and fixture.expected_payable_contains.lower() in payable.lower())
                if fixture.expected_calculation_contains:
                    evaluation_passed = evaluation_passed and bool(calculation) and all(
                        expected.lower() in calculation.lower() for expected in fixture.expected_calculation_contains
                    )
                evaluation_detail = (
                    f"verdict={actual_verdict}, payable={payable!r}, calculation={calculation!r}; "
                    f"expected verdict={fixture.expected_verdict}."
                )
                checks.append(_stage_check("evaluation", evaluation_passed, evaluation_detail))

                try:
                    citations = result.clauses
                    actual_citation_ids = {citation.clause_id for citation in citations}
                    verified = bool(citations) and expected_ids <= actual_citation_ids and all(
                        citation.policy_id == BENCHMARK_POLICY_ID
                        and citation.clause_id in source_by_id
                        and citation.exact_quote in source_by_id[citation.clause_id].text
                        for citation in citations
                    )
                    verification_detail = f"Verified source citations {sorted(actual_citation_ids)} against original clause text." if verified else f"Citations {sorted(actual_citation_ids)} failed expected-ID or exact-source verification."
                except Exception as exc:
                    verified = False
                    verification_detail = f"Citation verification raised {type(exc).__name__}."
                checks.append(_stage_check(
                    "verification", verified, verification_detail,
                ))
            except Exception as exc:
                checks.append(_stage_check("evaluation", False, f"Evaluation raised {type(exc).__name__}."))
                checks.append(_stage_check("verification", False, "No result was available to verify."))

            self._add_case(cases, fixture.case_id, checks)


def coverage_evaluation_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Coverage Evaluation Report",
        "",
        f"- Cases: {report['passed_cases']}/{report['case_count']} passed ({report['pass_rate_pct']:.1f}%)",
        f"- Retrieval recall: {report['retrieval_recall_pct']:.1f}%",
        f"- Overall: {'PASS' if report['all_passed'] else 'FAIL'}",
        "",
        "## Stage Summary",
        "",
        "| Stage | Passed | Checks | Pass rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for stage in STAGES:
        summary = report["stage_summary"][stage]
        lines.append(f"| {stage} | {summary['passed']} | {summary['checks']} | {summary['pass_rate_pct']:.1f}% |")
    lines.extend(["", "## Cases", "", "| Case | Result | Failure stage |", "| --- | --- | --- |"])
    for case in report["cases"]:
        lines.append(f"| {case['case_id']} | {'PASS' if case['passed'] else 'FAIL'} | {case['failure_stage'] or '-'} |")
        for check in case["checks"]:
            if not check["passed"]:
                lines.append(f"|  | {check['stage']}: {check['detail']} |  |")
    return "\n".join(lines) + "\n"


coverage_evaluation_service = CoverageEvaluationService()