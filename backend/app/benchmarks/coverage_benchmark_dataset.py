"""Deterministic fixtures for the coverage extraction and evaluation benchmark."""

from dataclasses import dataclass
from typing import Optional

from app.schemas.policy import ExtractedClause


@dataclass(frozen=True)
class TableExtractionFixture:
    case_id: str
    vector_borders: bool
    required_text: tuple[str, ...]
    expected_rows: Optional[tuple[tuple[str, ...], ...]] = None


@dataclass(frozen=True)
class RetrievalEventFixture:
    event: str
    query: str
    expected_seed_ids: tuple[str, ...]
    expected_section_ids: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalFixture:
    case_id: str
    events: tuple[RetrievalEventFixture, ...]
    expected_document_wide_ids: tuple[str, ...]


@dataclass(frozen=True)
class CoverageOutcomeFixture:
    case_id: str
    situation: str
    query: str
    expected_verdict: str
    expected_citation_ids: tuple[str, ...]
    expected_payable_contains: Optional[str] = None
    expected_calculation_contains: tuple[str, ...] = ()


TABLE_ROWS = (
    ("Item", "Depreciation per year", "Maximum benefit"),
    ("Camera", "10% depreciation per year", "$1,500"),
    ("Laptop", "15% depreciation per year", "$2,000"),
)

TABLE_EXTRACTION_FIXTURES = (
    TableExtractionFixture(
        case_id="bordered-vector-table",
        vector_borders=True,
        required_text=("Camera", "10% depreciation per year", "$1,500", "Laptop", "$2,000"),
        expected_rows=TABLE_ROWS,
    ),
    TableExtractionFixture(
        case_id="unbordered-visual-table",
        vector_borders=False,
        required_text=("Camera", "10% depreciation per year", "$1,500", "Laptop", "$2,000"),
    ),
)


def build_table_fixture_pdf(fixture: TableExtractionFixture) -> bytes:
    """Build either a vector table or a visually aligned, text-only table."""
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((45, 45), "Section 4: Item limits and depreciation")
    x_edges = (45, 205, 405, 555)
    y_edges = (70, 102, 134, 166)
    if fixture.vector_borders:
        for x in x_edges:
            page.draw_line((x, y_edges[0]), (x, y_edges[-1]))
        for y in y_edges:
            page.draw_line((x_edges[0], y), (x_edges[-1], y))

    for row_index, row in enumerate(TABLE_ROWS):
        y = y_edges[row_index] + 21
        for column_index, value in enumerate(row):
            page.insert_text((x_edges[column_index] + 5, y), value, fontsize=9)

    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


BENCHMARK_POLICY_ID = "coverage-eval-policy"
BENCHMARK_DOCUMENT_HASH = "coverage-eval-synthetic-document"

COVERAGE_POLICY_CLAUSES = (
    ExtractedClause(
        clause_id="ER-1",
        page_number=1,
        clause_heading="Emergency Room Services",
        section_path=["Section 1: Medical Benefits", "Emergency Services"],
        clause_type="benefit",
        scope="section",
        text="Emergency Room Services are covered subject to a $150 copayment per visit.",
        token_count=12,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="CAM-1",
        page_number=2,
        clause_heading="Camera Cover",
        section_path=["Section 2: Personal Property", "Camera Cover"],
        clause_type="benefit",
        scope="section",
        related_clause_ids=["CAM-TABLE"],
        text=(
            "Accidental damage to cameras is covered, subject to the applicable limits, "
            "a $100 excess, and 10% depreciation per year."
        ),
        token_count=20,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="CAM-TABLE",
        page_number=2,
        clause_heading="Camera Cover Limits",
        section_path=["Section 2: Personal Property", "Camera Cover"],
        clause_type="table",
        scope="section",
        table_rows=[list(row) for row in TABLE_ROWS],
        text="\n".join(" | ".join(row) for row in TABLE_ROWS),
        token_count=25,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="HOTEL-1",
        page_number=3,
        clause_heading="Additional Accommodation",
        section_path=["Section 3: Additional Expenses", "Additional Accommodation"],
        clause_type="benefit",
        scope="section",
        text="Reasonable additional accommodation expenses following an insured event are covered up to $500 per night.",
        token_count=15,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="COS-1",
        page_number=4,
        clause_heading="Cosmetic Rhinoplasty",
        section_path=["Section 5: Exclusions", "Cosmetic Treatment"],
        clause_type="exclusion",
        scope="section",
        text="Cosmetic rhinoplasty procedures performed primarily for appearance are excluded from coverage.",
        token_count=11,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="GLOBAL-WEAR",
        page_number=5,
        clause_heading="General Exclusions",
        section_path=["General Exclusions"],
        clause_type="exclusion",
        scope="document_wide",
        text="We do not cover loss caused by gradual wear and tear.",
        token_count=11,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="OPTIONAL-BIKE",
        page_number=6,
        clause_heading="Optional Bicycle Cover",
        section_path=["Section 6: Optional Covers", "Bicycle Cover"],
        clause_type="optional_cover",
        scope="section",
        text="Optional bicycle cover applies only if selected on the policy schedule and the additional premium is paid.",
        token_count=16,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="CAM-REPORTING",
        page_number=2,
        clause_heading="Camera Claims",
        section_path=["Section 2: Personal Property", "Camera Cover"],
        clause_type="condition",
        scope="section",
        text="A camera loss must be reported within 30 days of discovery.",
        token_count=11,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="OTHER-BENEFIT",
        page_number=7,
        clause_heading="Bicycle Liability Benefit",
        section_path=["Section 7: Liability", "Bicycle Liability"],
        clause_type="benefit",
        scope="section",
        text="Bicycle liability is covered when the insured is legally responsible for injury to another person.",
        token_count=15,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
    ExtractedClause(
        clause_id="OTHER-CONDITION",
        page_number=7,
        clause_heading="Bicycle Liability Conditions",
        section_path=["Section 7: Liability", "Bicycle Liability"],
        clause_type="condition",
        scope="section",
        text="Bicycle liability requires written notice within 14 days.",
        token_count=9,
        document_hash=BENCHMARK_DOCUMENT_HASH,
    ),
)


RETRIEVAL_FIXTURES = (
    RetrievalFixture(
        case_id="multi-event-camera-and-accommodation",
        events=(
            RetrievalEventFixture(
                event="camera damage",
                query="camera accidental damage cover benefit limits depreciation excess",
                expected_seed_ids=("CAM-1",),
                expected_section_ids=("CAM-1", "CAM-TABLE", "CAM-REPORTING"),
            ),
            RetrievalEventFixture(
                event="extra hotel night",
                query="additional accommodation expenses insured event maximum per night",
                expected_seed_ids=("HOTEL-1",),
                expected_section_ids=("HOTEL-1",),
            ),
        ),
        expected_document_wide_ids=("GLOBAL-WEAR",),
    ),
)


COVERAGE_OUTCOME_FIXTURES = (
    CoverageOutcomeFixture(
        case_id="emergency-room-copayment",
        situation="Emergency Room Care",
        query="Emergency Room Services emergency copayment",
        expected_verdict="covered",
        expected_citation_ids=("ER-1",),
        expected_payable_contains="$150 copayment per visit",
        expected_calculation_contains=("$150 copayment",),
    ),
    CoverageOutcomeFixture(
        case_id="camera-limit-and-depreciation",
        situation="A storm damaged my camera",
        query="camera accidental damage benefit limits depreciation excess",
        expected_verdict="conditional",
        expected_citation_ids=("CAM-1",),
        expected_payable_contains="Camera: $1,500",
        expected_calculation_contains=("$100", "10% depreciation per year"),
    ),
    CoverageOutcomeFixture(
        case_id="cosmetic-rhinoplasty-exclusion",
        situation="Cosmetic Rhinoplasty",
        query="cosmetic rhinoplasty excluded procedure",
        expected_verdict="excluded",
        expected_citation_ids=("COS-1",),
    ),
    CoverageOutcomeFixture(
        case_id="additional-accommodation-limit",
        situation="I paid for an extra hotel night",
        query="additional accommodation expenses maximum per night hotel",
        expected_verdict="conditional",
        expected_citation_ids=("HOTEL-1",),
        expected_payable_contains="Maximum limit: $500",
        expected_calculation_contains=("$500",),
    ),
)