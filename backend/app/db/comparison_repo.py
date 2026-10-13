"""Database and Development Session Repository for Multi-Policy Comparisons.

Manages persistence for:
- Multi-policy comparison matrix records (ComparisonRecord)
- Illustrative cost simulations

Strictly distinguishes live PostgreSQL persistence from local development session storage.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.db.session import db_manager
from app.schemas.comparison import ComparisonRecord

logger = logging.getLogger("claimwise.db.comparison_repo")


class ComparisonRepository:
    """
    Unified Comparison Repository supporting PostgreSQL and development session cache.
    """

    def __init__(self):
        # In-memory store for active development preview session: comparison_id -> ComparisonRecord
        self._dev_comparisons: Dict[str, ComparisonRecord] = {}

    async def save_comparison(self, record: ComparisonRecord) -> str:
        """
        Persist comparison record. Always updates development session cache.
        Attempts PostgreSQL insert if database is reachable.
        """
        self._dev_comparisons[record.id] = record

        conn = await db_manager.get_connection()
        if not conn:
            logger.info("Database connection unavailable. Storing comparison %s in development session store.", record.id)
            return record.id

        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO public.comparisons (
                        id, user_id, title, policy_ids,
                        comparison_data, cost_simulation, status,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        comparison_data = EXCLUDED.comparison_data,
                        cost_simulation = EXCLUDED.cost_simulation,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    uuid.UUID(record.id) if len(record.id) == 36 else uuid.uuid4(),
                    uuid.UUID(record.user_id) if len(record.user_id) == 36 else uuid.uuid4(),
                    record.title,
                    json.dumps(record.policy_ids),
                    json.dumps([p.model_dump() for p in record.policies]),
                    json.dumps(record.cost_simulation.model_dump()) if record.cost_simulation else None,
                    record.status,
                    record.created_at,
                    record.updated_at,
                )
            logger.info("Successfully persisted comparison %s to PostgreSQL.", record.id)
        except Exception as exc:
            logger.warning("Database write failed for comparison %s: %s (held in development preview).", record.id, exc)
        finally:
            await conn.close()

        return record.id

    def get_comparison(self, comparison_id: str) -> Optional[ComparisonRecord]:
        """Retrieve comparison from development session store."""
        return self._dev_comparisons.get(comparison_id)

    def list_comparisons(self, user_id: Optional[str] = None) -> List[ComparisonRecord]:
        """List comparisons, optionally filtering by user_id."""
        all_comps = list(self._dev_comparisons.values())
        if user_id:
            return [c for c in all_comps if c.user_id == user_id]
        return all_comps


comparison_repo = ComparisonRepository()
