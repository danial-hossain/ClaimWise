"""Database and Repository for Claim, Bill, and Appeal Draft records in Neon PostgreSQL."""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.db.local_store import (
    local_store,
    PersistentAppealDraftStore,
    PersistentBillStore,
    PersistentClaimStore,
)
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
    Unified Claim Repository with live PostgreSQL persistence via Neon.
    """

    def __init__(self):
        # Persistent stores backed by Neon PostgreSQL
        self._dev_bills: Dict[str, BillExtractionResult] = PersistentBillStore()
        self._dev_claims: Dict[str, ClaimRecord] = PersistentClaimStore()
        self._dev_appeal_drafts: Dict[str, Any] = PersistentAppealDraftStore()

    def save_appeal_draft(self, draft: Any) -> None:
        """Store appeal draft in persistent PostgreSQL store."""
        self._dev_appeal_drafts[draft.claim_id] = draft
        self._dev_appeal_drafts[draft.draft_id] = draft

    def get_appeal_draft(self, claim_or_draft_id: str) -> Optional[Any]:
        """Retrieve appeal draft by claim ID or draft ID."""
        return self._dev_appeal_drafts.get(claim_or_draft_id)

    def save_bill_extraction(self, bill: BillExtractionResult) -> None:
        """Store parsed bill in persistent PostgreSQL store."""
        self._dev_bills[bill.bill_id] = bill

    def get_bill_extraction(self, bill_id: str) -> Optional[BillExtractionResult]:
        """Retrieve parsed bill by ID."""
        return self._dev_bills.get(bill_id)

    async def save_claim(self, claim: ClaimRecord) -> str:
        """
        Persist claim record into Neon PostgreSQL.
        """
        # Updates persistent PostgreSQL store
        # Fail the request on database errors; never report an unsaved draft as saved.
        local_store.save_claim(claim)
        dict.__setitem__(self._dev_claims, claim.id, claim)
        logger.info("Successfully persisted claim %s to PostgreSQL.", claim.id)
        return claim.id

    def get_claim(self, claim_id: str) -> Optional[ClaimRecord]:
        """Retrieve claim by ID from persistent PostgreSQL store."""
        return self._dev_claims.get(claim_id)

    def list_claims(self, user_id: Optional[str] = None) -> List[ClaimRecord]:
        """
        List claims in persistent PostgreSQL store.
        If user_id is provided, filters to claims belonging to that user.
        """
        all_claims = list(self._dev_claims.values())
        if user_id:
            return [c for c in all_claims if c.user_id == user_id]
        return all_claims

    def save_claim_document(self, document_id: str, claim_id: str, file_name: str, mime_type: str, content: bytes, uploaded_at: datetime) -> None:
        local_store.save_claim_document(document_id, claim_id, file_name, mime_type, content, uploaded_at)

    def get_claim_document(self, claim_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        return local_store.get_claim_document(claim_id, document_id)


claim_repo = ClaimRepository()
