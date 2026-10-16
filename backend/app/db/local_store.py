"""PostgreSQL persistent store for ClaimWise (Neon Database).

Provides durable, thread-safe persistence for:
- Policies and granular extracted clause chunks (with pgvector support)
- Medical bill parsing results
- Claims, itemized line items, and adjudication EOBs
- Appeal drafts
- Multi-policy comparison matrix records
- Cryptographic hash-chained audit events
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
import threading
from typing import Any, Dict, List, Optional, Union
import uuid

import psycopg
from app.core.config import get_settings
from app.core.exceptions import DatabaseConnectionException
from app.db.session import db_manager
from app.schemas.appeal import ClaimAppealDraft
from app.schemas.audit import AuditEvent, AuditEventCreate
from app.schemas.claim import BillExtractionResult, ClaimRecord
from app.schemas.comparison import ComparisonRecord
from app.schemas.policy import ExtractedClause, PolicyExtractionResult

logger = logging.getLogger("claimwise.db.postgres_store")

_lock = threading.RLock()


SCHEMA_SQL = """
SET LOCAL statement_timeout = '15s';

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'policyholder',
    phone_number TEXT,
    country TEXT,
    occupation_status TEXT,
    organization TEXT,
    address TEXT,
    tier INTEGER DEFAULT 1,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    document_name TEXT NOT NULL,
    document_hash TEXT NOT NULL,
    title TEXT,
    insurer_name TEXT,
    policy_type TEXT DEFAULT 'health',
    total_clauses INTEGER DEFAULT 0,
    persistence_mode TEXT DEFAULT 'persistent_db',
    user_id TEXT,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_policies_user_id ON policies(user_id);
CREATE INDEX IF NOT EXISTS idx_policies_doc_hash ON policies(document_hash);

CREATE TABLE IF NOT EXISTS policy_chunks (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    clause_id TEXT NOT NULL,
    clause_heading TEXT,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    document_hash TEXT NOT NULL,
    embedding vector(1024),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_policy_chunks_policy_id ON policy_chunks(policy_id);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    policy_id TEXT,
    claim_reference TEXT,
    bill_id TEXT,
    total_billed_cents BIGINT DEFAULT 0,
    status TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_claims_user_id ON claims(user_id);
CREATE INDEX IF NOT EXISTS idx_claims_policy_id ON claims(policy_id);

CREATE TABLE IF NOT EXISTS bills (
    bill_id TEXT PRIMARY KEY,
    document_name TEXT NOT NULL,
    document_hash TEXT NOT NULL,
    total_billed_cents BIGINT DEFAULT 0,
    data JSONB NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS claim_documents (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    content BYTEA NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_claim_documents_claim_id ON claim_documents(claim_id);

CREATE TABLE IF NOT EXISTS appeal_drafts (
    draft_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_appeal_drafts_claim_id ON appeal_drafts(claim_id);

CREATE TABLE IF NOT EXISTS comparisons (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_comparisons_user_id ON comparisons(user_id);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    sequence_number BIGINT UNIQUE NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    outcome TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_events_seq ON audit_events(sequence_number);
CREATE INDEX IF NOT EXISTS idx_audit_events_user_id ON audit_events(user_id);
"""


class PostgresStore:
    """Thread-safe PostgreSQL persistent storage manager backed by Neon."""

    def __init__(self):
        self._initialized = False

    @contextmanager
    def _connection(self):
        """Context manager providing a pooled PostgreSQL connection."""
        self._ensure_init()
        with db_manager.sync_connection() as conn:
            yield conn

    def _ensure_init(self) -> None:
        """Ensure database schema is created on first access."""
        if not self._initialized:
            self.init_db()
        if not self._initialized:
            raise DatabaseConnectionException("The database is temporarily unavailable. Please retry shortly.")

    def init_db(self) -> None:
        """Create extensions, tables, and indexes in PostgreSQL if not present."""
        with _lock:
            if self._initialized:
                return
            settings = get_settings()
            if not settings.database_url or "placeholder" in settings.database_url:
                return
            try:
                # Use connection pool for fast multiplexed connection
                with db_manager.sync_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SET LOCAL statement_timeout = '15s'")
                        try:
                            cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
                        except Exception as ext_err:
                            logger.info("Extension note: %s", ext_err)
                        try:
                            cur.execute('CREATE EXTENSION IF NOT EXISTS "vector";')
                        except Exception as ext_err:
                            logger.info("Extension note: %s", ext_err)
                        cur.execute(SCHEMA_SQL)
                self._initialized = True
                logger.info("Initialized PostgreSQL database schema on Neon successfully.")
            except Exception as exc:
                logger.warning("Could not initialize PostgreSQL schema: %s", type(exc).__name__)


    # --------------------------------------------------------------------------
    # POLICIES & CLAUSES
    # --------------------------------------------------------------------------

    def save_policy(self, policy_id: str, policy: PolicyExtractionResult, user_id: Optional[str] = None) -> None:
        """Save or update an extracted policy and its child clauses in PostgreSQL."""
        eff_user_id = user_id or getattr(policy, "user_id", None)
        if eff_user_id and hasattr(policy, "user_id"):
            policy.user_id = eff_user_id
        policy.persistence_mode = "persistent_db"
        policy.policy_id = policy_id
        data_json = policy.model_dump_json()
        now_ts = policy.uploaded_at if hasattr(policy, "uploaded_at") and policy.uploaded_at else datetime.now(timezone.utc)
        title = policy.document_name.rsplit(".", 1)[0].replace("_", " ").title()

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO policies (
                        id, document_name, document_hash, title, insurer_name,
                        policy_type, total_clauses, persistence_mode, user_id,
                        data, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(id) DO UPDATE SET
                        document_name = EXCLUDED.document_name,
                        document_hash = EXCLUDED.document_hash,
                        title = EXCLUDED.title,
                        insurer_name = EXCLUDED.insurer_name,
                        policy_type = EXCLUDED.policy_type,
                        total_clauses = EXCLUDED.total_clauses,
                        persistence_mode = EXCLUDED.persistence_mode,
                        user_id = EXCLUDED.user_id,
                        data = EXCLUDED.data,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    (
                        policy_id,
                        policy.document_name,
                        policy.document_hash,
                        title,
                        "Health Insurance",
                        "health",
                        policy.total_clauses,
                        "persistent_db",
                        eff_user_id,
                        data_json,
                        now_ts,
                        now_ts,
                    ),
                )

                # Refresh chunks
                cur.execute("DELETE FROM policy_chunks WHERE policy_id = %s;", (policy_id,))
                chunk_rows = []
                for idx, clause in enumerate(policy.clauses):
                    from app.services.policy_extraction_validation import is_clause_evidence_eligible
                    if not is_clause_evidence_eligible(clause):
                        continue
                    chunk_id = str(uuid.uuid4())
                    chunk_rows.append((
                        chunk_id,
                        policy_id,
                        idx,
                        clause.page_number,
                        clause.clause_id,
                        clause.clause_heading,
                        clause.text,
                        clause.token_count,
                        clause.document_hash,
                        json.dumps(clause.model_dump(mode="json", exclude={"text"})),
                    ))
                if chunk_rows:
                    cur.executemany(
                        """
                        INSERT INTO policy_chunks (
                            id, policy_id, chunk_index, page_number,
                            clause_id, clause_heading, content,
                            token_count, document_hash, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        chunk_rows,
                    )

    def get_policy(self, policy_id: str) -> Optional[PolicyExtractionResult]:
        """Retrieve policy extraction result by ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM policies WHERE id = %s;", (policy_id,))
                row = cur.fetchone()
                if row:
                    raw_data = row[0]
                    if isinstance(raw_data, dict):
                        return PolicyExtractionResult.model_validate(raw_data)
                    return PolicyExtractionResult.model_validate_json(raw_data)
                return None

    def list_policies(self, user_id: Optional[str] = None) -> Dict[str, PolicyExtractionResult]:
        """List saved policies as a dictionary of policy_id -> PolicyExtractionResult."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                if user_id is not None:
                    cur.execute("SELECT id, data FROM policies WHERE user_id = %s ORDER BY created_at ASC;", (user_id,))
                else:
                    cur.execute("SELECT id, data FROM policies ORDER BY created_at ASC;")
                results: Dict[str, PolicyExtractionResult] = {}
                for row in cur.fetchall():
                    try:
                        p_id = row[0]
                        raw_data = row[1]
                        if isinstance(raw_data, dict):
                            results[p_id] = PolicyExtractionResult.model_validate(raw_data)
                        else:
                            results[p_id] = PolicyExtractionResult.model_validate_json(raw_data)
                    except Exception as exc:
                        logger.warning("Failed to deserialize stored policy %s: %s", row[0], type(exc).__name__)
                return results

    def delete_policy(self, policy_id: str) -> bool:
        """Delete policy and associated clauses by ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM policies WHERE id = %s;", (policy_id,))
                return cur.rowcount > 0

    def clear_policies(self) -> None:
        """Clear all policies from persistent storage."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM policies;")

    # --------------------------------------------------------------------------
    # CLAIMS
    # --------------------------------------------------------------------------

    def save_claim(self, claim: ClaimRecord) -> None:
        """Persist or update a ClaimRecord in PostgreSQL."""
        data_json = claim.model_dump_json()
        now_ts = claim.updated_at if hasattr(claim, "updated_at") and claim.updated_at else datetime.now(timezone.utc)
        created_ts = claim.created_at if hasattr(claim, "created_at") and claim.created_at else now_ts

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO claims (
                        id, user_id, policy_id, claim_reference, bill_id,
                        total_billed_cents, status, data, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        policy_id = EXCLUDED.policy_id,
                        claim_reference = EXCLUDED.claim_reference,
                        bill_id = EXCLUDED.bill_id,
                        total_billed_cents = EXCLUDED.total_billed_cents,
                        status = EXCLUDED.status,
                        data = EXCLUDED.data,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    (
                        claim.id,
                        claim.user_id,
                        claim.policy_id,
                        claim.claim_reference,
                        claim.bill_id,
                        claim.total_billed_cents,
                        claim.status.value if hasattr(claim.status, "value") else str(claim.status),
                        data_json,
                        created_ts,
                        now_ts,
                    ),
                )

    def get_claim(self, claim_id: str) -> Optional[ClaimRecord]:
        """Retrieve ClaimRecord by ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM claims WHERE id = %s;", (claim_id,))
                row = cur.fetchone()
                if row:
                    raw_data = row[0]
                    if isinstance(raw_data, dict):
                        return ClaimRecord.model_validate(raw_data)
                    return ClaimRecord.model_validate_json(raw_data)
                return None

    def list_claims(self, user_id: Optional[str] = None) -> List[ClaimRecord]:
        """List claims, optionally filtered by user ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute("SELECT data FROM claims WHERE user_id = %s ORDER BY created_at ASC;", (user_id,))
                else:
                    cur.execute("SELECT data FROM claims ORDER BY created_at ASC;")
                claims: List[ClaimRecord] = []
                for row in cur.fetchall():
                    try:
                        raw_data = row[0]
                        if isinstance(raw_data, dict):
                            claims.append(ClaimRecord.model_validate(raw_data))
                        else:
                            claims.append(ClaimRecord.model_validate_json(raw_data))
                    except Exception as exc:
                        logger.warning("Failed to deserialize stored claim: %s", type(exc).__name__)
                return claims

    def delete_claim(self, claim_id: str) -> bool:
        """Delete claim record by ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM claims WHERE id = %s;", (claim_id,))
                return cur.rowcount > 0

    def clear_claims(self) -> None:
        """Clear all claims from persistent storage."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM claims;")

    def save_claim_document(
        self, document_id: str, claim_id: str, file_name: str,
        mime_type: str, content: bytes, uploaded_at: datetime,
    ) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO claim_documents
                    (id, claim_id, file_name, mime_type, file_size_bytes, content, uploaded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);""",
                    (document_id, claim_id, file_name, mime_type, len(content), content, uploaded_at),
                )

    def get_claim_document(self, claim_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, file_name, mime_type, file_size_bytes, content, uploaded_at FROM claim_documents WHERE claim_id = %s AND id = %s;",
                    (claim_id, document_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0], "file_name": row[1], "mime_type": row[2],
                    "file_size_bytes": row[3], "content": bytes(row[4]), "uploaded_at": row[5],
                }

    # --------------------------------------------------------------------------
    # BILLS
    # --------------------------------------------------------------------------

    def save_bill(self, bill: BillExtractionResult) -> None:
        """Persist or update a BillExtractionResult in PostgreSQL."""
        data_json = bill.model_dump_json()
        now_ts = bill.uploaded_at if hasattr(bill, "uploaded_at") and bill.uploaded_at else datetime.now(timezone.utc)

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bills (
                        bill_id, document_name, document_hash, total_billed_cents, data, uploaded_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(bill_id) DO UPDATE SET
                        document_name = EXCLUDED.document_name,
                        document_hash = EXCLUDED.document_hash,
                        total_billed_cents = EXCLUDED.total_billed_cents,
                        data = EXCLUDED.data,
                        uploaded_at = EXCLUDED.uploaded_at;
                    """,
                    (
                        bill.bill_id,
                        bill.document_name,
                        bill.document_hash,
                        bill.total_billed_cents,
                        data_json,
                        now_ts,
                    ),
                )

    def get_bill(self, bill_id: str) -> Optional[BillExtractionResult]:
        """Retrieve parsed bill by ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM bills WHERE bill_id = %s;", (bill_id,))
                row = cur.fetchone()
                if row:
                    raw_data = row[0]
                    if isinstance(raw_data, dict):
                        return BillExtractionResult.model_validate(raw_data)
                    return BillExtractionResult.model_validate_json(raw_data)
                return None

    def list_bills(self) -> Dict[str, BillExtractionResult]:
        """List all parsed bills."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bill_id, data FROM bills ORDER BY uploaded_at ASC;")
                bills: Dict[str, BillExtractionResult] = {}
                for row in cur.fetchall():
                    try:
                        raw_data = row[1]
                        if isinstance(raw_data, dict):
                            bills[row[0]] = BillExtractionResult.model_validate(raw_data)
                        else:
                            bills[row[0]] = BillExtractionResult.model_validate_json(raw_data)
                    except Exception as exc:
                        logger.warning("Failed to deserialize bill: %s", type(exc).__name__)
                return bills

    def delete_bill(self, bill_id: str) -> bool:
        """Delete parsed bill by ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM bills WHERE bill_id = %s;", (bill_id,))
                return cur.rowcount > 0

    def clear_bills(self) -> None:
        """Clear all bills from persistent storage."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM bills;")

    # --------------------------------------------------------------------------
    # APPEAL DRAFTS
    # --------------------------------------------------------------------------

    def save_appeal_draft(self, draft: Any) -> None:
        """Persist or update an appeal draft in PostgreSQL."""
        data_json = draft.model_dump_json() if hasattr(draft, "model_dump_json") else json.dumps(draft)
        now_ts = datetime.now(timezone.utc)
        draft_id = getattr(draft, "draft_id", str(uuid.uuid4()))
        claim_id = getattr(draft, "claim_id", "")

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO appeal_drafts (draft_id, claim_id, data, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(draft_id) DO UPDATE SET
                        claim_id = EXCLUDED.claim_id,
                        data = EXCLUDED.data,
                        created_at = EXCLUDED.created_at;
                    """,
                    (draft_id, claim_id, data_json, now_ts),
                )

    def get_appeal_draft(self, claim_or_draft_id: str) -> Optional[ClaimAppealDraft]:
        """Retrieve appeal draft by draft_id or claim_id."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data FROM appeal_drafts WHERE draft_id = %s OR claim_id = %s LIMIT 1;",
                    (claim_or_draft_id, claim_or_draft_id),
                )
                row = cur.fetchone()
                if row:
                    raw_data = row[0]
                    try:
                        if isinstance(raw_data, dict):
                            return ClaimAppealDraft.model_validate(raw_data)
                        return ClaimAppealDraft.model_validate_json(raw_data)
                    except Exception:
                        return raw_data if isinstance(raw_data, dict) else json.loads(raw_data)
                return None

    def list_appeal_drafts(self) -> Dict[str, Any]:
        """List appeal drafts indexed by both draft_id and claim_id."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT draft_id, claim_id, data FROM appeal_drafts;")
                drafts: Dict[str, Any] = {}
                for row in cur.fetchall():
                    raw_data = row[2]
                    try:
                        if isinstance(raw_data, dict):
                            obj = ClaimAppealDraft.model_validate(raw_data)
                        else:
                            obj = ClaimAppealDraft.model_validate_json(raw_data)
                    except Exception:
                        obj = raw_data if isinstance(raw_data, dict) else json.loads(raw_data)
                    drafts[row[0]] = obj
                    if row[1]:
                        drafts[row[1]] = obj
                return drafts

    def delete_appeal_draft(self, claim_or_draft_id: str) -> bool:
        """Delete appeal draft by draft_id or claim_id."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM appeal_drafts WHERE draft_id = %s OR claim_id = %s;",
                    (claim_or_draft_id, claim_or_draft_id),
                )
                return cur.rowcount > 0

    def clear_appeal_drafts(self) -> None:
        """Clear all appeal drafts."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM appeal_drafts;")

    # --------------------------------------------------------------------------
    # COMPARISONS
    # --------------------------------------------------------------------------

    def save_comparison(self, comparison: ComparisonRecord) -> None:
        """Persist or update a ComparisonRecord in PostgreSQL."""
        data_json = comparison.model_dump_json()
        now_ts = comparison.updated_at if hasattr(comparison, "updated_at") and comparison.updated_at else datetime.now(timezone.utc)
        created_ts = comparison.created_at if hasattr(comparison, "created_at") and comparison.created_at else now_ts

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO comparisons (id, user_id, title, data, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        title = EXCLUDED.title,
                        data = EXCLUDED.data,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    (
                        comparison.id,
                        comparison.user_id,
                        comparison.title,
                        data_json,
                        created_ts,
                        now_ts,
                    ),
                )

    def get_comparison(self, comparison_id: str) -> Optional[ComparisonRecord]:
        """Retrieve comparison record by ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM comparisons WHERE id = %s;", (comparison_id,))
                row = cur.fetchone()
                if row:
                    raw_data = row[0]
                    if isinstance(raw_data, dict):
                        return ComparisonRecord.model_validate(raw_data)
                    return ComparisonRecord.model_validate_json(raw_data)
                return None

    def list_comparisons(self, user_id: Optional[str] = None) -> List[ComparisonRecord]:
        """List comparison records, optionally filtered by user ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute("SELECT data FROM comparisons WHERE user_id = %s ORDER BY created_at ASC;", (user_id,))
                else:
                    cur.execute("SELECT data FROM comparisons ORDER BY created_at ASC;")
                comparisons: List[ComparisonRecord] = []
                for row in cur.fetchall():
                    try:
                        raw_data = row[0]
                        if isinstance(raw_data, dict):
                            comparisons.append(ComparisonRecord.model_validate(raw_data))
                        else:
                            comparisons.append(ComparisonRecord.model_validate_json(raw_data))
                    except Exception as exc:
                        logger.warning("Failed to deserialize comparison: %s", type(exc).__name__)
                return comparisons

    def delete_comparison(self, comparison_id: str) -> bool:
        """Delete comparison record by ID."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM comparisons WHERE id = %s;", (comparison_id,))
                return cur.rowcount > 0

    def clear_comparisons(self) -> None:
        """Clear all comparisons from persistent storage."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM comparisons;")

    # --------------------------------------------------------------------------
    # AUDIT EVENTS
    # --------------------------------------------------------------------------

    def save_audit_event(self, event: AuditEvent) -> None:
        """Persist an immutable cryptographic audit event in PostgreSQL."""
        data_json = event.model_dump_json()

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, sequence_number, timestamp, user_id, action,
                        resource_type, resource_id, outcome, previous_hash,
                        event_hash, data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(sequence_number) DO NOTHING;
                    """,
                    (
                        event.event_id,
                        event.sequence_number,
                        event.timestamp,
                        event.user_id,
                        event.action,
                        event.resource_type,
                        event.resource_id,
                        event.outcome,
                        event.previous_hash,
                        event.event_hash,
                        data_json,
                    ),
                )

    def record_audit_event_transactional(self, event_create: AuditEventCreate) -> AuditEvent:
        """
        Record a cryptographically hash-chained audit event within a serialized
        database transaction using a PostgreSQL advisory transaction lock (98234721).
        Guarantees strictly monotonic sequence allocation and previous-hash chaining
        under high concurrent write pressure across multiple worker processes.
        """
        from app.services.audit_service import audit_service
        now_utc = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())
        sanitized_meta = audit_service.sanitize_metadata(event_create.metadata) if event_create.metadata else {}

        with self._connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("SELECT pg_advisory_xact_lock(98234721);")
                except Exception:
                    pass

                cur.execute("SELECT data FROM audit_events ORDER BY sequence_number DESC LIMIT 1;")
                row = cur.fetchone()
                last_event: Optional[AuditEvent] = None
                if row:
                    try:
                        raw_data = row[0]
                        if isinstance(raw_data, dict):
                            last_event = AuditEvent.model_validate(raw_data)
                        else:
                            last_event = AuditEvent.model_validate_json(raw_data)
                    except Exception as exc:
                        logger.warning("Error parsing last event in transactional write: %s", type(exc).__name__)

                next_seq = (last_event.sequence_number + 1) if last_event else 1
                prev_hash = last_event.event_hash if last_event else "0" * 64

                event_hash = audit_service.calculate_hash(
                    sequence_number=next_seq,
                    timestamp=now_utc,
                    user_id=event_create.user_id,
                    action=event_create.action,
                    resource_type=event_create.resource_type,
                    resource_id=event_create.resource_id,
                    outcome=event_create.outcome,
                    metadata=sanitized_meta,
                    previous_hash=prev_hash,
                )

                event = AuditEvent(
                    event_id=event_id,
                    sequence_number=next_seq,
                    timestamp=now_utc.isoformat(),
                    user_id=event_create.user_id or "system",
                    action=event_create.action,
                    resource_type=event_create.resource_type,
                    resource_id=event_create.resource_id,
                    outcome=event_create.outcome,
                    metadata=sanitized_meta,
                    previous_hash=prev_hash,
                    event_hash=event_hash,
                )

                data_json = event.model_dump_json()
                cur.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, sequence_number, timestamp, user_id, action,
                        resource_type, resource_id, outcome, previous_hash,
                        event_hash, data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(sequence_number) DO NOTHING;
                    """,
                    (
                        event.event_id,
                        event.sequence_number,
                        event.timestamp,
                        event.user_id,
                        event.action,
                        event.resource_type,
                        event.resource_id,
                        event.outcome,
                        event.previous_hash,
                        event.event_hash,
                        data_json,
                    ),
                )
                conn.commit()
                return event

    def get_last_audit_event(self) -> Optional[AuditEvent]:
        """Return the most recent audit event recorded in persistent storage."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM audit_events ORDER BY sequence_number DESC LIMIT 1;")
                row = cur.fetchone()
                if row:
                    try:
                        raw_data = row[0]
                        if isinstance(raw_data, dict):
                            return AuditEvent.model_validate(raw_data)
                        return AuditEvent.model_validate_json(raw_data)
                    except Exception as exc:
                        logger.warning("Failed to deserialize last audit event: %s", type(exc).__name__)
                return None

    def list_audit_events(self) -> List[AuditEvent]:
        """List all audit events ordered by monotonic sequence number ascending."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data FROM audit_events ORDER BY sequence_number ASC;")
                events: List[AuditEvent] = []
                for row in cur.fetchall():
                    try:
                        raw_data = row[0]
                        if isinstance(raw_data, dict):
                            events.append(AuditEvent.model_validate(raw_data))
                        else:
                            events.append(AuditEvent.model_validate_json(raw_data))
                    except Exception as exc:
                        logger.warning("Failed to deserialize stored audit event: %s", type(exc).__name__)
                return events

    def clear_audit_events(self) -> None:
        """Clear audit events from persistent storage."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM audit_events;")


# Global singleton instance
local_store = PostgresStore()
LocalStore = PostgresStore  # Alias for compatibility


class LazyPersistentStore(dict):
    """Load a PostgreSQL snapshot only when a caller first reads it.

    Constructors must never contact the network: the API's liveness endpoint
    must be available even when a database or embedding provider is offline.
    """

    def __init__(self, store=None):
        super().__init__()
        self._store = store or local_store
        self._loaded = False
        self._load_lock = threading.RLock()

    def _records(self):
        raise NotImplementedError

    def _ensure_loaded(self):
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:
                return
            records = self._records()  # Failed reads remain retryable.
            for key, value in records.items():
                # A new record may have been saved before the first read.
                if not dict.__contains__(self, key):
                    dict.__setitem__(self, key, value)
            self._loaded = True

    def __getitem__(self, key):
        if not dict.__contains__(self, key):
            self._ensure_loaded()
        return dict.__getitem__(self, key)

    def __contains__(self, key):
        if not dict.__contains__(self, key):
            self._ensure_loaded()
        return dict.__contains__(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        self._ensure_loaded()
        return dict.__iter__(self)

    def __len__(self):
        self._ensure_loaded()
        return dict.__len__(self)

    def keys(self):
        self._ensure_loaded()
        return dict.keys(self)

    def values(self):
        self._ensure_loaded()
        return dict.values(self)

    def items(self):
        self._ensure_loaded()
        return dict.items(self)

    def copy(self):
        self._ensure_loaded()
        return dict.copy(self)

    def pop(self, key, *args):
        self._ensure_loaded()
        return dict.pop(self, key, *args)

    def __delitem__(self, key):
        self._ensure_loaded()
        return dict.__delitem__(self, key)

    def clear(self):
        dict.clear(self)
        self._loaded = True


class PersistentPolicyStore(LazyPersistentStore):
    """Dict-compatible store backed by PostgreSQL for policies."""

    def _records(self):
        return self._store.list_policies()

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        try:
            if isinstance(value, PolicyExtractionResult):
                self._store.save_policy(key, value)
            elif isinstance(value, dict):
                self._store.save_policy(key, PolicyExtractionResult.model_validate(value))
        except Exception as exc:
            logger.error("Failed to persist policy %s to PostgreSQL: %s", key, type(exc).__name__)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        try:
            self._store.delete_policy(key)
        except Exception as exc:
            logger.error("Failed to delete policy %s from PostgreSQL: %s", key, type(exc).__name__)

    def pop(self, key: str, *args) -> Any:
        self._ensure_loaded()
        try:
            self._store.delete_policy(key)
        except Exception as exc:
            logger.error("Failed to pop policy %s from PostgreSQL: %s", key, type(exc).__name__)
        return super().pop(key, *args)

    def clear(self) -> None:
        try:
            self._store.clear_policies()
        except Exception as exc:
            logger.error("Failed to clear policies in PostgreSQL: %s", type(exc).__name__)
        super().clear()


class PersistentClaimStore(LazyPersistentStore):
    """Dict-compatible store backed by PostgreSQL for claims."""

    def _records(self):
        return {claim.id: claim for claim in self._store.list_claims()}

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        try:
            if isinstance(value, ClaimRecord):
                self._store.save_claim(value)
            elif isinstance(value, dict):
                self._store.save_claim(ClaimRecord.model_validate(value))
        except Exception as exc:
            logger.error("Failed to persist claim %s to PostgreSQL: %s", key, type(exc).__name__)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        try:
            self._store.delete_claim(key)
        except Exception as exc:
            logger.error("Failed to delete claim %s from PostgreSQL: %s", key, type(exc).__name__)

    def pop(self, key: str, *args) -> Any:
        self._ensure_loaded()
        try:
            self._store.delete_claim(key)
        except Exception as exc:
            logger.error("Failed to pop claim %s from PostgreSQL: %s", key, type(exc).__name__)
        return super().pop(key, *args)

    def clear(self) -> None:
        try:
            self._store.clear_claims()
        except Exception as exc:
            logger.error("Failed to clear claims in PostgreSQL: %s", type(exc).__name__)
        super().clear()


class PersistentBillStore(LazyPersistentStore):
    """Dict-compatible store backed by PostgreSQL for parsed medical bills."""

    def _records(self):
        return self._store.list_bills()

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        try:
            if isinstance(value, BillExtractionResult):
                self._store.save_bill(value)
            elif isinstance(value, dict):
                self._store.save_bill(BillExtractionResult.model_validate(value))
        except Exception as exc:
            logger.error("Failed to persist bill %s to PostgreSQL: %s", key, type(exc).__name__)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        try:
            self._store.delete_bill(key)
        except Exception as exc:
            logger.error("Failed to delete bill %s from PostgreSQL: %s", key, type(exc).__name__)

    def pop(self, key: str, *args) -> Any:
        self._ensure_loaded()
        try:
            self._store.delete_bill(key)
        except Exception as exc:
            logger.error("Failed to pop bill %s from PostgreSQL: %s", key, type(exc).__name__)
        return super().pop(key, *args)

    def clear(self) -> None:
        try:
            self._store.clear_bills()
        except Exception as exc:
            logger.error("Failed to clear bills in PostgreSQL: %s", type(exc).__name__)
        super().clear()


class PersistentAppealDraftStore(LazyPersistentStore):
    """Dict-compatible store backed by PostgreSQL for appeal drafts."""

    def _records(self):
        return self._store.list_appeal_drafts()

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        try:
            self._store.save_appeal_draft(value)
        except Exception as exc:
            logger.error("Failed to persist appeal draft %s to PostgreSQL: %s", key, type(exc).__name__)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        try:
            self._store.delete_appeal_draft(key)
        except Exception as exc:
            logger.error("Failed to delete appeal draft %s from PostgreSQL: %s", key, type(exc).__name__)

    def pop(self, key: str, *args) -> Any:
        self._ensure_loaded()
        try:
            self._store.delete_appeal_draft(key)
        except Exception as exc:
            logger.error("Failed to pop appeal draft %s from PostgreSQL: %s", key, type(exc).__name__)
        return super().pop(key, *args)

    def clear(self) -> None:
        try:
            self._store.clear_appeal_drafts()
        except Exception as exc:
            logger.error("Failed to clear appeal drafts in PostgreSQL: %s", type(exc).__name__)
        super().clear()


class PersistentComparisonStore(LazyPersistentStore):
    """Dict-compatible store backed by PostgreSQL for multi-policy comparisons."""

    def _records(self):
        return {record.id: record for record in self._store.list_comparisons()}

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        try:
            if isinstance(value, ComparisonRecord):
                self._store.save_comparison(value)
            elif isinstance(value, dict):
                self._store.save_comparison(ComparisonRecord.model_validate(value))
        except Exception as exc:
            logger.error("Failed to persist comparison %s to PostgreSQL: %s", key, type(exc).__name__)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        try:
            self._store.delete_comparison(key)
        except Exception as exc:
            logger.error("Failed to delete comparison %s from PostgreSQL: %s", key, type(exc).__name__)

    def pop(self, key: str, *args) -> Any:
        self._ensure_loaded()
        try:
            self._store.delete_comparison(key)
        except Exception as exc:
            logger.error("Failed to pop comparison %s from PostgreSQL: %s", key, type(exc).__name__)
        return super().pop(key, *args)

    def clear(self) -> None:
        try:
            self._store.clear_comparisons()
        except Exception as exc:
            logger.error("Failed to clear comparisons in PostgreSQL: %s", type(exc).__name__)
        super().clear()
