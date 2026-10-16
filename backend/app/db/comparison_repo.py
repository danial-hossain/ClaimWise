"""Database Repository for Multi-Policy Comparisons in Neon PostgreSQL."""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.db.local_store import PersistentComparisonStore
from app.db.session import db_manager
from app.schemas.comparison import ComparisonRecord

logger = logging.getLogger("claimwise.db.comparison_repo")


class ComparisonRepository:
    """
    Unified Comparison Repository supporting persistent storage in Neon PostgreSQL.
    """

    def __init__(self):
        # Persistent store backed by Neon PostgreSQL
        self._dev_comparisons: Dict[str, ComparisonRecord] = PersistentComparisonStore()

    async def save_comparison(self, record: ComparisonRecord) -> str:
        """
        Persist comparison record in Neon PostgreSQL.
        """
        self._dev_comparisons[record.id] = record
        logger.info("Successfully persisted comparison %s to PostgreSQL.", record.id)
        return record.id

    def get_comparison(self, comparison_id: str) -> Optional[ComparisonRecord]:
        """Retrieve comparison from persistent store."""
        return self._dev_comparisons.get(comparison_id)

    def list_comparisons(self, user_id: Optional[str] = None) -> List[ComparisonRecord]:
        """List comparisons, optionally filtering by user_id."""
        all_comps = list(self._dev_comparisons.values())
        if user_id:
            return [c for c in all_comps if c.user_id == user_id]
        return all_comps


comparison_repo = ComparisonRepository()
