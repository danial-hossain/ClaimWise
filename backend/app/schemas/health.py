"""Pydantic schemas for health and readiness endpoints."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness check response."""
    status: str = Field(default="healthy", description="Application liveness status")
    app_name: str = Field(..., description="Application name")
    environment: str = Field(..., description="Running environment")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of check"
    )


class ServiceComponentStatus(BaseModel):
    """Status report for a single external or internal subsystem."""
    status: str = Field(..., description="Component state: healthy, unconfigured, unreachable, degraded, or not_started")
    configured: bool = Field(..., description="Whether required credentials or endpoints are set")
    required: bool = Field(..., description="Whether this service is required for basic foundation")
    message: str = Field(..., description="Human-readable description of current readiness")
    details: Optional[Dict[str, str]] = Field(default=None, description="Optional diagnostic details")


class ReadinessResponse(BaseModel):
    """Comprehensive readiness check response."""
    ready: bool = Field(..., description="True if core server is ready to accept requests")
    status: str = Field(..., description="Overall readiness: operational, partial, or unready")
    app_name: str = Field(..., description="Application name")
    environment: str = Field(..., description="Runtime environment")
    version: str = Field(..., description="Application version")
    services: Dict[str, ServiceComponentStatus] = Field(
        ..., description="Status breakdown of dependent and optional subsystems"
    )
    unconfigured_optional_services: List[str] = Field(
        default_factory=list, description="List of optional services pending API keys"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of readiness check"
    )
