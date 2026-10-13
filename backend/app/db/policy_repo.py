"""Database repository for Policy and Policy Chunk entities.

Interacts with PostgreSQL (Supabase) tables:
- public.policies
- public.policy_chunks
Strictly avoids faking successful persistence when database connectivity is unverified.
"""

import json
import logging
from typing import Any, Dict, List, Optional
import uuid

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
    ) -> Optional[str]:
        """
        Persist policy record and child chunks in PostgreSQL.
        
        Returns:
            policy_id (UUID string) if successfully committed, or None if database is unreachable.
        """
        conn = await db_manager.get_connection()
        if not conn:
            logger.info("Database connection unavailable. Skipping persistent write.")
            return None

        policy_id = str(uuid.uuid4())

        try:
            async with conn.transaction():
                # 1. Insert into public.policies
                await conn.execute(
                    """
                    INSERT INTO public.policies (
                        id, user_id, title, insurer_name, policy_number,
                        policy_type, deductible_amount_cents, out_of_pocket_max_cents,
                        status, document_sha256
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
                    """,
                    uuid.UUID(policy_id),
                    uuid.UUID(user_id),
                    title,
                    insurer_name,
                    policy_number,
                    policy_type.value,
                    deductible_cents,
                    out_of_pocket_max_cents,
                    PolicyStatus.ACTIVE.value,
                    document_hash,
                )

                # 2. Insert into public.policy_chunks
                for idx, clause in enumerate(clauses):
                    chunk_id = uuid.uuid4()
                    meta = {
                        "heading_confidence": clause.heading_confidence,
                        "section_number": clause.section_number,
                    }
                    await conn.execute(
                        """
                        INSERT INTO public.policy_chunks (
                            id, policy_id, chunk_index, page_number,
                            section_heading, clause_identifier, content,
                            token_count, metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
                        """,
                        chunk_id,
                        uuid.UUID(policy_id),
                        idx,
                        clause.page_number,
                        clause.clause_heading,
                        clause.clause_id,
                        clause.text,
                        clause.token_count,
                        json.dumps(meta),
                    )

            logger.info("Successfully persisted policy %s with %d chunks to database.", policy_id, len(clauses))
            return policy_id

        except Exception as exc:
            logger.warning("Database write failed for policy %s: %s", policy_id, exc)
            return None
        finally:
            await conn.close()


policy_repo = PolicyRepository()
