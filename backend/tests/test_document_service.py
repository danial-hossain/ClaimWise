"""Unit tests for PDF Document Processing Service."""

import pytest
import pymupdf
from app.services.document_service import DocumentProcessingError, document_service


def create_synthetic_pdf(pages_text: list[list[str]]) -> bytes:
    """Helper to generate in-memory synthetic test PDF bytes."""
    doc = pymupdf.open()
    for page_blocks in pages_text:
        page = doc.new_page()
        y_pos = 70
        for block in page_blocks:
            page.insert_text((50, y_pos), block)
            y_pos += 80
    data = doc.tobytes()
    doc.close()
    return data


def test_valid_single_page_pdf_extraction():
    """Test extracting structured clauses from a single-page PDF."""
    pdf_bytes = create_synthetic_pdf([
        [
            "SECTION 1.1: General Benefit Provisions\nAll in-network treatments are covered.",
            "2.1 Deductible Requirements\nA $500 annual deductible applies.",
        ]
    ])

    result = document_service.process_pdf(pdf_bytes, filename="single_page.pdf")

    assert result.status == "success"
    assert result.total_pages == 1
    assert result.total_clauses == 2
    assert result.is_scanned is False
    assert result.has_extractable_text is True
    assert len(result.document_hash) == 64  # SHA-256 hex length
    assert result.clauses[0].page_number == 1
    assert result.clauses[0].clause_id == "SEC-1.1"
    assert result.clauses[0].heading_confidence == "high"
    assert result.clauses[0].validation["verbatim_pass"] is True
    assert result.clauses[0].clause_type == "benefit"
    assert result.clauses[0].section_path
    assert result.clauses[1].page_number == 1
    assert result.clauses[1].clause_id == "SEC-2.1"
    assert result.extraction_validation.verbatim_pass_rate == 1.0
    assert result.pages[0].extraction_coverage_ratio > 0


def test_multiple_page_pdf_page_numbering():
    """Verify 1-based page numbering across multiple pages."""
    pdf_bytes = create_synthetic_pdf([
        ["Section 1.0: Introduction\nWelcome to your policy."],
        ["Section 2.0: Schedule of Benefits\nBenefit table details."],
        ["Section 3.0: Exclusions and Limitations\nNon-covered conditions."],
    ])

    result = document_service.process_pdf(pdf_bytes, filename="three_pages.pdf")

    assert result.status == "success"
    assert result.total_pages == 3
    assert len(result.pages) == 3

    # Check 1-based page numbers
    assert result.pages[0].page_number == 1
    assert result.pages[1].page_number == 2
    assert result.pages[2].page_number == 3

    assert result.clauses[0].page_number == 1
    assert result.clauses[1].page_number == 2
    assert result.clauses[2].page_number == 3


def test_clause_metadata_and_heuristic_headings():
    """Test detection of heuristic headings vs unlabelled paragraphs."""
    pdf_bytes = create_synthetic_pdf([
        [
            "COVERED MEDICAL EXPENSES\nInpatient hospital care is covered at 80%.",
            "Random unlabelled paragraph without any title or section marker.",
        ]
    ])

    result = document_service.process_pdf(pdf_bytes, filename="headings.pdf")
    assert result.status == "success"
    assert len(result.clauses) == 2

    c1 = result.clauses[0]
    assert c1.clause_heading == "COVERED MEDICAL EXPENSES"
    assert c1.heading_confidence == "heuristic"

    c2 = result.clauses[1]
    assert c2.clause_heading is None
    assert c2.heading_confidence == "none"
    assert c2.clause_id.startswith("P1-C")


def test_hierarchy_scope_type_and_cross_reference_are_derived_from_source_structure():
    pdf_bytes = create_synthetic_pdf([[
        "Section 1: Property Cover",
        "1.1 Accidental Damage",
        "The insurer will pay for accidental damage to insured property subject to the applicable schedule.",
        "Section 2: General Terms",
        "This exclusion applies to all sections of the policy. See section 1.1 for the covered property definition.",
    ]])

    result = document_service.process_pdf(pdf_bytes, filename="hierarchy.pdf")
    benefit = next(clause for clause in result.clauses if "accidental damage to insured property" in clause.text.lower())
    global_clause = next(clause for clause in result.clauses if "applies to all sections" in clause.text.lower())

    assert "1 Property Cover" in benefit.section_path
    assert benefit.sub_heading == "1.1 Accidental Damage"
    assert benefit.clause_type in {"benefit", "condition"}
    assert global_clause.scope == "document_wide"
    assert global_clause.related_clause_ids
    assert benefit.clause_id in global_clause.related_clause_ids


def test_pdf_table_is_preserved_as_one_complete_clause_unit():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 45), "Section 4: Benefit Limits")
    x_edges = [50, 260, 440]
    y_edges = [70, 100, 130, 160]
    for x in x_edges:
        page.draw_line((x, y_edges[0]), (x, y_edges[-1]))
    for y in y_edges:
        page.draw_line((x_edges[0], y), (x_edges[-1], y))
    cells = [
        ["Item", "Maximum benefit"],
        ["Camera", "$1,500"],
        ["Other property", "$500"],
    ]
    for row_index, row in enumerate(cells):
        y = y_edges[row_index] + 20
        page.insert_text((x_edges[0] + 6, y), row[0])
        page.insert_text((x_edges[1] + 6, y), row[1])
    pdf_bytes = doc.tobytes()
    doc.close()

    result = document_service.process_pdf(pdf_bytes, filename="table.pdf")
    table_clause = next(clause for clause in result.clauses if clause.clause_type == "table")

    assert table_clause.table_rows[0] == ["Item", "Maximum benefit"]
    assert table_clause.table_rows[1] == ["Camera", "$1,500"]
    assert table_clause.page_number == 1
    assert table_clause.validation["verbatim_pass"] is True


def test_scanned_pdf_behavior():
    """Test scanned/raster image PDF returns explicit OCR unavailable status."""
    doc = pymupdf.open()
    page = doc.new_page()
    # Insert small RGB pixmap without any digital text
    pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 50, 50), 1)
    page.insert_image(pymupdf.Rect(50, 50, 150, 150), pixmap=pix)
    scanned_bytes = doc.tobytes()
    doc.close()

    result = document_service.process_pdf(scanned_bytes, filename="scanned.pdf")

    assert result.status == "scanned_ocr_unavailable"
    assert result.is_scanned is True
    assert result.has_extractable_text is False
    assert "OCR extraction is not yet enabled" in result.message


def test_empty_pdf_bytes_rejected():
    """Empty 0-byte file should raise DocumentProcessingError."""
    with pytest.raises(DocumentProcessingError) as exc_info:
        document_service.process_pdf(b"", filename="empty.pdf")
    assert exc_info.value.status_code == "empty"


def test_non_pdf_file_rejected():
    """Non-PDF file signature should raise DocumentProcessingError."""
    with pytest.raises(DocumentProcessingError) as exc_info:
        document_service.process_pdf(b"This is definitely not a PDF file.", filename="fake.pdf")
    assert exc_info.value.status_code == "unsupported_type"


def test_sha256_hash_consistency():
    """SHA-256 hash must be deterministic for identical content."""
    pdf_bytes = create_synthetic_pdf([["Section 1.1: Constant Policy"]])
    hash1 = document_service.calculate_sha256(pdf_bytes)
    hash2 = document_service.calculate_sha256(pdf_bytes)
    assert hash1 == hash2
    assert len(hash1) == 64
