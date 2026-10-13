"""Standard API response envelopes and common models."""

from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    """Detailed error object."""
    code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[dict] = Field(default=None, description="Optional diagnostic details")


class APIResponse(BaseModel, Generic[DataT]):
    """Standard generic API response wrapper."""
    success: bool = Field(default=True, description="Indicates if the request succeeded")
    data: Optional[DataT] = Field(default=None, description="Response payload")
    error: Optional[ErrorDetail] = Field(default=None, description="Error payload if failed")


class SystemMetadata(BaseModel):
    """System information returned on root inspection."""
    name: str
    version: str
    tagline: str
    docs_url: str
    environment: str
