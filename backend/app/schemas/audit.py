"""Pydantic schemas for the Cryptographic Audit Trail."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class AuditEventCreate(BaseModel):
    """Payload to create an immutable audit record."""

    action: str = Field(..., description="Action type (e.g. policy.upload, claim.adjudicate)")
    resource_type: str = Field(..., description="Resource category (e.g. policy, claim, appeal)")
    resource_id: Optional[str] = Field(None, description="Identifier of the resource affected")
    outcome: str = Field(default="success", description="Outcome status (success, failed, denied)")
    user_id: Optional[str] = Field(None, description="Verified actor user identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Sanitized, non-sensitive audit metadata")


class AuditEvent(BaseModel):
    """Immutable, tamper-evident audit event with SHA-256 hash chaining."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sequence_number: int = Field(..., description="Monotonically increasing 1-based sequence number")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_id: str = Field(..., description="Verified actor user ID")
    action: str = Field(..., description="Action name")
    resource_type: str = Field(..., description="Resource entity type")
    resource_id: Optional[str] = Field(None, description="Target resource ID")
    outcome: str = Field(default="success", description="Operation outcome")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Redacted metadata payload")
    previous_hash: str = Field(..., description="SHA-256 hash of the immediately preceding audit event")
    event_hash: str = Field(..., description="SHA-256 hash of the canonical JSON representation of this event")
    schema_version: str = Field(default="1.0.0", description="Audit schema version")


class AuditVerificationResult(BaseModel):
    """Result of cryptographic verification across the audit event chain."""

    is_valid: bool = Field(..., description="True if all cryptographic hashes and links are verified")
    total_events: int = Field(..., description="Total number of evaluated events")
    verified_count: int = Field(..., description="Number of sequentially verified events")
    chain_head_hash: Optional[str] = Field(None, description="Current cryptographic head hash of the audit chain")
    genesis_hash: Optional[str] = Field(None, description="Genesis hash of the chain")
    tampered_event_id: Optional[str] = Field(None, description="ID of first tampered event if verification failed")
    tampered_sequence: Optional[int] = Field(None, description="Sequence number of tampered event")
    error_reason: Optional[str] = Field(None, description="Detailed diagnostic description of failure")
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditQueryFilter(BaseModel):
    """Filters for querying authorized audit logs."""

    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
