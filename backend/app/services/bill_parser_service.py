"""Medical Bill & Provider Invoice Parser Service for ClaimWise.

Extracts line items, service dates, CPT/HCPCS procedure codes, billed charges,
quantities, and source page provenance from uploaded medical bill PDFs.
Treats all extracted text as untrusted and requires human review.
"""

from datetime import datetime, timezone
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid
import pymupdf

from app.schemas.claim import BillExtractionResult, BillLineItem
from app.services.document_service import DocumentProcessingError, DocumentService
from app.services.rules_engine import dollars_to_cents

logger = logging.getLogger("claimwise.bill_parser_service")

# Regex for standard 5-character CPT/HCPCS procedure codes
# E.g. 99284 (ED visit), 80053 (Comprehensive metabolic panel), 71046 (Chest X-ray), J0129, G0438
CPT_CODE_REGEX = re.compile(r"\b([0-9]{4}[0-9A-Z]|[A-Z][0-9]{4})\b")

# Regex for dates in YYYY-MM-DD, MM/DD/YYYY, or MM-DD-YYYY format
DATE_REGEX = re.compile(
    r"\b(20[2-9][0-9][\-\/.](?:0[1-9]|1[0-2])[\-\/.](?:0[1-9]|[12][0-9]|3[01])|"
    r"(?:0[1-9]|1[0-2])[\-\/.](?:0[1-9]|[12][0-9]|3[01])[\-\/.](?:20[2-9][0-9]|[2-9][0-9]))\b"
)

# Regex for monetary charges, e.g. $1,250.00, $450.50, 750.00
CHARGE_REGEX = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})\b")

# Regex for quantity indicators like "Qty: 2", "Units: 1", "x2"
QTY_REGEX = re.compile(r"\b(?:QTY|UNITS?|QTY:|UNITS?:)\s*([1-9][0-9]?)\b|\bx([1-9][0-9]?)\b", re.IGNORECASE)

# Keywords commonly present on line item descriptions
MEDICAL_LINE_KEYWORDS = [
    "visit", "exam", "panel", "test", "x-ray", "therapy", "surgery",
    "emergency", "evaluation", "management", "consultation", "screening",
    "procedure", "injection", "lab", "pathology", "radiology", "treatment",
    "infusion", "office", "facility", "hospital", "urgent", "ct scan", "mri"
]


class BillParserService:
    """
    Deterministic intake parser for medical bills and provider invoices.
    
    Adheres strictly to the 'Evidence first' standard:
    - Never invents CPT codes, dates, or billed amounts.
    - Preserves 1-based page numbers and verbatim source excerpts.
    - Flags ambiguous or partial line items for user review.
    - Detects scanned raster PDFs and explicitly reports OCR unavailability.
    """

    def parse_bill_pdf(self, file_bytes: bytes, filename: str) -> BillExtractionResult:
        """
        Parse raw PDF bytes into structured line items with provenance.
        """
        # 1. Validate PDF header magic bytes and size
        DocumentService.validate_pdf_bytes(file_bytes)
        document_hash = DocumentService.calculate_sha256(file_bytes)
        file_size_bytes = len(file_bytes)

        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            raise DocumentProcessingError(
                "Failed to parse bill PDF. Upload a valid, readable PDF.",
                status_code="corrupted",
            )

        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            raise DocumentProcessingError("PDF contains 0 pages.", status_code="empty")

        extracted_line_items: List[BillLineItem] = []
        total_text_chars = 0
        has_images = False
        default_bill_date: Optional[str] = None
        detected_provider: Optional[str] = None

        bill_id = f"bill-{uuid.uuid4().hex[:10]}"

        # First pass: check for document-wide header metadata (e.g. overall date or provider)
        for page_idx in range(total_pages):
            page = doc[page_idx]
            text = page.get_text("text") or ""
            total_text_chars += len(text.strip())
            if len(page.get_images()) > 0:
                has_images = True

            # Detect document-level provider name if present in top lines
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            for top_ln in lines[:6]:
                if any(kw in top_ln.lower() for kw in ["hospital", "clinic", "health", "medical center", "physicians", "urgent care"]):
                    if not detected_provider and len(top_ln) < 80:
                        detected_provider = top_ln
                # Look for statement/service date
                date_match = DATE_REGEX.search(top_ln)
                if date_match and not default_bill_date:
                    default_bill_date = self._normalize_date(date_match.group(1))

        # Check for scanned image-only PDF
        is_scanned = total_text_chars < 50 and has_images
        if is_scanned:
            doc.close()
            return BillExtractionResult(
                bill_id=bill_id,
                document_name=filename,
                document_hash=document_hash,
                file_size_bytes=file_size_bytes,
                total_pages=total_pages,
                total_billed_cents=0,
                is_scanned=True,
                has_extractable_text=False,
                line_items=[],
                uploaded_at=datetime.now(timezone.utc),
                message=(
                    "Scanned image-only medical bill detected. This file contains raster images without extractable digital text. "
                    "In accordance with ClaimWise rules, OCR extraction is not simulated. Please upload a digital PDF bill or enter items manually."
                ),
            )

        # Second pass: line-by-line item extraction
        line_counter = 1
        seen_line_keys = set()

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_number = page_idx + 1  # 1-based page number
            text = page.get_text("text") or ""
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

            for line in lines:
                # Find charge amounts in this line
                charge_matches = list(CHARGE_REGEX.finditer(line))
                if not charge_matches:
                    continue

                # Take the last charge in the line as the billed charge (standard invoice layout)
                charge_str = charge_matches[-1].group(1)
                try:
                    charge_cents = dollars_to_cents(charge_str.replace(",", ""))
                except Exception:
                    continue

                if charge_cents <= 0:
                    continue

                # Skip obvious summary rows like "Total Due", "Balance Due", "Account Summary", "Amount Paid"
                lower_line = line.lower()
                if any(skip_kw in lower_line for skip_kw in ["total due", "balance due", "amount paid", "total charges", "payment received", "subtotal", "tax total"]):
                    continue

                # Find CPT / HCPCS code
                cpt_match = CPT_CODE_REGEX.search(line)
                cpt_code = cpt_match.group(1) if cpt_match else None

                # Find service date
                date_match = DATE_REGEX.search(line)
                service_date = self._normalize_date(date_match.group(1)) if date_match else default_bill_date

                # Find quantity
                qty = 1
                qty_match = QTY_REGEX.search(line)
                if qty_match:
                    try:
                        raw_qty = qty_match.group(1) or qty_match.group(2)
                        qty = max(1, int(raw_qty))
                    except Exception:
                        qty = 1

                # Clean up description by stripping dates, codes, and dollar amounts
                clean_desc = line
                if date_match:
                    clean_desc = clean_desc.replace(date_match.group(0), "")
                if cpt_match:
                    clean_desc = clean_desc.replace(cpt_match.group(0), "")
                for m in charge_matches:
                    clean_desc = clean_desc.replace(m.group(0), "")
                if qty_match:
                    clean_desc = clean_desc.replace(qty_match.group(0), "")

                clean_desc = re.sub(r"[\$\s,;:|\-]+", " ", clean_desc).strip()
                if not clean_desc or len(clean_desc) < 3:
                    clean_desc = f"Medical Procedure {cpt_code}" if cpt_code else "Unspecified Medical Service"

                # Check if ambiguous
                is_ambiguous = False
                ambiguity_notes = []
                if not cpt_code:
                    is_ambiguous = True
                    ambiguity_notes.append("CPT/HCPCS code not detected on line item.")
                if not date_match and not default_bill_date:
                    is_ambiguous = True
                    ambiguity_notes.append("Service date missing; please verify.")

                # Deduplicate exact duplicate reads from multi-column flow
                line_key = (page_number, cpt_code, charge_cents, clean_desc[:25])
                if line_key in seen_line_keys:
                    continue
                seen_line_keys.add(line_key)

                item_id = f"LINE-{line_counter:02d}"
                line_counter += 1

                extracted_line_items.append(
                    BillLineItem(
                        line_id=item_id,
                        service_date=service_date,
                        description=clean_desc,
                        cpt_code=cpt_code,
                        billed_charge_cents=charge_cents,
                        quantity=qty,
                        provider_name=detected_provider,
                        source_page_number=page_number,
                        raw_text_excerpt=line,
                        is_ambiguous=is_ambiguous,
                        ambiguity_notes="; ".join(ambiguity_notes) if ambiguity_notes else None,
                    )
                )

        doc.close()

        total_billed_cents = sum(item.billed_charge_cents for item in extracted_line_items)

        return BillExtractionResult(
            bill_id=bill_id,
            document_name=filename,
            document_hash=document_hash,
            file_size_bytes=file_size_bytes,
            total_pages=total_pages,
            total_billed_cents=total_billed_cents,
            is_scanned=False,
            has_extractable_text=len(extracted_line_items) > 0,
            line_items=extracted_line_items,
            uploaded_at=datetime.now(timezone.utc),
            message=(
                f"Successfully parsed {len(extracted_line_items)} line items across {total_pages} page(s) "
                f"totaling ${total_billed_cents / 100:,.2f}."
            ),
        )

    @staticmethod
    def _normalize_date(raw_date: str) -> str:
        """Convert MM/DD/YYYY or MM-DD-YYYY or YYYY-MM-DD into ISO YYYY-MM-DD format."""
        raw = raw_date.strip().replace("/", "-").replace(".", "-")
        parts = raw.split("-")
        if len(parts) == 3:
            # Check if format is YYYY-MM-DD
            if len(parts[0]) == 4:
                return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
            # Format is MM-DD-YYYY
            elif len(parts[2]) == 4:
                return f"{parts[2]}-{int(parts[0]):02d}-{int(parts[1]):02d}"
            # Format is MM-DD-YY
            elif len(parts[2]) == 2:
                year = f"20{parts[2]}"
                return f"{year}-{int(parts[0]):02d}-{int(parts[1]):02d}"
        return raw_date


bill_parser_service = BillParserService()
