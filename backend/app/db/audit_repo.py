"""Database and session repository for the cryptographic audit log."""

import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.db.session import db_manager
from app.schemas.audit import AuditEvent, AuditEventCreate, AuditVerificationResult
from app.services.audit_service import audit_service

logger = logging.getLogger("claimwise.db.audit_repo")


class AuditRepository:
    """
    Unified Audit Repository supporting PostgreSQL persistence and
    an in-memory sequential session store for local development preview.
    """

    def __init__(self):
        # Monotonic in-memory chain of verified events
        self._events: List[AuditEvent] = []

    def get_last_event(self) -> Optional[AuditEvent]:
        """Return the most recent audit event in the chain."""
        return self._events[-1] if self._events else None

    async def record_event(
        self,
        event_create: AuditEventCreate,
    ) -> AuditEvent:
        """
        Create, cryptographically hash-chain, and record an audit event.
        """
        last_event = self.get_last_event()
        event = await audit_service.create_event(
            event_create=event_create,
            last_event=last_event,
        )
        self._events.append(event)

        # Attempt PostgreSQL persistence if connected
        conn = await db_manager.get_connection()
        if conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO public.audit_logs (
                            id, user_id, action, entity_type, entity_id,
                            details, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7);
                        """,
                        uuid.UUID(event.event_id),
                        uuid.UUID(event.user_id) if len(event.user_id) == 36 else None,
                        event.action,
                        event.resource_type,
                        uuid.UUID(event.resource_id) if event.resource_id and len(event.resource_id) == 36 else None,
                        json.dumps({
                            "sequence_number": event.sequence_number,
                            "previous_hash": event.previous_hash,
                            "event_hash": event.event_hash,
                            "outcome": event.outcome,
                            "schema_version": event.schema_version,
                            "metadata": event.metadata,
                        }),
                        event.timestamp,
                    )
                logger.info(
                    "Persisted audit event %s (seq %d, hash %s) to PostgreSQL.",
                    event.event_id,
                    event.sequence_number,
                    event.event_hash[:12],
                )
            except Exception as exc:
                logger.warning(
                    "Database write failed for audit event %s: %s (held in memory chain).",
                    event.event_id,
                    exc,
                )
            finally:
                await conn.close()

        return event

    def list_events(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """Query authorized audit events with pagination and filters."""
        filtered = self._events
        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]
        if action:
            filtered = [e for e in filtered if e.action == action]
        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]

        # Return latest events first
        reversed_list = list(reversed(filtered))
        return reversed_list[offset : offset + limit]

    def get_all_events(self) -> List[AuditEvent]:
        """Return all events in chronological sequence order."""
        return list(self._events)

    def verify_chain(self) -> AuditVerificationResult:
        """Run cryptographic hash-chain verification on all stored events."""
        return audit_service.verify_chain(self._events)


audit_repo = AuditRepository()
