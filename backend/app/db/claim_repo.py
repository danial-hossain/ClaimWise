"""Database and Development Session Repository for Claim & Bill records.

Manages persistence for:
- Medical bill extractions (BillExtractionResult)
- Claims, itemized line items, and EOB calculations (ClaimRecord)
- Simulated sandbox submissions

Strictly distinguishes live PostgreSQL persistence from local development session storage.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.db.session import db_manager
from app.models.domain import ClaimStatus
from app.schemas.claim import (
    BillExtractionResult,
    ClaimRecord,
    ExplanationOfBenefits,
)

logger = logging.getLogger("claimwise.db.claim_repo")


class ClaimRepository:
    """
    Unified Claim Repository with live PostgreSQL write capabilities and
    an explicit in-memory development adapter for offline/unconnected mode.
    """

    def __init__(self):
        # In-memory stores for active development preview session
        self._dev_bills: Dict[str, BillExtractionResult] = {}
        self._dev_claims: Dict[str, ClaimRecord] = {}
        self._dev_appeal_drafts: Dict[str, Any] = {}

    def save_appeal_draft(self, draft: Any) -> None:
        """Store appeal draft in development session cache."""
        self._dev_appeal_drafts[draft.claim_id] = draft
        self._dev_appeal_drafts[draft.draft_id] = draft

    def get_appeal_draft(self, claim_or_draft_id: str) -> Optional[Any]:
        """Retrieve appeal draft by claim ID or draft ID."""
        return self._dev_appeal_drafts.get(claim_or_draft_id)

    def save_bill_extraction(self, bill: BillExtractionResult) -> None:
        """Store parsed bill in development preview session."""
        self._dev_bills[bill.bill_id] = bill

    def get_bill_extraction(self, bill_id: str) -> Optional[BillExtractionResult]:
        """Retrieve parsed bill by ID."""
        return self._dev_bills.get(bill_id)

    async def save_claim(self, claim: ClaimRecord) -> str:
        """
        Persist claim record. Attempts PostgreSQL write if connection is available;
        always updates in-memory development store.
        """
        # Always update development session cache
        self._dev_claims[claim.id] = claim

        # Attempt database write if connection is verified
        conn = await db_manager.get_connection()
        if not conn:
            logger.info("Database connection unavailable. Storing claim %s in development session store.", claim.id)
            return claim.id

        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO public.claims (
                        id, user_id, policy_id, claim_reference,
                        incident_date, claimed_amount_cents, approved_amount_cents,
                        status, line_items, adjudicated_items, eob_data,
                        sandbox_submission, bill_document_hash, bill_document_name,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        approved_amount_cents = EXCLUDED.approved_amount_cents,
                        line_items = EXCLUDED.line_items,
                        adjudicated_items = EXCLUDED.adjudicated_items,
                        eob_data = EXCLUDED.eob_data,
                        sandbox_submission = EXCLUDED.sandbox_submission,
                        updated_at = EXCLUDED.updated_at;
                    """,
                    uuid.UUID(claim.id) if len(claim.id) == 36 else uuid.uuid4(),
                    uuid.UUID(claim.user_id) if len(claim.user_id) == 36 else uuid.uuid4(),
                    uuid.UUID(claim.policy_id) if len(claim.policy_id) == 36 else None,
                    claim.claim_reference,
                    claim.incident_date,
                    claim.total_billed_cents,
                    claim.eob.total_illustrative_insurer_cents if claim.eob else 0,
                    claim.status.value,
                    json.dumps([item.model_dump() for item in claim.line_items]),
                    json.dumps([item.model_dump() for item in claim.adjudicated_items]),
                    json.dumps(claim.eob.model_dump()) if claim.eob else None,
                    json.dumps(claim.sandbox_submission) if claim.sandbox_submission else None,
                    claim.bill_document_hash,
                    claim.bill_document_name,
                    claim.created_at,
                    claim.updated_at,
                )
            logger.info("Successfully persisted claim %s to PostgreSQL.", claim.id)
        except Exception as exc:
            logger.warning("Database write failed for claim %s: %s (held in development preview).", claim.id, exc)
        finally:
            await conn.close()

        return claim.id

    def get_claim(self, claim_id: str) -> Optional[ClaimRecord]:
        """Retrieve claim by ID from development session store."""
        return self._dev_claims.get(claim_id)

    def list_claims(self, user_id: Optional[str] = None) -> List[ClaimRecord]:
        """
        List claims in active development session.
        If user_id is provided, filters to claims belonging to that user.
        """
        all_claims = list(self._dev_claims.values())
        if user_id:
            return [c for c in all_claims if c.user_id == user_id]
        return all_claims


claim_repo = ClaimRepository()
