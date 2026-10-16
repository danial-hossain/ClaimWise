"""Database and session repository for the cryptographic audit log in Neon PostgreSQL."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.db.local_store import local_store
from app.db.session import db_manager
from app.core.exceptions import DatabaseConnectionException
from app.schemas.audit import AuditEvent, AuditEventCreate, AuditVerificationResult
from app.services.audit_service import audit_service

logger = logging.getLogger("claimwise.db.audit_repo")


class AuditRepository:
    """
    Unified Audit Repository supporting persistent PostgreSQL storage
    preserving the cryptographic hash chain across restarts.
    """

    def __init__(self):
        # Monotonic sequential chain of verified events loaded from Neon PostgreSQL
        self._events: List[AuditEvent] = []  # Hydrated by _sync_events on first use.
        self._lock = asyncio.Lock()

    def _sync_events(self) -> None:
        """Sync internal cache with persistent storage if external writes occurred."""
        last_stored = local_store.get_last_audit_event()
        if last_stored:
            if not self._events or self._events[-1].sequence_number < last_stored.sequence_number:
                self._events = local_store.list_audit_events()

    def get_last_event(self) -> Optional[AuditEvent]:
        """Return the most recent audit event in the chain."""
        self._sync_events()
        return self._events[-1] if self._events else None

    async def record_event(
        self,
        event_create: AuditEventCreate,
    ) -> AuditEvent:
        """
        Create, cryptographically hash-chain, and record an audit event in Neon PostgreSQL
        with transactional database locks supporting multi-worker concurrency.
        """
        async with self._lock:
            try:
                event = local_store.record_audit_event_transactional(event_create)
                self._events.append(event)
                logger.info(
                    "Persisted audit event %s (seq %d, hash %s) to Neon PostgreSQL.",
                    event.event_id,
                    event.sequence_number,
                    event.event_hash[:12],
                )
                return event
            except Exception as exc:
                logger.warning("Transactional audit persistence failed (%s).", type(exc).__name__)
                # Never fabricate a second chain or cache an event that was not committed.
                raise DatabaseConnectionException("Audit storage is temporarily unavailable.") from exc

    def list_events_with_count(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[AuditEvent], int]:
        """Query authorized audit events with pagination and filters, returning (events, total_count)."""
        self._sync_events()
        filtered = self._events
        if user_id is not None:
            filtered = [e for e in filtered if e.user_id == user_id]
        else:
            filtered = []
        if action:
            filtered = [e for e in filtered if e.action == action]
        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]
        if resource_id:
            filtered = [e for e in filtered if e.resource_id == resource_id]
        if outcome:
            filtered = [e for e in filtered if (e.outcome or "").lower() == outcome.lower()]

        total = len(filtered)
        reversed_list = list(reversed(filtered))
        return reversed_list[offset : offset + limit], total

    def list_events(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """Query authorized audit events with pagination and filters."""
        events, _ = self.list_events_with_count(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            limit=limit,
            offset=offset,
        )
        return events

    def get_all_events(self) -> List[AuditEvent]:
        """Return all events in chronological sequence order."""
        self._sync_events()
        return list(self._events)

    def verify_chain(self) -> AuditVerificationResult:
        """Run cryptographic hash-chain verification on all stored events."""
        self._sync_events()
        return audit_service.verify_chain(self._events)


audit_repo = AuditRepository()
