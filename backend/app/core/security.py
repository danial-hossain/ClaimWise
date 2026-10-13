"""Security, authentication foundations, and identity validation."""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Optional

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger("claimwise.security")


class AuthenticatedUser(BaseModel):
    """Authenticated user context derived from verified Supabase JWT."""

    id: str
    email: Optional[str] = None
    role: Optional[str] = "authenticated"
    aud: Optional[str] = "authenticated"

    @property
    def user_id(self) -> str:
        """Alias for id to ensure backward compatibility across repositories."""
        return self.id


def _b64url_decode(segment: str) -> bytes:
    """Decode base64url-encoded segment with required RFC 4648 padding."""
    pad = "=" * ((4 - len(segment) % 4) % 4)
    return base64.urlsafe_b64decode((segment + pad).encode("utf-8"))


def verify_supabase_token(token: str) -> AuthenticatedUser:
    """
    Cryptographically verify a Supabase access token (HS256).
    
    Verifies:
    1. Structure: Header.Payload.Signature
    2. Algorithm: Must declare HS256
    3. Signature: Cryptographic HMAC-SHA256 signature against SUPABASE_JWT_SECRET
    4. Expiration: 'exp' claim checked against current UTC time
    5. Audience: 'aud' claim checked against expected audience
    6. Subject: 'sub' (User UUID) must be present and valid
    
    In production mode:
    Fails closed if SUPABASE_JWT_SECRET is missing or token is invalid.
    """
    settings = get_settings()
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed JWT: Token must consist of three period-separated segments.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    header_b64, payload_b64, sig_b64 = parts[0], parts[1], parts[2]

    # 1. Parse header
    try:
        header_bytes = _b64url_decode(header_b64)
        header = json.loads(header_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT header formatting.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if header.get("alg") != "HS256":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported JWT algorithm '{header.get('alg')}'. Expected HS256.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Signature verification
    is_prod = settings.environment.lower() == "production"
    jwt_secret = settings.supabase_jwt_secret

    if is_prod and not jwt_secret:
        logger.error("Production security configuration missing: SUPABASE_JWT_SECRET is not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server security configuration error: SUPABASE_JWT_SECRET is required in production.",
        )

    if jwt_secret:
        try:
            expected_sig = hmac.new(
                jwt_secret.encode("utf-8"),
                f"{header_b64}.{payload_b64}".encode("utf-8"),
                hashlib.sha256,
            ).digest()
            received_sig = _b64url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, received_sig):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token signature. Cryptographic verification failed.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Signature verification failure: {str(exc)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 3. Parse and validate payload
    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT payload formatting.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check expiration (exp)
    exp = payload.get("exp")
    if exp is not None:
        try:
            now_ts = int(time.time())
            if now_ts >= int(exp):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired. Please re-authenticate.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed 'exp' expiration claim in token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Check audience (aud)
    aud = payload.get("aud")
    if aud and settings.supabase_jwt_audience and aud != settings.supabase_jwt_audience:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token audience claim '{aud}'. Expected '{settings.supabase_jwt_audience}'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check issuer (iss) if configured
    iss = payload.get("iss")
    if settings.supabase_jwt_issuer and iss != settings.supabase_jwt_issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token issuer claim '{iss}'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check subject (sub)
    user_id = payload.get("sub")
    if not user_id or not str(user_id).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing valid subject ('sub') user identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        id=str(user_id).strip(),
        email=payload.get("email"),
        role=payload.get("role", "authenticated"),
        aud=str(aud) if aud else "authenticated",
    )


async def get_current_user_optional(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[AuthenticatedUser]:
    """
    Extract authenticated user identity from Authorization header.
    
    SECURITY PRINCIPLE:
    - Never accept a client-supplied user ID as proof of identity.
    - If Bearer token is provided, cryptographically verify it.
    - In production mode, disable dev-user-001 fallback. Return None if unauthenticated.
    - In explicit development mode, if no header is supplied, fall back to clearly labeled dev-user-001.
    """
    settings = get_settings()

    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header scheme. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = authorization.split("Bearer ", 1)[1].strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Empty Bearer token provided in Authorization header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return verify_supabase_token(token)

    # No authorization header provided
    if settings.environment.lower() == "production":
        return None

    # Explicit development mode fallback
    return AuthenticatedUser(
        id="dev-user-001",
        email="developer@claimwise.local",
        role="authenticated",
        aud="authenticated",
    )


async def require_authenticated_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthenticatedUser:
    """
    Require a verified authenticated user or raise 401 Unauthorized.
    """
    user = await get_current_user_optional(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
