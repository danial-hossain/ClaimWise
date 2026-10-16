from app.schemas.policy import ExtractedClause
from app.services.policy_extraction_validation import validate_page_clauses


def clause(text: str, clause_id: str = "P1-C1") -> ExtractedClause:
    return ExtractedClause(
        clause_id=clause_id,
        page_number=1,
        section_path=["Section 1: Cover"],
        section_number="1",
        text=text,
        token_count=len(text.split()),
        document_hash="synthetic-document",
    )


def test_verbatim_check_tolerates_line_wrap_normalization_and_reports_uncovered_text():
    source = (
        "The company will pay for accidental damage to insured property.\n"
        "The benefit is subject to the excess shown in the schedule."
    )
    clauses = [clause("The company will pay for accidental damage to insured property.")]

    stats = validate_page_clauses(source, clauses)

    assert clauses[0].validation["verbatim_pass"] is True
    assert clauses[0].validation["verbatim_similarity"] == 1.0
    assert stats["coverage_ratio"] < 1.0
    assert any("excess shown in the schedule" in span for span in stats["uncovered_spans"])


def test_fabricated_or_reordered_clause_fails_source_verification():
    source = "The company will pay for accidental damage to insured property."
    fabricated = clause("The company will pay every claim without limits.")

    stats = validate_page_clauses(source, [fabricated])

    assert fabricated.validation["verbatim_pass"] is False
    assert fabricated.is_clause is False
    assert stats["verbatim_pass_count"] == 0
    assert stats["uncovered_spans"]


def test_empty_page_reports_zero_coverage_without_division_error():
    stats = validate_page_clauses("", [])
    assert stats["coverage_ratio"] == 0.0
    assert stats["uncovered_spans"] == []

def test_line_wrap_repair_preserves_original_page_offsets():
    source = "Acci-\ndental loss is covered. The excess is stated in the schedule."
    extracted = clause("Accidental loss is covered.")
    stats = validate_page_clauses(source, [extracted])
    assert source[extracted.validation["source_span_start"]:extracted.validation["source_span_end"]] == "Acci-\ndental loss is covered"
    assert stats["uncovered_spans"] == ["The excess is stated in the schedule"]
