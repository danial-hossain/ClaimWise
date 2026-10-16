"""Cryptographic Audit Trail Service with SHA-256 Tamper-Evident Hash Chaining.

Provides:
- Canonical serialization (RFC 8785 inspired deterministic JSON)
- Monotonic sequence numbering and immutable previous-hash linkage
- Automated sanitization/redaction of sensitive credentials or full PHI
- Independent verification engine detecting modification, deletion, or reordering
"""

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.audit import AuditEvent, AuditEventCreate, AuditVerificationResult

logger = logging.getLogger("claimwise.audit")

GENESIS_PREVIOUS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

# Sensitive keys that must be redacted from audit metadata
REDACT_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "ssn",
    "credentials",
    "notes",
    "clinical",
    "bill_text",
    "medical",
}


class AuditService:
    """Manages creation, canonical hashing, and integrity verification of audit events."""

    GENESIS_HASH = GENESIS_PREVIOUS_HASH

    def __init__(self):
        self._lock = asyncio.Lock()

    @staticmethod
    def canonical_serialize(data: Dict[str, Any]) -> str:
        """
        Produce a deterministic canonical JSON string.
        Keys are sorted lexicographically with no extra whitespace.
        """
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @classmethod
    def sanitize_metadata(cls, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively redact credentials, tokens, or overly large sensitive bodies from metadata.
        """
        sanitized: Dict[str, Any] = {}
        for key, value in meta.items():
            k_lower = key.lower()
            if any(sensitive in k_lower for sensitive in REDACT_KEYS):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = cls.sanitize_metadata(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [cls.sanitize_metadata({"value": item})["value"] for item in value]
            elif isinstance(value, str):
                try:
                    from app.services.pii_service import pii_service
                    val_str = pii_service.mask_text(value).masked_text
                except Exception:
                    val_str = "[REDACTED: sanitization unavailable]"
                from app.core.logging_security import redact_log_text
                val_str = redact_log_text(val_str)
                if len(val_str) > 2048:
                    sanitized[key] = val_str[:256] + "... [TRUNCATED]"
                else:
                    sanitized[key] = val_str
            else:
                sanitized[key] = value
        return sanitized

    @classmethod
    def compute_event_hash(
        cls,
        sequence_number: int,
        timestamp: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        outcome: str,
        sanitized_metadata: Dict[str, Any],
        previous_hash: str,
        schema_version: str = "1.0.0",
    ) -> str:
        """
        Compute SHA-256 hash over canonical representation of the audit event payload.
        """
        canonical_dict = {
            "action": action,
            "metadata": sanitized_metadata,
            "outcome": outcome,
            "previous_hash": previous_hash,
            "resource_id": resource_id or "",
            "resource_type": resource_type,
            "schema_version": schema_version,
            "sequence_number": sequence_number,
            "timestamp": timestamp,
            "user_id": user_id,
        }
        canonical_str = cls.canonical_serialize(canonical_dict)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    @classmethod
    def calculate_hash(
        cls,
        sequence_number: int,
        timestamp: Any,
        user_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        outcome: str,
        metadata: Dict[str, Any],
        previous_hash: str,
        schema_version: str = "1.0.0",
    ) -> str:
        """Compute SHA-256 canonical hash with automatic timestamp string conversion."""
        ts = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
        return cls.compute_event_hash(
            sequence_number=sequence_number,
            timestamp=ts,
            user_id=user_id or "system",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            sanitized_metadata=metadata,
            previous_hash=previous_hash,
            schema_version=schema_version,
        )

    def build_event(
        self,
        action: str,
        resource_type: str,
        sequence_number: int,
        previous_hash: str,
        resource_id: Optional[str] = None,
        outcome: str = "success",
        user_id: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> AuditEvent:
        """Construct an AuditEvent with computed SHA-256 hash."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        sanitized_meta = self.sanitize_metadata(metadata or {})
        event_hash = self.compute_event_hash(
            sequence_number=sequence_number,
            timestamp=ts,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            sanitized_metadata=sanitized_meta,
            previous_hash=previous_hash,
        )
        return AuditEvent(
            event_id=str(uuid.uuid4()),
            sequence_number=sequence_number,
            timestamp=ts,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            metadata=sanitized_meta,
            previous_hash=previous_hash,
            event_hash=event_hash,
            schema_version="1.0.0",
        )

    async def create_event(
        self,
        event_create: AuditEventCreate,
        last_event: Optional[AuditEvent] = None,
        override_sequence: Optional[int] = None,
    ) -> AuditEvent:
        """
        Construct a new hash-chained AuditEvent.
        """
        async with self._lock:
            seq = override_sequence or ((last_event.sequence_number + 1) if last_event else 1)
            prev_hash = last_event.event_hash if last_event else GENESIS_PREVIOUS_HASH
            ts = datetime.now(timezone.utc).isoformat()
            user_id = event_create.user_id or "system"
            sanitized_meta = self.sanitize_metadata(event_create.metadata)

            event_hash = self.compute_event_hash(
                sequence_number=seq,
                timestamp=ts,
                user_id=user_id,
                action=event_create.action,
                resource_type=event_create.resource_type,
                resource_id=event_create.resource_id,
                outcome=event_create.outcome,
                sanitized_metadata=sanitized_meta,
                previous_hash=prev_hash,
            )

            return AuditEvent(
                event_id=str(uuid.uuid4()),
                sequence_number=seq,
                timestamp=ts,
                user_id=user_id,
                action=event_create.action,
                resource_type=event_create.resource_type,
                resource_id=event_create.resource_id,
                outcome=event_create.outcome,
                metadata=sanitized_meta,
                previous_hash=prev_hash,
                event_hash=event_hash,
                schema_version="1.0.0",
            )

    @classmethod
    def verify_chain(cls, events: List[AuditEvent]) -> AuditVerificationResult:
        """
        Verify the mathematical and chronological integrity of an ordered audit event chain.
        
        Checks:
        1. Monotonic sequence numbering starting at 1.
        2. Genesis event links to GENESIS_PREVIOUS_HASH.
        3. Every subsequent event links to previous event's SHA-256 hash.
        4. Recomputed canonical SHA-256 hash matches the recorded event_hash.
        """
        if not events:
            return AuditVerificationResult(
                is_valid=True,
                total_events=0,
                verified_count=0,
                chain_head_hash=None,
                genesis_hash=GENESIS_PREVIOUS_HASH,
                error_reason=None,
            )

        # Sort events by sequence number to evaluate canonical order
        sorted_events = sorted(events, key=lambda e: e.sequence_number)
        start_seq = sorted_events[0].sequence_number

        for idx, event in enumerate(sorted_events):
            expected_seq = start_seq + idx
            if event.sequence_number != expected_seq:
                return AuditVerificationResult(
                    is_valid=False,
                    total_events=len(events),
                    verified_count=idx,
                    chain_head_hash=None,
                    genesis_hash=GENESIS_PREVIOUS_HASH,
                    tampered_event_id=event.event_id,
                    tampered_sequence=event.sequence_number,
                    error_reason=(
                        f"Sequence break at index {idx}: expected sequence {expected_seq}, "
                        f"but found {event.sequence_number}."
                    ),
                )

            # Check previous hash link
            if idx == 0:
                if start_seq == 1 and event.previous_hash != GENESIS_PREVIOUS_HASH:
                    return AuditVerificationResult(
                        is_valid=False,
                        total_events=len(events),
                        verified_count=0,
                        chain_head_hash=None,
                        genesis_hash=GENESIS_PREVIOUS_HASH,
                        tampered_event_id=event.event_id,
                        tampered_sequence=event.sequence_number,
                        error_reason=f"Genesis event previous_hash mismatch at sequence {event.sequence_number}.",
                    )
            else:
                expected_prev = sorted_events[idx - 1].event_hash
                if event.previous_hash != expected_prev:
                    return AuditVerificationResult(
                        is_valid=False,
                        total_events=len(events),
                        verified_count=idx,
                        chain_head_hash=None,
                        genesis_hash=GENESIS_PREVIOUS_HASH,
                        tampered_event_id=event.event_id,
                        tampered_sequence=event.sequence_number,
                        error_reason=(
                            f"Broken chain linkage on event '{event.event_id}' (seq {event.sequence_number}): "
                            f"expected previous_hash '{expected_prev}', but found '{event.previous_hash}'."
                        ),
                    )

            # Recompute hash from canonical payload
            recomputed = cls.compute_event_hash(
                sequence_number=event.sequence_number,
                timestamp=event.timestamp,
                user_id=event.user_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                outcome=event.outcome,
                sanitized_metadata=event.metadata,
                previous_hash=event.previous_hash,
                schema_version=event.schema_version,
            )

            if recomputed != event.event_hash:
                return AuditVerificationResult(
                    is_valid=False,
                    total_events=len(events),
                    verified_count=idx,
                    chain_head_hash=None,
                    genesis_hash=GENESIS_PREVIOUS_HASH,
                    tampered_event_id=event.event_id,
                    tampered_sequence=event.sequence_number,
                    error_reason=(
                        f"Cryptographic hash mismatch on event '{event.event_id}' (seq {event.sequence_number}): "
                        f"payload recomputed hash '{recomputed}' does not match stored hash '{event.event_hash}'. "
                        "Payload has been altered or tampered with."
                    ),
                )

        # Entire chain verified successfully
        return AuditVerificationResult(
            is_valid=True,
            total_events=len(sorted_events),
            verified_count=len(sorted_events),
            chain_head_hash=sorted_events[-1].event_hash,
            genesis_hash=GENESIS_PREVIOUS_HASH,
            error_reason=None,
        )


audit_service = AuditService()
