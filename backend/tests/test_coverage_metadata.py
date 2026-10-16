"""Regression tests for source metadata through extraction, storage and retrieval."""
from contextlib import contextmanager
import json
from datetime import datetime, timezone
import pymupdf
from app.schemas.policy import ExtractedClause, PolicyExtractionResult
from app.db.local_store import local_store
from app.services.document_service import DocumentService
from app.services.retrieval.hybrid_service import HybridRetrievalService
from app.services.retrieval.bm25_service import BM25RetrievalService


def source():
    return ExtractedClause(clause_id="C", page_number=1, text="Accidental loss is covered.",
        document_hash="hash", section_path=["Cover"], scope="section", clause_type="benefit",
        related_clause_ids=["D"], cross_references=["Section D"], table_rows=[["Limit", "400"]],
        validation={"verbatim_pass": True, "attribution_status": "structural"})


def test_metadata_survives_store_serialization_and_retrieval(monkeypatch):
    captured = {}
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params):
            if "INSERT INTO policies" in sql: captured["data"] = params[9]
        def executemany(self, sql, rows): captured["chunks"] = list(rows)
        def fetchone(self): return (captured["data"],)
    class Connection:
        def cursor(self): return Cursor()
    @contextmanager
    def connection(): yield Connection()
    monkeypatch.setattr(local_store, "_connection", connection)
    policy = PolicyExtractionResult(document_name="synthetic.pdf", document_hash="hash",
        file_size_bytes=1, total_pages=1, total_clauses=1, status="success", message="ok",
        clauses=[source()], uploaded_at=datetime.now(timezone.utc))
    local_store.save_policy("owner", policy, user_id="user")
    loaded = local_store.get_policy("owner")
    assert loaded.policy_id == "owner"
    assert loaded.clauses == policy.clauses
    meta = json.loads(captured["chunks"][0][-1])
    for key in ("section_path", "scope", "clause_type", "related_clause_ids", "validation", "table_rows"):
        assert meta[key] == source().model_dump()[key]
    retriever = HybridRetrievalService(lexical_engine=BM25RetrievalService())
    monkeypatch.setattr(retriever._dense, "index_policy", lambda *args: 0)
    monkeypatch.setattr(retriever._dense, "is_available", lambda: False)
    retriever.index_policy("owner", loaded.clauses, "hash")
    hits, _ = retriever.retrieve("accidental loss", ["owner"])
    assert hits
    for key in ("section_path", "scope", "clause_type", "related_clause_ids", "validation", "table_rows"):
        assert getattr(hits[0], key) == getattr(source(), key)


def test_recovered_span_is_not_assigned_last_section(monkeypatch):
    document = pymupdf.open(); page = document.new_page()
    page.insert_text((50, 50), "The company will pay for accidental loss of insured equipment.")
    page.insert_text((50, 150), "Section 8: Separate conditions")
    page.insert_text((50, 180), "Claims must be notified promptly to the company.")
    def omit_first(cls, page, blocks):
        blocks.pop(0)
        return []
    monkeypatch.setattr(DocumentService, "_extract_page_tables", classmethod(omit_first))
    result = DocumentService.process_pdf(document.tobytes(), "synthetic.pdf")
    document.close()
    recovered = [c for c in result.clauses if "-U" in c.clause_id]
    assert recovered
    assert all(c.section_path == [] and c.validation["attribution_flagged"] for c in recovered)


def test_short_operative_excess_is_retained():
    assert DocumentService._is_policy_clause("The instrument claim excess is 100.", None, None)
