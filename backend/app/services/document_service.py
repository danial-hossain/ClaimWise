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
    DocumentExtractionValidation,
    ExtractedClause,
    PageSummary,
    PolicyExtractionResult,
)
from app.services.policy_extraction_validation import validate_page_clauses

logger = logging.getLogger("claimwise.document_service")
EXTRACTION_VERSION = 2

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
    def _normalize_clause_text(cls, text: str) -> str:
        """
        Repair broken line wraps from PDF columns while preserving paragraphs and bullet lists.
        """
        if not text:
            return ""
        # 1. Repair hyphenated word wrap at line break: e.g. 'co-\ninsurance' -> 'coinsurance'
        repaired = re.sub(r'(\b[A-Za-z]+)[-\u2010\u2013]\r?\n\s*([A-Za-z]+\b)', r'\1\2', text)
        # Normalize font checkmarks and table checkmarks (Wingdings/Unicode checkmarks)
        repaired = re.sub(r"[\uf0d6\uf0fc\u2713\u2714]", " [Covered] ", repaired)
        # Remove nonprinting glyph artifacts emitted by some PDF fonts while
        # preserving tabs and line breaks used by lists and table cells.
        repaired = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", repaired)

        # 2. Split on double newlines to protect distinct paragraphs
        paragraphs = re.split(r'\r?\n\s*\r?\n', repaired)
        cleaned_paras = []
        for p in paragraphs:
            lines = [line.strip() for line in p.splitlines() if line.strip()]
            if not lines:
                continue
            # If the paragraph is a bulleted/numbered list, preserve lines
            is_list = any(re.match(r'^(?:[•\-\*▪►]|(?:\d+|[a-zA-Z])[\.\)])\s+', l) for l in lines)
            if is_list:
                cleaned_paras.append('\n'.join(lines))
            else:
                # Merge soft line breaks into a clean flowing sentence
                cleaned_paras.append(' '.join(lines))
        return '\n\n'.join(cleaned_paras)

    @staticmethod
    def _is_standalone_question(text: str) -> bool:
        """Identify a PDF text block that is a question heading without its answer."""
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        if not lines:
            return False
        question = " ".join(lines)
        return question.endswith("?") and bool(re.match(
            r"^(?:what|how|why|when|where|who|which|can|could|would|should|do|does|did|is|are|was|were)\b",
            question,
            re.IGNORECASE,
        ))

    @classmethod
    def _looks_like_list_context_heading(cls, text: str) -> bool:
        """Identify a short structural heading that may govern following list items."""
        normalized = re.sub(r"\s+", " ", (text or "")).strip()
        _, _, confidence = cls._detect_heading(normalized)
        return confidence in {"high", "heuristic"} or (
            len(normalized.split()) <= 14
            and len(normalized) <= 180
            and not normalized.endswith((".", ";", "?", "!"))
        )

    @staticmethod
    def _classify_clause_metadata(text: str, heading: Optional[str], section_path: List[str], is_table: bool = False) -> Tuple[str, str]:
        """Classify operative wording and scope from generic policy language."""
        source = f"{heading or ''} {text or ''}"
        normalized = re.sub(r"\s+", " ", source).casefold()
        if is_table:
            clause_type = "table"
        elif re.search(r"\b(?:exclusion|excluded|not covered|will not pay|we will not cover|not payable)\b", normalized):
            clause_type = "exclusion"
        elif re.search(r"\b(?:maximum|maximum benefit|limit|sub-?limit|cap|excess|deductible|depreciat(?:e|ion)|percentage payable)\b", normalized):
            clause_type = "limit"
        elif re.search(r"\b(?:means|is defined as|definition of|for the purposes of this policy)\b", normalized):
            clause_type = "definition"
        elif re.search(r"\b(?:optional|optional cover|additional premium|additional amount|add-on)\b", normalized):
            clause_type = "optional_cover"
        elif re.search(r"\b(?:must|shall|required to|subject to|provided that|unless|only if|condition of cover)\b", normalized):
            clause_type = "condition"
        elif re.search(r"\b(?:covered|cover|benefit|we will pay|we pay|payable|insured against)\b", normalized):
            clause_type = "benefit"
        else:
            clause_type = "unknown"

        document_wide = bool(re.search(
            r"\b(?:all sections|all benefits|all cover sections|any section of this policy|throughout this policy|applies to this entire policy|general exclusions?)\b",
            re.sub(r"\s+", " ", heading or "").casefold()
            + " " + re.split(r"(?<=[.!?])\s+", re.sub(r"\b(?:also )?(?:refer to|see)(?: also)?[^.\n]*", "", text or "", flags=re.I), maxsplit=1)[0].casefold(),
        ))
        if document_wide:
            scope = "document_wide"
        elif section_path:
            scope = "section"
        else:
            scope = "unknown"
        return clause_type, scope

    @staticmethod
    def _extract_cross_references(text: str) -> List[str]:
        pattern = re.compile(
            r"\b(?:see(?:\s+also)?|refer(?:\s+also)?\s+to|as\s+described\s+in|as\s+set\s+out\s+in|in\s+accordance\s+with)\s+"
            r"(?P<target>(?:(?:section|clause|part|schedule|appendix|table|page)\s+)?[A-Z]?[0-9]+(?:[.\-][A-Z0-9]+)*(?:\([A-Za-z0-9]+\))?)",
            re.IGNORECASE,
        )
        return list(dict.fromkeys(re.sub(r"\s+", " ", match.group("target")).strip() for match in pattern.finditer(text or "")))

    @staticmethod
    def _extract_page_tables(page: Any, text_blocks: list[tuple]) -> list[tuple]:
        """Represent each detected PDF table as a complete, row-preserving source block."""
        try:
            finder = page.find_tables()
            tables = finder.tables
        except Exception:
            return []
        table_blocks = []
        for table_index, table in enumerate(tables):
            rows = table.extract() or []
            normalized_rows = [[str(cell or "").strip() for cell in row] for row in rows]
            normalized_rows = [row for row in normalized_rows if any(row)]
            if not normalized_rows:
                continue
            bbox = tuple(table.bbox)
            table_text = "\n".join(" | ".join(row) for row in normalized_rows)
            overlapping = [
                block for block in text_blocks
                if block[0] < bbox[2] and block[2] > bbox[0] and block[1] < bbox[3] and block[3] > bbox[1]
            ]
            block_order = min((block[5] for block in overlapping), default=len(text_blocks) + table_index)
            table_blocks.append((*bbox, table_text, block_order, 0, normalized_rows))
        return table_blocks

    @classmethod
    def _is_policy_clause(cls, text: str, heading: Optional[str], sec_num: Optional[str]) -> bool:
        """
        Differentiate actual policy/contractual clauses from questions, FAQs,
        headers/footers, table of contents, and incidental text.
        """
        raw_text = (text or "").strip()
        raw_heading = (heading or "").strip()
        lower_heading = raw_heading.lower()
        lower_text = raw_text.lower()

        # FAQ style questions are useful policy content when their answer is
        # present in the same extracted block (including blocks joined below).
        first_line = raw_text.splitlines()[0].strip() if raw_text.splitlines() else ""
        if cls._is_standalone_question(first_line):
            answer_text = raw_text[len(first_line):].strip()
            if len(answer_text) >= 25:
                return True

        # 1. Filter out Questions (FAQ, questions in heading or opening line)
        if raw_heading.endswith("?"):
            return False
        if re.match(
            r"^(?:what|how|why|when|where|who|which|can\s+(?:i|you|we|a)|do\s+(?:i|we|you)|does|is\s+(?:it|there|this)|are\s+(?:there|we|you)|should|could|would)\b",
            raw_heading,
            re.IGNORECASE,
        ):
            return False
        if re.match(
            r"^(?:faq|faqs|frequently\s+asked\s+questions?|common\s+questions?|questions?\s*&?\s*answers?|q\s*&\s*a)\b",
            lower_heading,
        ):
            return False

        first_line = raw_text.splitlines()[0].strip() if raw_text.splitlines() else ""
        if not sec_num and first_line.endswith("?") and re.match(r"^(?:what|how|why|when|where|who|can|do|is|are)\b", first_line, re.IGNORECASE):
            return False

        # 2. Filter out Headers, Footers, Page Numbers & TOC
        if re.match(r"^(?:page\s+\d+(\s+of\s+\d+)?|\d+\s+of\s+\d+|-\s*\d+\s*-|\d+)$", raw_text, re.IGNORECASE):
            return False
        if re.match(r"^(?:table\s+of\s+contents|contents|index)\b", lower_heading):
            return False
        if re.match(r"^(?:all\s+rights\s+reserved|copyright\s*©?|confidential|printed\s+in\s+u\.?s\.?a\.?)", lower_text):
            return False
        if re.match(r"^(?:for\s+customer\s+service|for\s+questions\s+call|call\s+customer\s+service|visit\s+our\s+website|tty\s*:?\s*\d+|call\s+1-\d{3})", lower_text) and len(raw_text) < 160:
            return False
        if re.match(r"^(?:signature|member\s+signature|authorized\s+signature|print\s+name|date)\s*[:_]", lower_text):
            return False

        # 3. Filter out trivial snippets
        if len(raw_text) < 25 and not sec_num and not raw_heading:
            return False

        # 4. If explicit section number exists, it is a clause
        if sec_num:
            return True

        # 5. Check if heading indicates recognized policy clause
        policy_keywords = [
            "benefit", "coverage", "covered", "exclusion", "limitation", "deductible",
            "copay", "coinsurance", "out-of-pocket", "eligibility", "termination",
            "inpatient", "outpatient", "emergency", "prescription", "claim",
            "authorization", "pre-auth", "appeal", "grievance", "coordination",
            "subrogation", "definition", "provision", "condition", "schedule",
            "allowance", "reimbursement", "liability", "rider", "general provision",
        ]
        if raw_heading and any(kw in lower_heading for kw in policy_keywords):
            return True

        # 6. Check for contractual/policy terms in body
        contractual_patterns = [
            r"\b(?:shall|must|is\s+covered|are\s+covered|will\s+be\s+covered|not\s+covered|excluded|exclusion|subject\s+to|in\s+the\s+event\s+of|payable|benefits\s+will|excess|depreciation|(?:benefit|claim|coverage)\s+limit|deductible|coinsurance|copayment|pre-authorization|prior\s+authorization|medically\s+necessary|maximum\s+allowable|out-of-pocket\s+maximum|eligible\s+expenses|coverage\s+terminates)\b"
        ]
        if any(re.search(pat, lower_text) for pat in contractual_patterns):
            return True

        # 7. Substantive unlabelled paragraphs without question/metadata markers
        if len(raw_text) >= 40:
            return True

        return False

    @staticmethod
    def _running_margin_text(doc) -> set[str]:
        """Identify repeated running furniture by geometry, never policy wording."""
        from collections import Counter
        counts = Counter()
        for page in doc:
            seen = set()
            for block in page.get_text("blocks"):
                if len(block) < 7 or block[6] != 0:
                    continue
                x0, y0, x1, y1, text = block[:5]
                at_margin = (x0 >= page.rect.width * .90 or x1 <= page.rect.width * .10
                             or y0 >= page.rect.height * .94 or y1 <= page.rect.height * .035)
                if at_margin:
                    seen.add(re.sub(r"\d+", "#", re.sub(r"\s+", " ", text).strip()))
            counts.update(seen)
        return {text for text, count in counts.items() if count >= 3}

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
            logger.warning("PDF parsing failed (%s).", type(exc).__name__)
            return PolicyExtractionResult(
                    extraction_version=EXTRACTION_VERSION,
                document_name=filename,
                document_hash=doc_hash,
                file_size_bytes=file_size,
                total_pages=0,
                total_clauses=0,
                is_scanned=False,
                has_extractable_text=False,
                status="malformed",
                message="Failed to parse PDF document. Upload a valid, readable PDF.",
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
                    extraction_version=EXTRACTION_VERSION,
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
                    extraction_version=EXTRACTION_VERSION,
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
            section_stack: List[Tuple[Tuple[str, ...], str]] = []
            current_sub_heading: Optional[str] = None
            inherited_scope = "unknown"
            validation_totals = {
                "verbatim_clause_count": 0,
                "verbatim_pass_count": 0,
                "extracted_source_token_count": 0,
                "covered_source_token_count": 0,
                "attribution_verified_count": 0,
                "attribution_flagged_count": 0,
                "rejected_clause_count": 0,
                "uncovered_span_count": 0,
            }

            running_margins = cls._running_margin_text(doc)

            # Iterate through each page (preserving 1-based page number)
            for page_idx in range(total_pages):
                page_number = page_idx + 1  # 1-based page numbering
                page = doc[page_idx]
                page_source_text = page.get_text("text")
                total_doc_text_len += len(page_source_text)

                # Extract text blocks: tuple (x0, y0, x1, y1, text, block_no, block_type)
                # block_type == 0 is text, block_type == 1 is image
                blocks = page.get_text("blocks")
                blocks = [block for block in blocks if not (
                    len(block) > 6 and block[6] == 0
                    and re.sub(r"\d+", "#", re.sub(r"\s+", " ", block[4]).strip()) in running_margins
                    and (block[0] >= page.rect.width * .90 or block[2] <= page.rect.width * .10
                         or block[1] >= page.rect.height * .94 or block[3] <= page.rect.height * .035))]
                page_images = page.get_images()
                total_doc_images += len(page_images)

                layout_section_titles = set()
                layout = page.get_text("dict")
                sizes = [round(span["size"], 1) for block in layout["blocks"] if "lines" in block
                         for line in block["lines"] for span in line["spans"] if len(span["text"].strip()) > 40]
                from statistics import median
                body_size = median(sizes) if sizes else 0
                for block in layout["blocks"]:
                    if "lines" not in block:
                        continue
                    spans = [span for line in block["lines"] for span in line["spans"] if span["text"].strip()]
                    title = " ".join(span["text"].strip() for span in spans)
                    if (spans and body_size and len(title) <= 180
                            and all(span["size"] >= body_size * 1.25 for span in spans)
                            and not title.endswith((".", ";", "?", "!"))):
                        layout_section_titles.add(block["lines"][0]["spans"][0]["text"].strip())

                # PDF exporters often put an FAQ question and its answer in
                # adjacent text blocks. Keep them together so the reader does
                # not lose the question or show an orphaned answer.
                raw_text_blocks = [block for block in blocks if len(block) > 6 and block[6] == 0 and len(block) > 4 and block[4].strip()]
                table_blocks = cls._extract_page_tables(page, raw_text_blocks)
                table_boxes = [block[:4] for block in table_blocks]
                text_blocks = [
                    block for block in raw_text_blocks
                    if not any(block[0] < box[2] and block[2] > box[0] and block[1] < box[3] and block[3] > box[1] for box in table_boxes)
                ]
                text_blocks.extend(table_blocks)
                text_blocks.sort(key=lambda block: (block[5], block[1], block[0]))
                merged_blocks = []
                block_index = 0
                while block_index < len(text_blocks):
                    block = text_blocks[block_index]
                    content = block[4].strip()
                    if len(block) > 7:
                        merged_blocks.append(block)
                        block_index += 1
                        continue
                    if cls._is_standalone_question(content) and block_index + 1 < len(text_blocks) and len(text_blocks[block_index + 1]) <= 7:
                        answer_block = text_blocks[block_index + 1]
                        answer = answer_block[4].strip()
                        if answer and not cls._is_standalone_question(answer):
                            block = (*block[:4], f"{content}\n\n{answer}", *block[5:])
                            block_index += 1
                    merged_blocks.append(block)
                    block_index += 1

                # Consolidate adjacent lines / text fragments that belong to the same paragraph or clause.
                # In many PDFs, PyMuPDF emits each visual line or phrase as a separate block.
                # Grouping contiguous lines preserves complete semantic clauses and headings.
                consolidated_blocks = []
                for b_item in merged_blocks:
                    if not consolidated_blocks:
                        consolidated_blocks.append(b_item)
                        continue

                    prev_b = consolidated_blocks[-1]
                    if len(b_item) > 7 or len(prev_b) > 7:
                        consolidated_blocks.append(b_item)
                        continue
                    prev_t = prev_b[4].strip()
                    curr_t = b_item[4].strip()

                    # Never merge across high-confidence section/article headings or explicit clause markers
                    curr_sec, curr_heading, curr_conf = cls._detect_heading(curr_t)
                    is_curr_heading = curr_t.splitlines()[0].strip() in layout_section_titles or curr_conf in ("high", "heuristic") or bool(
                        re.match(r"^(?:SECTION|SEC\.|ARTICLE|ART\.|CLAUSE|SCHEDULE|PART)\b", curr_t, re.I)
                    )

                    prev_x0, prev_y0, prev_x1, prev_y1 = prev_b[:4]
                    curr_x0, curr_y0, curr_x1, curr_y1 = b_item[:4]

                    same_column = (abs(curr_x0 - prev_x0) < 35) or (curr_x0 >= prev_x0 - 5 and curr_x1 <= prev_x1 + 40)
                    vertical_gap = curr_y0 - prev_y1
                    line_height = max(8.0, prev_y1 - prev_y0)

                    is_list_start = bool(re.match(r"^\s*\(?(?:[ivxlcdm]+|[a-z]|\d+)[.)]\s+", curr_t, re.I))
                    previous_list_item = bool(re.match(r"^\s*\(?(?:[ivxlcdm]+|[a-z]|\d+)[.)]\s+", prev_t, re.I))
                    is_curr_heading = is_curr_heading or is_list_start
                    prev_ends_mid_sentence = not prev_t.endswith((".", ":", ";", "?", "!"))
                    prev_ends_hyphen = prev_t.endswith(("-", "–", "—"))

                    can_merge = bool(
                        is_list_start and same_column and len(prev_t) <= 240
                        and not re.search(r"(?m)^\s*\(?(?:[ivxlcdm]+|[a-z]|\d+)[.)]\s+", prev_t, re.I)
                        and cls._looks_like_list_context_heading(prev_t)
                    )
                    if not is_curr_heading and same_column:
                        if previous_list_item and curr_t[:1].islower():
                            can_merge = True
                        # Normal line spacing within a paragraph
                        if -2.0 <= vertical_gap <= max(12.0, line_height * 1.3):
                            can_merge = True
                        elif prev_ends_mid_sentence and vertical_gap <= max(20.0, line_height * 2.0):
                            can_merge = True
                        elif prev_ends_hyphen and vertical_gap <= 25.0:
                            can_merge = True
                    # Also handle multi-column text wrap from bottom of column 1 to top of column 2 mid-sentence
                    if not is_curr_heading and prev_ends_mid_sentence and curr_t and curr_t[0].islower():
                        if curr_x0 > prev_x1 - 20 and curr_y0 < prev_y1:
                            can_merge = True

                    if can_merge:
                        sep = "" if prev_ends_hyphen else "\n"
                        new_text = f"{prev_b[4].rstrip()}{sep}{curr_t.lstrip()}"
                        new_x0 = min(prev_x0, curr_x0)
                        new_y0 = min(prev_y0, curr_y0)
                        new_x1 = max(prev_x1, curr_x1)
                        new_y1 = max(prev_y1, curr_y1)
                        consolidated_blocks[-1] = (new_x0, new_y0, new_x1, new_y1, new_text, *prev_b[5:])
                    else:
                        consolidated_blocks.append(b_item)

                merged_blocks = consolidated_blocks

                page_char_count = 0
                page_clause_count = 0
                sample_heading: Optional[str] = None

                clause_on_page_idx = 1
                for block in merged_blocks:
                    block_type = block[6] if len(block) > 6 else 0
                    if block_type != 0:
                        continue  # Skip image blocks

                    raw_text = block[4].strip() if len(block) > 4 else ""
                    if not raw_text:
                        continue

                    # Count the source page once; clause text can be joined or table-rendered.
                    page_char_count = len(page_source_text)

                    # Detect clause heading and section number
                    sec_num, heading, confidence = cls._detect_heading(raw_text)
                    if sec_num:
                        number_path = tuple(re.findall(r"[A-Za-z]+|\d+", sec_num))
                        explicit_section = bool(re.match(r"^(?:section|sec\.|article|art\.|clause|schedule|part)\b", raw_text, re.I))
                        if not explicit_section and section_stack and len(number_path) == 1:
                            number_path = section_stack[0][0] + ("sub",) + number_path
                        section_stack = [
                            (old_path, old_heading) for old_path, old_heading in section_stack
                            if len(old_path) < len(number_path) and number_path[:len(old_path)] == old_path
                        ]
                        section_stack.append((number_path, heading or sec_num))
                        current_sub_heading = heading if len(number_path) > 1 else None
                        inherited_scope = "section"
                    elif raw_text.splitlines()[0].strip() in layout_section_titles:
                        heading = raw_text.splitlines()[0].strip()
                        confidence = "high"
                        section_stack = [(("title", heading), heading)]
                        current_sub_heading = None
                        _, inherited_scope = cls._classify_clause_metadata(raw_text, heading, [heading])
                    elif heading and confidence in {"heuristic", "uncertain"}:
                        current_sub_heading = heading
                    section_path = [path_heading for _, path_heading in section_stack]
                    if heading and not sample_heading:
                        sample_heading = heading

                    # Generate stable clause identifier
                    if sec_num:
                        # Clean section number for safe ID: e.g. "SEC-1.2"
                        clean_sec = re.sub(r"[^A-Za-z0-9\.\-]", "", sec_num)
                        clause_id = f"SEC-{clean_sec}"
                    else:
                        clause_id = f"P{page_number}-C{clause_on_page_idx}"
                    if any(c.clause_id == clause_id for c in extracted_clauses):
                        clause_id = f"{clause_id}-P{page_number}-C{clause_on_page_idx}"

                    # Rough token estimation (~1.3 tokens per word)
                    word_count = len(raw_text.split())
                    token_count = max(1, int(word_count * 1.3))
                    is_table = len(block) > 7 and bool(block[7])
                    clause_type, scope = cls._classify_clause_metadata(raw_text, heading, section_path, is_table)
                    if inherited_scope == "document_wide":
                        scope = "document_wide"
                    cross_references = cls._extract_cross_references(raw_text)

                    extracted_clauses.append(
                        ExtractedClause(
                            clause_id=clause_id,
                            page_number=page_number,
                            printed_page_label=page.get_label() or None,
                            clause_heading=heading,
                            section_path=section_path,
                            sub_heading=current_sub_heading,
                            heading_confidence=confidence,
                            section_number=sec_num,
                            clause_type=clause_type,
                            scope=scope,
                            cross_references=cross_references,
                            table_rows=block[7] if is_table else [],
                            text=cls._normalize_clause_text(raw_text),
                            token_count=token_count,
                            document_hash=doc_hash,
                            is_clause=cls._is_policy_clause(raw_text, heading, sec_num),
                        )
                    )
                    page_clause_count += 1
                    clause_on_page_idx += 1

                page_clauses = [clause for clause in extracted_clauses if clause.page_number == page_number]
                page_validation = validate_page_clauses(page_source_text, page_clauses)
                reextracted = 0
                for uncovered_index, span in enumerate(page_validation["uncovered_spans"], start=1):
                    if not cls._is_policy_clause(span, None, None):
                        continue
                    clause_id = f"P{page_number}-U{uncovered_index}"
                    fallback_type, fallback_scope = cls._classify_clause_metadata(span, None, [], False)
                    fallback = ExtractedClause(
                        clause_id=clause_id,
                        page_number=page_number,
                        printed_page_label=page.get_label() or None,
                        section_path=[],  # A recovered span has no reliable structural position.
                        sub_heading=current_sub_heading,
                        heading_confidence="none",
                        section_number=None,
                        clause_type=fallback_type,
                        scope=fallback_scope,
                        cross_references=cls._extract_cross_references(span),
                        text=span,
                        token_count=max(1, int(len(span.split()) * 1.3)),
                        document_hash=doc_hash,
                        is_clause=True,
                    )
                    if not any(existing.clause_id == clause_id and existing.page_number == page_number for existing in page_clauses):
                        page_clauses.append(fallback)
                        extracted_clauses.append(fallback)
                        reextracted += 1
                if reextracted:
                    page_validation = validate_page_clauses(page_source_text, page_clauses)

                validation_totals["verbatim_clause_count"] += page_validation["verbatim_clause_count"]
                validation_totals["verbatim_pass_count"] += page_validation["verbatim_pass_count"]
                validation_totals["extracted_source_token_count"] += page_validation["source_token_count"]
                validation_totals["covered_source_token_count"] += page_validation["covered_token_count"]
                validation_totals["attribution_verified_count"] += page_validation["attribution_verified_count"]
                validation_totals["attribution_flagged_count"] += page_validation["attribution_flagged_count"]
                validation_totals["rejected_clause_count"] += page_validation["verbatim_clause_count"] - page_validation["verbatim_pass_count"]
                validation_totals["uncovered_span_count"] += len(page_validation["uncovered_spans"])

                page_summaries.append(
                    PageSummary(
                        page_number=page_number,
                        clause_count=len(page_clauses),
                        char_count=page_char_count,
                        has_images=len(page_images) > 0,
                        sample_heading=sample_heading,
                        source_token_count=page_validation["source_token_count"],
                        covered_token_count=page_validation["covered_token_count"],
                        extraction_coverage_ratio=page_validation["coverage_ratio"],
                        uncovered_spans=page_validation["uncovered_spans"],
                    )
                )

            # Resolve numbered section/page cross-references within this document version.
            for clause in extracted_clauses:
                targets: list[str] = []
                for reference in clause.cross_references:
                    page_match = re.search(r"\bpage\s+(\d+)\b", reference, re.I)
                    section_match = re.search(r"\b(?:section|clause|part|schedule|appendix|table)\s+([A-Z0-9][A-Z0-9.\-()]*)", reference, re.I)
                    if page_match:
                        target_page = int(page_match.group(1))
                        targets.extend(item.clause_id for item in extracted_clauses if item.page_number == target_page and item.clause_id != clause.clause_id)
                    elif section_match:
                        target = section_match.group(1).casefold().strip(".-()")
                        targets.extend(item.clause_id for item in extracted_clauses if item.clause_id != clause.clause_id and (
                            (item.section_number or "").casefold().strip(".-()") == target
                            or any(re.match(rf"^{re.escape(target)}(?:\s|$)", heading.casefold()) for heading in item.section_path)
                        ))
                clause.related_clause_ids = list(dict.fromkeys(targets))

            # Check if document is scanned (images exist but negligible digital text)
            is_scanned = (total_doc_images > 0 and total_doc_text_len < 50)
            has_extractable_text = total_doc_text_len > 0 and not is_scanned

            if is_scanned:
                return PolicyExtractionResult(
                    extraction_version=EXTRACTION_VERSION,
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
                    extraction_version=EXTRACTION_VERSION,
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
                    extraction_version=EXTRACTION_VERSION,
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
                extraction_validation=DocumentExtractionValidation(
                    **validation_totals,
                    verbatim_pass_rate=validation_totals["verbatim_pass_count"] / max(validation_totals["verbatim_clause_count"], 1),
                    text_coverage_ratio=validation_totals["covered_source_token_count"] / max(validation_totals["extracted_source_token_count"], 1),
                ),
                persistence_mode=persistence_mode,
                policy_id=policy_id,
                uploaded_at=uploaded_at,
            )

        finally:
            doc.close()


document_service = DocumentService()
