"""Database repository for Policy and Policy Chunk entities in Neon PostgreSQL."""

import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.db.local_store import local_store
from app.db.session import db_manager
from app.models.domain import PolicyStatus, PolicyType
from app.schemas.policy import ExtractedClause, PolicyExtractionResult

logger = logging.getLogger("claimwise.db.policy_repo")


class PolicyRepository:
    """PostgreSQL repository for saving and querying parsed policies and chunks."""

    @classmethod
    async def save_policy_and_chunks(
        cls,
        user_id: str,
        title: str,
        insurer_name: str,
        policy_type: PolicyType,
        document_hash: str,
        clauses: List[ExtractedClause],
        deductible_cents: int = 0,
        out_of_pocket_max_cents: int = 0,
        policy_number: Optional[str] = None,
        extraction_result: Optional[PolicyExtractionResult] = None,
    ) -> Optional[str]:
        """
        Persist policy record and child chunks in Neon PostgreSQL.
        
        Returns:
            policy_id (string) if successfully committed, or None if database write fails.
        """
        policy_id = str(uuid.uuid4())

        # If full extraction_result is provided, use local_store which handles JSONB and chunks
        if extraction_result:
            try:
                extraction_result.policy_id = policy_id
                extraction_result.user_id = user_id
                extraction_result.persistence_mode = "persistent_db"
                local_store.save_policy(policy_id, extraction_result, user_id=user_id)
                logger.info("Successfully persisted policy %s to PostgreSQL via store.", policy_id)
                return policy_id
            except Exception as exc:
                logger.warning("PostgresStore write failed for policy %s: %s", policy_id, type(exc).__name__)

        conn = await db_manager.get_connection()
        if not conn:
            logger.info("Database connection unavailable.")
            return None

        try:
            async with conn.transaction():
                policy_data = {
                    "document_name": title,
                    "document_hash": document_hash,
                    "file_size_bytes": 0,
                    "total_pages": max([c.page_number for c in clauses], default=1),
                    "total_clauses": len(clauses),
                    "is_scanned": False,
                    "has_extractable_text": True,
                    "status": "success",
                    "message": "Policy stored in PostgreSQL database.",
                    "pages": [],
                    "clauses": [c.model_dump() for c in clauses],
                    "persistence_mode": "persistent_db",
                    "policy_id": policy_id,
                    "user_id": user_id,
                }
                await conn.execute(
                    """
                    INSERT INTO policies (
                        id, document_name, document_hash, title, insurer_name,
                        policy_type, total_clauses, persistence_mode, user_id,
                        data, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        insurer_name = EXCLUDED.insurer_name,
                        data = EXCLUDED.data,
                        updated_at = NOW();
                    """,
                    policy_id,
                    title,
                    document_hash,
                    title,
                    insurer_name,
                    policy_type.value if hasattr(policy_type, "value") else str(policy_type),
                    len(clauses),
                    "persistent_db",
                    str(user_id),
                    json.dumps(policy_data),
                )

                for idx, clause in enumerate(clauses):
                    from app.services.policy_extraction_validation import is_clause_evidence_eligible
                    if not is_clause_evidence_eligible(clause):
                        continue
                    chunk_id = str(uuid.uuid4())
                    meta = clause.model_dump(mode="json", exclude={"text"})
                    await conn.execute(
                        """
                        INSERT INTO policy_chunks (
                            id, policy_id, chunk_index, page_number,
                            clause_id, clause_heading, content,
                            token_count, document_hash, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
                        """,
                        chunk_id,
                        policy_id,
                        idx,
                        clause.page_number,
                        clause.clause_id,
                        clause.clause_heading,
                        clause.text,
                        clause.token_count,
                        clause.document_hash,
                        json.dumps(meta),
                    )

            logger.info("Successfully persisted policy %s with %d chunks to PostgreSQL.", policy_id, len(clauses))
            return policy_id

        except Exception as exc:
            logger.warning("Database write failed for policy %s: %s", policy_id, type(exc).__name__)
            return None
        finally:
            await conn.close()

    @classmethod
    def get_policy(cls, policy_id: str) -> Optional[PolicyExtractionResult]:
        """Retrieve policy by ID from persistent store."""
        return local_store.get_policy(policy_id)

    @classmethod
    def list_policies(cls, user_id: Optional[str] = None) -> List[PolicyExtractionResult]:
        """List policies, optionally filtered by user_id."""
        return list(local_store.list_policies(user_id=user_id).values())

    @classmethod
    def delete_policy(cls, policy_id: str) -> bool:
        """Delete policy by ID from persistent store."""
        return local_store.delete_policy(policy_id)


policy_repo = PolicyRepository()
