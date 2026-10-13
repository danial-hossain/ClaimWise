"""Unit tests for Medical Bill & Invoice Parser Service."""

import io
import pytest
import pymupdf

from app.services.bill_parser_service import bill_parser_service
from app.services.document_service import DocumentProcessingError


def create_sample_medical_bill_pdf(is_scanned: bool = False, multi_page: bool = False) -> bytes:
    """Generate synthetic medical bill PDF."""
    doc = pymupdf.open()
    page1 = doc.new_page()

    if is_scanned:
        # Create small 50x50 dummy image pixmap
        pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 50, 50), False)
        page1.insert_image(pymupdf.Rect(50, 50, 150, 150), pixmap=pix)
        # No text inserted
    else:
        page1.insert_text((50, 40), "CITY MEMORIAL HOSPITAL - ITEMIZATION STATEMENT")
        page1.insert_text((50, 60), "Statement Date: 2026-03-15  Account: ACCT-99201")
        page1.insert_text((50, 100), "2026-03-14 99284 Emergency Dept Visit Level 4 Qty: 1 $1,250.00")
        page1.insert_text((50, 130), "2026-03-14 80053 Comprehensive Metabolic Panel Qty: 1 $150.00")
        page1.insert_text((50, 160), "2026-03-14 71046 Chest X-Ray 2 Views Qty: 1 $350.00")
        page1.insert_text((50, 200), "Total Charges: $1,750.00")

        if multi_page:
            page2 = doc.new_page()
            page2.insert_text((50, 40), "CITY MEMORIAL HOSPITAL - CONTINUATION SHEET")
            page2.insert_text((50, 80), "2026-03-14 99213 Follow-up Consultation Qty: 1 $200.00")

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_parse_valid_single_page_bill():
    """Verify digital single-page bill parsing extracts CPT codes, dates, and charges."""
    pdf_bytes = create_sample_medical_bill_pdf()
    result = bill_parser_service.parse_bill_pdf(pdf_bytes, "hospital_invoice.pdf")

    assert result.is_scanned is False
    assert result.has_extractable_text is True
    assert result.total_pages == 1
    assert len(result.line_items) == 3

    # Check first line item (Emergency Room Visit)
    item1 = result.line_items[0]
    assert item1.line_id == "LINE-01"
    assert item1.cpt_code == "99284"
    assert item1.billed_charge_cents == 125000  # $1,250.00
    assert "Emergency" in item1.description
    assert item1.source_page_number == 1
    assert item1.service_date == "2026-03-14"

    # Check second item (Metabolic panel)
    item2 = result.line_items[1]
    assert item2.cpt_code == "80053"
    assert item2.billed_charge_cents == 15000  # $150.00

    # Check third item (Chest X-Ray)
    item3 = result.line_items[2]
    assert item3.cpt_code == "71046"
    assert item3.billed_charge_cents == 35000  # $350.00

    assert result.total_billed_cents == 175000  # $1,750.00


def test_parse_multi_page_bill_page_numbers():
    """Verify multi-page bill extraction preserves 1-based page numbers across pages."""
    pdf_bytes = create_sample_medical_bill_pdf(multi_page=True)
    result = bill_parser_service.parse_bill_pdf(pdf_bytes, "multi_page_bill.pdf")

    assert result.total_pages == 2
    assert len(result.line_items) == 4

    # Verify line items on page 1
    assert result.line_items[0].source_page_number == 1
    assert result.line_items[1].source_page_number == 1
    assert result.line_items[2].source_page_number == 1

    # Verify line item on page 2
    assert result.line_items[3].source_page_number == 2
    assert result.line_items[3].cpt_code == "99213"
    assert result.line_items[3].billed_charge_cents == 20000


def test_parse_scanned_image_bill_detection():
    """Verify image-only raster bill triggers honest scanned status without fake OCR."""
    pdf_bytes = create_sample_medical_bill_pdf(is_scanned=True)
    result = bill_parser_service.parse_bill_pdf(pdf_bytes, "scanned_invoice.pdf")

    assert result.is_scanned is True
    assert result.has_extractable_text is False
    assert len(result.line_items) == 0
    assert "Scanned image-only medical bill detected" in result.message


def test_parse_empty_and_corrupt_bill():
    """Verify empty or corrupted bytes raise DocumentProcessingError."""
    with pytest.raises(DocumentProcessingError) as exc:
        bill_parser_service.parse_bill_pdf(b"", "empty.pdf")
    assert "empty" in exc.value.status_code

    with pytest.raises(DocumentProcessingError) as exc:
        bill_parser_service.parse_bill_pdf(b"not a pdf content", "fake.pdf")
    assert "unsupported_type" in exc.value.status_code or "corrupted" in exc.value.status_code
