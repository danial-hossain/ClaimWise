"""Authentication schemas for ClaimWise."""

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field


class SignUpRequest(BaseModel):
    """Payload for registering a new user account."""
    email: str = Field(..., min_length=3, max_length=150, description="User's valid email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password with minimum 6 characters")
    full_name: str = Field(..., min_length=2, max_length=100, description="User's display full name")
    role: Literal["policyholder", "broker", "advocate"] = Field(default="policyholder", description="Public persona; does not confer administrative authority")
    phone_number: Optional[str] = Field(default=None, max_length=35, description="Contact phone number")
    country: Optional[str] = Field(default=None, max_length=100, description="Country of residence")
    occupation_status: Optional[str] = Field(default=None, max_length=50, description="Status: student, employee, self_employed, other")
    organization: Optional[str] = Field(default=None, max_length=150, description="School, university, or company name")


class LoginRequest(BaseModel):
    """Payload for user login."""
    email: str = Field(..., min_length=3, max_length=150, description="Registered email address")
    password: str = Field(..., min_length=1, max_length=128, description="Account password")


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    address: Optional[str] = Field(default=None, max_length=300)


class DemoLoginRequest(BaseModel):
    """Payload for quick 1-click demo login."""
    role: str = Field(default="policyholder", description="Target demo persona: policyholder, broker, or advocate")


class UserResponse(BaseModel):
    """Safe public user entity representation."""
    id: str
    email: str
    full_name: str
    role: str
    phone_number: Optional[str] = None
    country: Optional[str] = None
    occupation_status: Optional[str] = None
    organization: Optional[str] = None
    address: Optional[str] = None
    tier: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuthResponse(BaseModel):
    """Authentication outcome with bearer token and user context."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    message: str = "Authentication successful"
    csrf_token: Optional[str] = None
