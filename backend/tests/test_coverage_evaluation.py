from app.benchmarks.coverage_benchmark_dataset import (
    BENCHMARK_DOCUMENT_HASH,
    BENCHMARK_POLICY_ID,
    COVERAGE_POLICY_CLAUSES,
    TABLE_EXTRACTION_FIXTURES,
    build_table_fixture_pdf,
)
from app.schemas.qa import RetrievedClause
from app.services.coverage_gap_service import CoverageGapService
from app.services.document_service import document_service
import pytest

import app.services.benchmarks.coverage_evaluation_service as coverage_evaluation_module
from app.services.benchmarks.coverage_evaluation_service import (
    CoverageEvaluationService,
    coverage_evaluation_to_markdown,
)
from app.services.retrieval.evidence_context import select_section_bundles
from app.services.retrieval.hybrid_service import HybridRetrievalService


def retrieved(clause):
    return RetrievedClause(
        **clause.model_dump(),
        policy_id=BENCHMARK_POLICY_ID,
        lexical_rank=1,
        dense_rank=None,
        fused_rank=1,
        rrf_score=0.1,
    )


def test_coverage_benchmark_passes_all_ground_truth_and_reports_stages():
    report = CoverageEvaluationService().run()

    assert report["all_passed"]
    assert report["pass_rate_pct"] == 100.0
    assert report["retrieval_recall_pct"] == 100.0
    assert set(report["stage_summary"]) == {
        "extraction", "retrieval", "evidence_context", "evaluation", "verification",
    }
    assert "Stage Summary" in coverage_evaluation_to_markdown(report)


def test_document_wide_exclusion_is_selected_for_another_section():
    camera = next(clause for clause in COVERAGE_POLICY_CLAUSES if clause.clause_id == "CAM-1")
    selected, _ = select_section_bundles(
        {"camera damage": [retrieved(camera)]},
        list(COVERAGE_POLICY_CLAUSES),
        max_chars=30000,
        document_wide_share=0.3,
    )

    selected_ids = {clause.clause_id for clause in selected}
    assert "CAM-1" in selected_ids
    assert "GLOBAL-WEAR" in selected_ids


def test_optional_cover_does_not_grant_default_affirmative_coverage():
    optional_cover = next(clause for clause in COVERAGE_POLICY_CLAUSES if clause.clause_id == "OPTIONAL-BIKE")
    result = CoverageGapService()._deterministic_eval(
        "I damaged my bicycle",
        "Property",
        None,
        BENCHMARK_POLICY_ID,
        [retrieved(optional_cover)],
    )

    assert result.verdict.value == "uncertain"
    assert result.clauses[0].clause_id == "OPTIONAL-BIKE"
    assert "selected" in (result.conditions_summary or "").lower()


def test_selected_optional_cover_is_evaluated_as_conditional():
    optional_cover = next(clause for clause in COVERAGE_POLICY_CLAUSES if clause.clause_id == "OPTIONAL-BIKE")
    result = CoverageGapService()._deterministic_eval(
        "I selected optional bicycle cover and paid the additional premium; my bicycle was damaged",
        "Property",
        None,
        BENCHMARK_POLICY_ID,
        [retrieved(optional_cover)],
    )

    assert result.verdict.value == "conditional"
    assert result.clauses[0].clause_id == "OPTIONAL-BIKE"


def test_table_limit_and_depreciation_rows_are_evaluated_together():
    fixture = next(item for item in TABLE_EXTRACTION_FIXTURES if item.vector_borders)
    extraction = document_service.process_pdf(build_table_fixture_pdf(fixture), filename="limits.pdf")
    table_clause = next(clause for clause in extraction.clauses if clause.clause_type == "table")
    camera_clause = next(clause for clause in COVERAGE_POLICY_CLAUSES if clause.clause_id == "CAM-1")

    assert tuple(tuple(row) for row in table_clause.table_rows) == fixture.expected_rows
    payable = CoverageGapService._calculate_component_payable_amount(
        "A storm damaged my camera",
        [table_clause, camera_clause],
    )
    calculation = CoverageGapService._explain_component_calculation(
        "A storm damaged my camera",
        payable,
        [table_clause, camera_clause],
    )
    assert payable == "Camera: $1,500"
    assert "$100" in calculation
    assert "10% depreciation per year" in calculation


def test_section_scoped_condition_does_not_leak_to_another_benefit():
    accommodation = next(clause for clause in COVERAGE_POLICY_CLAUSES if clause.clause_id == "HOTEL-1")
    selected, _ = select_section_bundles(
        {"extra hotel night": [retrieved(accommodation)]},
        list(COVERAGE_POLICY_CLAUSES),
        max_chars=30000,
        document_wide_share=0.3,
    )

    selected_ids = {clause.clause_id for clause in selected}
    assert "HOTEL-1" in selected_ids
    assert "CAM-REPORTING" not in selected_ids
    assert "OTHER-CONDITION" not in selected_ids


def test_visual_table_without_vector_lines_falls_back_to_text_blocks():
    fixture = next(item for item in TABLE_EXTRACTION_FIXTURES if not item.vector_borders)
    extraction = document_service.process_pdf(build_table_fixture_pdf(fixture), filename="visual-limits.pdf")
    extracted_text = "\n".join(clause.text for clause in extraction.clauses)

    assert extraction.status == "success"
    assert all(value in extracted_text for value in fixture.required_text)


def test_benchmark_attributes_extraction_exceptions_to_extraction_stage(monkeypatch):
    def extraction_failure(*args, **kwargs):
        raise RuntimeError("synthetic extraction failure")

    monkeypatch.setattr(document_service, "process_pdf", extraction_failure)
    report = CoverageEvaluationService().run()
    table_case = next(case for case in report["cases"] if case["case_id"] == "bordered-vector-table")

    assert not table_case["passed"]
    assert table_case["failure_stage"] == "extraction"


@pytest.mark.parametrize("stage", ["retrieval", "evidence_context", "evaluation", "verification"])
def test_benchmark_attributes_failures_to_their_pipeline_stage(monkeypatch, stage):
    if stage == "retrieval":
        monkeypatch.setattr(
            HybridRetrievalService,
            "retrieve",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("retrieval failure")),
        )
    elif stage == "evidence_context":
        monkeypatch.setattr(
            coverage_evaluation_module,
            "select_section_bundles",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("context failure")),
        )
    elif stage == "evaluation":
        monkeypatch.setattr(
            CoverageGapService,
            "_deterministic_eval",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("evaluation failure")),
        )
    else:
        original = CoverageGapService._deterministic_eval
        monkeypatch.setattr(
            CoverageGapService,
            "_deterministic_eval",
            lambda self, *args, **kwargs: original(self, *args, **kwargs).model_copy(update={"clauses": []}),
        )

    report = CoverageEvaluationService().run()
    case = next(item for item in report["cases"] if item["case_id"] == "emergency-room-copayment")

    assert case["failure_stage"] == stage


def test_fixture_clause_document_hash_is_stable():
    assert all(clause.document_hash == BENCHMARK_DOCUMENT_HASH for clause in COVERAGE_POLICY_CLAUSES)