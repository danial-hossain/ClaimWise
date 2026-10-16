"""Security, authentication foundations, and identity validation."""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger("claimwise.security")


class AuthenticatedUser(BaseModel):
    """Authenticated user context derived from verified Supabase JWT."""

    id: str
    email: Optional[str] = None
    role: Optional[str] = "authenticated"
    aud: Optional[str] = "authenticated"
    tier: int = 1

    @property
    def user_id(self) -> str:
        """Alias for id to ensure backward compatibility across repositories."""
        return self.id


def _b64url_decode(segment: str) -> bytes:
    """Decode base64url-encoded segment with required RFC 4648 padding."""
    pad = "=" * ((4 - len(segment) % 4) % 4)
    return base64.b64decode((segment + pad).encode("ascii"), altchars=b"-_", validate=True)


def _b64url_encode(data: bytes) -> str:
    """Encode bytes to base64url string without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def create_access_token(
    user_id: str,
    email: str,
    role: str = "authenticated",
    tier: int = 1,
    exp_seconds: int = 86400,
) -> str:
    """
    Generate a cryptographically signed HS256 JWT access token compatible with verify_supabase_token.
    """
    settings = get_settings()
    secret = getattr(settings, "jwt_secret", None) or getattr(settings, "supabase_jwt_secret", None) or "claimwise-dev-jwt-secret-key-32chars-min!!"

    header = {"alg": "HS256", "typ": "JWT"}
    now_ts = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "tier": tier,
        "aud": settings.supabase_jwt_audience or "authenticated",
        "exp": now_ts + exp_seconds,
        "iat": now_ts,
    }

    if settings.jwt_issuer:
        payload["iss"] = settings.jwt_issuer

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


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
    if not isinstance(token, str) or len(token) > 16_384:
        raise HTTPException(status_code=401, detail="Invalid access token.")
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

    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported JWT algorithm. Expected HS256.",
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

    effective_secret = jwt_secret or "claimwise-dev-jwt-secret-key-32chars-min!!"
    try:
        expected_sig = hmac.new(
            effective_secret.encode("utf-8"),
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
            detail="Signature verification failed.",
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

    # Claims must match the application's token design; absent/malformed claims fail closed.
    def invalid_claim():
        return HTTPException(status_code=401, detail="Invalid or expired token claims.", headers={"WWW-Authenticate": "Bearer"})

    if not isinstance(payload, dict):
        raise invalid_claim()
    now = time.time()
    exp = payload.get("exp")
    issued = payload.get("iat")
    if type(exp) is not int or exp <= now:
        raise invalid_claim()
    if type(issued) is not int or issued > now + 30 or issued >= exp:
        raise invalid_claim()
    if "nbf" in payload and (type(payload["nbf"]) is not int or payload["nbf"] > now):
        raise invalid_claim()
    aud = payload.get("aud")
    if aud != settings.jwt_audience:
        raise invalid_claim()
    if settings.jwt_issuer and payload.get("iss") != settings.jwt_issuer:
        raise invalid_claim()
    user_id = payload.get("sub")
    tier = payload.get("tier", 1)
    if not isinstance(user_id, str) or not user_id.strip() or len(user_id) > 200:
        raise invalid_claim()
    if type(tier) is not int or not 0 <= tier <= 4:
        raise invalid_claim()
    if not isinstance(payload.get("role", "authenticated"), str) or not isinstance(payload.get("email", ""), str):
        raise invalid_claim()
    if settings.environment == "production" and (user_id.startswith("usr-demo-") or user_id == "dev-user-001"):
        raise invalid_claim()
    return AuthenticatedUser(id=user_id, email=payload.get("email"), role=payload.get("role", "authenticated"), aud=aud, tier=tier)


COOKIE_ACCESS_TOKEN_KEY = "claimwise_access_token"
COOKIE_CSRF_TOKEN_KEY = "claimwise_csrf_token"


def set_auth_cookies(
    response: Response,
    token: str,
    csrf_token: Optional[str] = None,
    max_age_seconds: int = 604800,
    is_production: bool = False,
) -> str:
    """
    Set Secure, HttpOnly authentication cookie and client-accessible CSRF cookie.
    - claimwise_access_token: HttpOnly, Secure (prod/HTTPS), SameSite=Lax, Path=/
    - claimwise_csrf_token: Accessible to client JavaScript for double-submit header
    """
    if not csrf_token:
        csrf_token = secrets.token_hex(32)

    response.set_cookie(
        key=COOKIE_ACCESS_TOKEN_KEY,
        value=token,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        path="/",
        secure=is_production,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        key=COOKIE_CSRF_TOKEN_KEY,
        value=csrf_token,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        path="/",
        secure=is_production,
        httponly=False,
        samesite="lax",
    )
    return csrf_token


def clear_auth_cookies(response: Response, is_production: bool = False) -> None:
    """
    Clear authentication and CSRF cookies on logout.
    """
    response.delete_cookie(
        key=COOKIE_ACCESS_TOKEN_KEY,
        path="/",
        secure=is_production,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=COOKIE_CSRF_TOKEN_KEY,
        path="/",
        secure=is_production,
        httponly=False,
        samesite="lax",
    )


def generate_csrf_token() -> str:
    """Generate a cryptographically secure random CSRF token."""
    return secrets.token_hex(32)


async def get_current_user_optional(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    claimwise_access_token: Optional[str] = Cookie(default=None),
) -> Optional[AuthenticatedUser]:
    """
    Extract authenticated user identity from Bearer token or Secure HttpOnly cookie.
    
    SECURITY PRINCIPLE:
    - Never accept a client-supplied user ID or profile as proof of identity.
    - If Bearer token is provided in Authorization header, cryptographically verify it.
    - If no Authorization header is provided, inspect the HttpOnly session cookie.
    - In production mode, disable dev-user-001 fallback. Return None if unauthenticated.
    - In explicit development mode, if no credentials are supplied, fall back to clearly labeled dev-user-001.
    """
    settings = get_settings()
    token = None

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

    if not token and claimwise_access_token:
        token = claimwise_access_token.strip()

    if token:
        return verify_supabase_token(token)

    # No credentials provided
    if settings.environment.lower() == "production":
        return None

    # Explicit development mode fallback
    return AuthenticatedUser(
        id="dev-user-001",
        email="developer@claimwise.local",
        role="authenticated",
        aud="authenticated",
        tier=1,
    )


async def require_authenticated_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    claimwise_access_token: Optional[str] = Cookie(default=None),
) -> AuthenticatedUser:
    """
    Require a verified authenticated user via cookie or Bearer token, or raise 401 Unauthorized.
    """
    if not authorization and not claimwise_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid session or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_current_user_optional(authorization, claimwise_access_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid session or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_min_tier(min_tier: int):
    """
    Dependency factory to enforce minimum subscription tier server-side.
    """
    async def _check_tier(user: AuthenticatedUser = Depends(require_authenticated_user)) -> AuthenticatedUser:
        if getattr(user, "tier", 1) < min_tier:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Subscription tier {min_tier} required for this feature.",
            )
        return user
    return _check_tier


verify_access_token = verify_supabase_token
