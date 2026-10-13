"""PDF Document Processing Service for ClaimWise.

Extracts text, preserves 1-based page numbers, detects clause headings,
computes document SHA-256 integrity hashes, and handles scanned/unreadable files.
Strictly decoupled from LLM analysis and system prompts.
"""

from datetime import datetime, timezone
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import pymupdf

from app.schemas.policy import (
    ExtractedClause,
    PageSummary,
    PolicyExtractionResult,
)

logger = logging.getLogger("claimwise.document_service")

# Regex patterns for heading and section detection
SECTION_PATTERNS = [
    # E.g. "Section 4.2: Exclusions and Limitations", "Sec. 1.1 - Eligibility"
    re.compile(
        r"^(?:SECTION|SEC\.|ARTICLE|ART\.|CLAUSE|SCHEDULE|PART)\s+([A-Z0-9\.\-]+(?:\([a-z0-9]+\))?)(?:\s*[:\-–—]\s*(.*))?$",
        re.IGNORECASE | re.MULTILINE,
    ),
    # E.g. "2.1.4 Emergency Medical Coverage", "3. Definitions"
    re.compile(
        r"^(\d+(?:\.\d+)*)\.?\s+([A-Z][A-Za-z0-9\s,\-_/&()]{2,70})$",
        re.MULTILINE,
    ),
]

# Pattern for heuristic all-caps or title-like headings
HEURISTIC_HEADING_PATTERN = re.compile(
    r"^([A-Z0-9\s,\-_/&()]{4,60})$"
)


class DocumentProcessingError(Exception):
    """Custom exception raised when document parsing encounters an unrecoverable format error."""
    def __init__(self, message: str, status_code: str = "malformed"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DocumentService:
    """
    High-assurance PDF parsing and clause extraction engine.
    
    Adheres strictly to the 'Evidence first' standard:
    - Never hallucinates page numbers or headings.
    - Preserves 1-based page indexing matching human PDF viewer page numbers.
    - Produces stable, reproducible clause identifiers.
    - Explicitly detects scanned/image-only PDFs where OCR is unavailable.
    - Treats all document text as untrusted, raw data.
    """

    @staticmethod
    def calculate_sha256(file_bytes: bytes) -> str:
        """Compute SHA-256 cryptographic hash of raw file bytes."""
        hasher = hashlib.sha256()
        hasher.update(file_bytes)
        return hasher.hexdigest()

    @staticmethod
    def validate_pdf_bytes(file_bytes: bytes) -> None:
        """
        Validate file headers and basic integrity without trusting client claims.
        Rejects empty or non-PDF bytes immediately.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise DocumentProcessingError(
                "Uploaded file is empty (0 bytes). Please upload a valid PDF document.",
                status_code="empty",
            )
        # Check PDF magic bytes (%PDF)
        if not file_bytes.startswith(b"%PDF"):
            raise DocumentProcessingError(
                "Invalid file signature. File header does not match PDF specification (%PDF).",
                status_code="unsupported_type",
            )

    @classmethod
    def _detect_heading(cls, text: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Analyze text block to detect likely clause heading and section number.
        
        Returns:
            Tuple of (section_number, heading_text, confidence)
            where confidence is one of: "high", "heuristic", "uncertain", "none"
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None, None, "none"

        first_line = lines[0]

        # Check explicit section/article patterns (High Confidence)
        for pattern in SECTION_PATTERNS:
            match = pattern.match(first_line)
            if match:
                sec_num = match.group(1).strip()
                heading_part = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ""
                full_heading = f"{sec_num} {heading_part}".strip() if heading_part else sec_num
                return sec_num, full_heading, "high"

        # Check all-caps or title-like short line (Heuristic Confidence)
        if len(first_line) <= 60 and not first_line.endswith((".", ";", ":", ",")):
            if first_line.isupper() and len(first_line) >= 4:
                return None, first_line, "heuristic"
            # Title Case heuristic
            words = first_line.split()
            if len(words) >= 2 and all(w[0].isupper() for w in words if w and w[0].isalpha()):
                return None, first_line, "uncertain"

        return None, None, "none"

    @classmethod
    def process_pdf(
        cls,
        file_bytes: bytes,
        filename: str = "document.pdf",
        persistence_mode: str = "development_preview",
        policy_id: Optional[str] = None,
    ) -> PolicyExtractionResult:
        """
        Process a PDF document into structured, page-referenced clauses.
        
        Args:
            file_bytes: Raw bytes of the PDF.
            filename: Original name of the document.
            persistence_mode: Storage indicator (e.g. 'development_preview' or 'persistent_db').
            policy_id: Optional ID if already registered.
            
        Returns:
            PolicyExtractionResult containing pages, clauses, SHA-256 hash, and extraction status.
        """
        uploaded_at = datetime.now(timezone.utc)
        file_size = len(file_bytes)
        doc_hash = cls.calculate_sha256(file_bytes)

        # Validate basic PDF integrity
        cls.validate_pdf_bytes(file_bytes)

        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            logger.warning("PyMuPDF failed to parse file %s: %s", filename, exc)
            return PolicyExtractionResult(
                document_name=filename,
                document_hash=doc_hash,
                file_size_bytes=file_size,
                total_pages=0,
                total_clauses=0,
                is_scanned=False,
                has_extractable_text=False,
                status="malformed",
                message=f"Failed to parse PDF document: {str(exc)}",
                pages=[],
                clauses=[],
                persistence_mode=persistence_mode,
                policy_id=policy_id,
                uploaded_at=uploaded_at,
            )

        try:
            # Check for encryption
            if doc.is_encrypted or doc.needs_pass:
                return PolicyExtractionResult(
                    document_name=filename,
                    document_hash=doc_hash,
                    file_size_bytes=file_size,
                    total_pages=doc.page_count,
                    total_clauses=0,
                    is_scanned=False,
                    has_extractable_text=False,
                    status="encrypted",
                    message="PDF is encrypted or password-protected. Decryption is not supported.",
                    pages=[],
                    clauses=[],
                    persistence_mode=persistence_mode,
                    policy_id=policy_id,
                    uploaded_at=uploaded_at,
                )

            total_pages = doc.page_count
            if total_pages == 0:
                return PolicyExtractionResult(
                    document_name=filename,
                    document_hash=doc_hash,
                    file_size_bytes=file_size,
                    total_pages=0,
                    total_clauses=0,
                    is_scanned=False,
                    has_extractable_text=False,
                    status="empty",
                    message="PDF document contains zero pages.",
                    pages=[],
                    clauses=[],
                    persistence_mode=persistence_mode,
                    policy_id=policy_id,
                    uploaded_at=uploaded_at,
                )

            page_summaries: List[PageSummary] = []
            extracted_clauses: List[ExtractedClause] = []
            total_doc_text_len = 0
            total_doc_images = 0

            # Iterate through each page (preserving 1-based page number)
            for page_idx in range(total_pages):
                page_number = page_idx + 1  # 1-based page numbering
                page = doc[page_idx]

                # Extract text blocks: tuple (x0, y0, x1, y1, text, block_no, block_type)
                # block_type == 0 is text, block_type == 1 is image
                blocks = page.get_text("blocks")
                page_images = page.get_images()
                total_doc_images += len(page_images)

                page_char_count = 0
                page_clause_count = 0
                sample_heading: Optional[str] = None

                clause_on_page_idx = 1
                for block in blocks:
                    block_type = block[6] if len(block) > 6 else 0
                    if block_type != 0:
                        continue  # Skip image blocks

                    raw_text = block[4].strip() if len(block) > 4 else ""
                    if not raw_text:
                        continue

                    # Accumulate characters
                    page_char_count += len(raw_text)
                    total_doc_text_len += len(raw_text)

                    # Detect clause heading and section number
                    sec_num, heading, confidence = cls._detect_heading(raw_text)
                    if heading and not sample_heading:
                        sample_heading = heading

                    # Generate stable clause identifier
                    if sec_num:
                        # Clean section number for safe ID: e.g. "SEC-1.2"
                        clean_sec = re.sub(r"[^A-Za-z0-9\.\-]", "", sec_num)
                        clause_id = f"SEC-{clean_sec}"
                    else:
                        clause_id = f"P{page_number}-C{clause_on_page_idx}"

                    # Rough token estimation (~1.3 tokens per word)
                    word_count = len(raw_text.split())
                    token_count = max(1, int(word_count * 1.3))

                    extracted_clauses.append(
                        ExtractedClause(
                            clause_id=clause_id,
                            page_number=page_number,
                            clause_heading=heading,
                            heading_confidence=confidence,
                            section_number=sec_num,
                            text=raw_text,
                            token_count=token_count,
                            document_hash=doc_hash,
                        )
                    )
                    page_clause_count += 1
                    clause_on_page_idx += 1

                page_summaries.append(
                    PageSummary(
                        page_number=page_number,
                        clause_count=page_clause_count,
                        char_count=page_char_count,
                        has_images=len(page_images) > 0,
                        sample_heading=sample_heading,
                    )
                )

            # Check if document is scanned (images exist but negligible digital text)
            is_scanned = (total_doc_images > 0 and total_doc_text_len < 50)
            has_extractable_text = total_doc_text_len > 0 and not is_scanned

            if is_scanned:
                return PolicyExtractionResult(
                    document_name=filename,
                    document_hash=doc_hash,
                    file_size_bytes=file_size,
                    total_pages=total_pages,
                    total_clauses=0,
                    is_scanned=True,
                    has_extractable_text=False,
                    status="scanned_ocr_unavailable",
                    message=(
                        "Scanned or image-only PDF detected. OCR extraction is not yet enabled in this milestone. "
                        "Digital text could not be extracted from raster pages."
                    ),
                    pages=page_summaries,
                    clauses=[],
                    persistence_mode=persistence_mode,
                    policy_id=policy_id,
                    uploaded_at=uploaded_at,
                )

            if not has_extractable_text:
                return PolicyExtractionResult(
                    document_name=filename,
                    document_hash=doc_hash,
                    file_size_bytes=file_size,
                    total_pages=total_pages,
                    total_clauses=0,
                    is_scanned=False,
                    has_extractable_text=False,
                    status="no_text_extracted",
                    message="Document opened successfully, but contains no extractable digital text.",
                    pages=page_summaries,
                    clauses=[],
                    persistence_mode=persistence_mode,
                    policy_id=policy_id,
                    uploaded_at=uploaded_at,
                )

            return PolicyExtractionResult(
                document_name=filename,
                document_hash=doc_hash,
                file_size_bytes=file_size,
                total_pages=total_pages,
                total_clauses=len(extracted_clauses),
                is_scanned=False,
                has_extractable_text=True,
                status="success",
                message=f"Successfully extracted {len(extracted_clauses)} clause blocks across {total_pages} pages.",
                pages=page_summaries,
                clauses=extracted_clauses,
                persistence_mode=persistence_mode,
                policy_id=policy_id,
                uploaded_at=uploaded_at,
            )

        finally:
            doc.close()


document_service = DocumentService()
