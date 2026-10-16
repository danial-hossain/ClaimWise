"""User authentication endpoints for ClaimWise."""

from datetime import datetime, timezone
import hashlib
import hmac
import logging
from typing import Dict, Optional
import secrets
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.security import (
    AuthenticatedUser,
    COOKIE_CSRF_TOKEN_KEY,
    clear_auth_cookies,
    create_access_token,
    generate_csrf_token,
    get_current_user_optional,
    require_authenticated_user,
    set_auth_cookies,
)
from app.db.audit_repo import audit_repo
from app.schemas.audit import AuditEventCreate
from app.schemas.auth import (
    AuthResponse,
    DemoLoginRequest,
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    SignUpRequest,
    UserResponse,
)

logger = logging.getLogger("claimwise.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])

from app.db.local_store import LazyPersistentStore, local_store
from app.core.exceptions import DatabaseConnectionException


PASSWORD_ITERATIONS = 600_000


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash passwords using salted PBKDF2-HMAC-SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2:sha256:{PASSWORD_ITERATIONS}:{salt}:{hashed}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash with backward compatibility for legacy SHA256 and varying iterations."""
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2:sha256:"):
        parts = stored_hash.split(":")
        if len(parts) == 5:
            try:
                iterations = int(parts[2])
                salt = parts[3]
                expected_hash = parts[4]
                actual_hash = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt.encode("utf-8"),
                    iterations,
                ).hex()
                return hmac.compare_digest(actual_hash, expected_hash)
            except Exception:
                return False
    # Legacy unsalted SHA-256 fallback
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)


# Pre-seeded in-memory user registry with precomputed hashes to eliminate import-time PBKDF2 cost
_DEMO_USERS: Dict[str, dict] = {
    "policyholder": {
        "id": "usr-demo-policyholder",
        "email": "alex.morgan@claimwise-demo.com",
        "full_name": "Alex Morgan",
        "role": "policyholder",
        "tier": 1,
        "password_hash": "pbkdf2:sha256:600000:claimwise_demo_salt_ph:e1dd37183b752ea9b12eb1b3dbacae6d5910dfe3298f5bc448be961fbf142d48",
    },
    "broker": {
        "id": "usr-demo-broker",
        "email": "marcus.vance@vancebenefits.com",
        "full_name": "Marcus Vance",
        "role": "broker",
        "tier": 1,
        "password_hash": "pbkdf2:sha256:600000:claimwise_demo_salt_br:90d24576d110b497c1a73175ad783b708b3d1b99846ac61b6c7f03957d42daa7",
    },
    "advocate": {
        "id": "usr-demo-advocate",
        "email": "sarah.jenkins@patientadvocacy.org",
        "full_name": "Dr. Sarah Jenkins",
        "role": "advocate",
        "tier": 2,
        "password_hash": "pbkdf2:sha256:600000:claimwise_demo_salt_ad:c413dd54a1b8788871af793136a2b8213e351bb0b655b6a88962cb262fc19bc2",
    },
}


def _load_users_from_db() -> Dict[str, dict]:
    production = get_settings().environment == "production"
    users = {} if production else {u["email"].lower(): dict(u) for u in _DEMO_USERS.values()}
    try:
        with local_store._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, email, full_name, role, phone_number, country,
                           occupation_status, organization, address, tier, password_hash, created_at
                    FROM users;
                    """
                )
                for row in cur.fetchall():
                    if production and (str(row[0]).startswith("usr-demo-") or row[0] == "dev-user-001"):
                        continue
                    users[row[1].lower()] = {
                        "id": row[0],
                        "email": row[1].lower(),
                        "full_name": row[2],
                        "role": row[3],
                        "phone_number": row[4],
                        "country": row[5],
                        "occupation_status": row[6],
                        "organization": row[7],
                        "address": row[8],
                        "tier": row[9] or 1,
                        "password_hash": row[10],
                        "created_at": row[11],
                    }
    except Exception as exc:
        logger.warning("Could not load users from PostgreSQL: %s", type(exc).__name__)
        if production:
            raise DatabaseConnectionException("Account storage is temporarily unavailable. Please retry shortly.") from exc
    return users


def _save_user_to_db(user: dict) -> None:
    try:
        with local_store._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (
                        id, email, full_name, role, phone_number, country,
                        occupation_status, organization, address, tier, password_hash, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        email = EXCLUDED.email,
                        full_name = EXCLUDED.full_name,
                        role = EXCLUDED.role,
                        phone_number = EXCLUDED.phone_number,
                        country = EXCLUDED.country,
                        occupation_status = EXCLUDED.occupation_status,
                        organization = EXCLUDED.organization,
                        address = EXCLUDED.address,
                        tier = EXCLUDED.tier,
                        password_hash = EXCLUDED.password_hash,
                        updated_at = NOW();
                    """,
                    (
                        user["id"],
                        user["email"],
                        user["full_name"],
                        user["role"],
                        user.get("phone_number"),
                        user.get("country"),
                        user.get("occupation_status"),
                        user.get("organization"),
                        user.get("address"),
                        user.get("tier", 1),
                        user["password_hash"],
                        user.get("created_at") or datetime.now(timezone.utc),
                    ),
                )
    except Exception as exc:
        logger.error("Failed to save user %s to PostgreSQL: %s", user.get("id"), type(exc).__name__)


class UserRegistry(LazyPersistentStore):
    def _records(self):
        return _load_users_from_db()


_user_db: Dict[str, dict] = UserRegistry()


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new ClaimWise user account",
)
async def signup(payload: SignUpRequest, response: Response, background_tasks: BackgroundTasks) -> AuthResponse:
    """Register a new user account, generate an authenticated JWT, and log the registration event."""
    email_clean = payload.email.lower().strip()
    if email_clean in _user_db:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{email_clean}' already exists. Please sign in instead.",
        )

    user_id = f"usr-{uuid.uuid4().hex[:10]}"
    phone_clean = payload.phone_number.strip() if payload.phone_number else None
    country_clean = payload.country.strip() if payload.country else None
    occ_clean = payload.occupation_status.strip().lower() if payload.occupation_status else None
    org_clean = payload.organization.strip() if payload.organization else None

    new_user = {
        "id": user_id,
        "email": email_clean,
        "full_name": payload.full_name.strip(),
        "role": payload.role.strip().lower() if payload.role else "policyholder",
        "phone_number": phone_clean,
        "country": country_clean,
        "occupation_status": occ_clean,
        "organization": org_clean,
        "tier": 1,
        "password_hash": _hash_password(payload.password),
        "created_at": datetime.now(timezone.utc),
    }
    _user_db[email_clean] = new_user
    _save_user_to_db(new_user)

    token = create_access_token(
        user_id=user_id,
        email=email_clean,
        role=new_user["role"],
        tier=new_user.get("tier", 1),
    )

    settings = get_settings()
    is_prod = settings.environment.lower() == "production"
    csrf_token = set_auth_cookies(response, token=token, is_production=is_prod)

    # Record tamper-evident audit event asynchronously in background
    background_tasks.add_task(
        audit_repo.record_event,
        AuditEventCreate(
            action="user.signup",
            resource_type="auth",
            resource_id=user_id,
            outcome="success",
            user_id=user_id,
            metadata={
                "email": email_clean,
                "role": new_user["role"],
                "country": country_clean,
                "occupation_status": occ_clean,
            },
        ),
    )

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user_id,
            email=email_clean,
            full_name=new_user["full_name"],
            role=new_user["role"],
            phone_number=new_user["phone_number"],
            country=new_user["country"],
            occupation_status=new_user["occupation_status"],
            organization=new_user["organization"],
            tier=1,
            created_at=new_user["created_at"],
        ),
        message="Account created successfully",
        csrf_token=csrf_token,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Sign in with email and password",
)
async def login(payload: LoginRequest, response: Response, background_tasks: BackgroundTasks) -> AuthResponse:
    """Validate credentials, return access token, and record authenticated audit event."""
    email_clean = payload.email.lower().strip()
    user_record = _user_db.get(email_clean)

    demo_in_production = bool(user_record and get_settings().environment == "production" and (
        user_record["id"].startswith("usr-demo-") or user_record["id"] == "dev-user-001"
    ))
    if not user_record or demo_in_production or not _verify_password(payload.password, user_record.get("password_hash", "")):
        # Record failed attempt in background
        background_tasks.add_task(
            audit_repo.record_event,
            AuditEventCreate(
                action="user.login_failed",
                resource_type="auth",
                resource_id=email_clean,
                outcome="denied",
                user_id="anonymous",
                metadata={"email": email_clean, "reason": "invalid_credentials"},
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Seamlessly upgrade legacy unsalted SHA-256 hashes to PBKDF2 in background
    current_hash = user_record.get("password_hash", "")
    if not current_hash.startswith(f"pbkdf2:sha256:{PASSWORD_ITERATIONS}:"):
        user_record["password_hash"] = _hash_password(payload.password)
        background_tasks.add_task(_save_user_to_db, user_record)

    token = create_access_token(
        user_id=user_record["id"],
        email=email_clean,
        role=user_record["role"],
        tier=user_record.get("tier", 1),
    )

    settings = get_settings()
    is_prod = settings.environment.lower() == "production"
    csrf_token = set_auth_cookies(response, token=token, is_production=is_prod)

    # Record successful login event in background
    background_tasks.add_task(
        audit_repo.record_event,
        AuditEventCreate(
            action="user.login",
            resource_type="auth",
            resource_id=user_record["id"],
            outcome="success",
            user_id=user_record["id"],
            metadata={"email": email_clean, "role": user_record["role"]},
        ),
    )

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user_record["id"],
            email=email_clean,
            full_name=user_record["full_name"],
            role=user_record["role"],
            phone_number=user_record.get("phone_number"),
            country=user_record.get("country"),
            occupation_status=user_record.get("occupation_status"),
            organization=user_record.get("organization"),
            address=user_record.get("address"),
            tier=user_record.get("tier", 1),
            created_at=user_record.get("created_at", datetime.now(timezone.utc)),
        ),
        message="Signed in successfully",
        csrf_token=csrf_token,
    )


@router.post(
    "/demo",
    response_model=AuthResponse,
    summary="Instant 1-click Demo Account sign in",
)
async def demo_login(payload: DemoLoginRequest, response: Response, background_tasks: BackgroundTasks) -> AuthResponse:
    """Instantly authenticate as one of 3 pre-configured demo personas."""
    settings = get_settings()
    if settings.environment.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo authentication is disabled in production environments.",
        )

    role_key = payload.role.lower().strip()
    demo_user = _DEMO_USERS.get(role_key) or _DEMO_USERS["policyholder"]

    token = create_access_token(
        user_id=demo_user["id"],
        email=demo_user["email"],
        role=demo_user["role"],
        tier=demo_user.get("tier", 1),
    )

    is_prod = settings.environment.lower() == "production"
    csrf_token = set_auth_cookies(response, token=token, is_production=is_prod)

    background_tasks.add_task(
        audit_repo.record_event,
        AuditEventCreate(
            action="user.demo_login",
            resource_type="auth",
            resource_id=demo_user["id"],
            outcome="success",
            user_id=demo_user["id"],
            metadata={"role": demo_user["role"], "persona": demo_user["full_name"]},
        ),
    )


    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=demo_user["id"],
            email=demo_user["email"],
            full_name=demo_user["full_name"],
            role=demo_user["role"],
            phone_number=demo_user.get("phone_number"),
            country=demo_user.get("country", "United States"),
            occupation_status=demo_user.get("occupation_status", "student" if demo_user["role"] == "policyholder" else "employee"),
            organization=demo_user.get("organization"),
            tier=demo_user.get("tier", 1),
            created_at=datetime.now(timezone.utc),
        ),
        message=f"Signed in as Demo {demo_user['role'].title()}",
        csrf_token=csrf_token,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Retrieve current user profile context",
)
async def get_me(current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user)) -> UserResponse:
    """Return identity and permission tier for current authenticated bearer session."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active authenticated session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Search registry or synthesize
    email = current_user.email or f"{current_user.id}@claimwise.local"
    user_record = _user_db.get(email.lower())

    if user_record and user_record["id"] != current_user.id:
        raise HTTPException(status_code=401, detail="Account does not match this session.")
    if not user_record and get_settings().environment == "production":
        raise HTTPException(status_code=401, detail="Account not found. Please sign in again.")
    if user_record:
        return UserResponse(
            id=user_record["id"],
            email=user_record["email"],
            full_name=user_record["full_name"],
            role=user_record["role"],
            phone_number=user_record.get("phone_number"),
            country=user_record.get("country"),
            occupation_status=user_record.get("occupation_status"),
            organization=user_record.get("organization"),
            tier=user_record.get("tier", 1),
            created_at=user_record.get("created_at", datetime.now(timezone.utc)),
        )

    return UserResponse(
        id=current_user.id,
        email=email,
        full_name=email.split("@")[0].replace(".", " ").title(),
        role=current_user.role or "policyholder",
        tier=1,
        created_at=datetime.now(timezone.utc),
    )


@router.put("/profile", response_model=UserResponse, summary="Update current user's name and address")
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
) -> UserResponse:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    email = (current_user.email or "").lower()
    record = _user_db.get(email)
    if not record or record["id"] != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found. Please sign in again.")
    record["full_name"] = payload.full_name.strip()
    record["address"] = payload.address.strip() if payload.address and payload.address.strip() else None
    _save_user_to_db(record)
    return UserResponse(
        id=record["id"], email=record["email"], full_name=record["full_name"], role=record["role"],
        phone_number=record.get("phone_number"), country=record.get("country"),
        occupation_status=record.get("occupation_status"), organization=record.get("organization"),
        address=record.get("address"), tier=record.get("tier", 1),
        created_at=record.get("created_at", datetime.now(timezone.utc)),
    )


@router.put("/password", summary="Change current user's password")
async def change_password(
    payload: PasswordChangeRequest,
    current_user: Optional[AuthenticatedUser] = Depends(require_authenticated_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    email = (current_user.email or "").lower()
    record = _user_db.get(email)
    if not record or record["id"] != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found. Please sign in again.")
    if not _verify_password(payload.current_password, record.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    record["password_hash"] = _hash_password(payload.new_password)
    _save_user_to_db(record)
    return {"message": "Password updated successfully."}


@router.get(
    "/csrf",
    summary="Issue or refresh CSRF token cookie",
)
async def get_csrf_token(response: Response):
    """Issue a new CSRF token cookie or refresh it for Double-Submit CSRF protection."""
    settings = get_settings()
    is_prod = settings.environment.lower() == "production"
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=COOKIE_CSRF_TOKEN_KEY,
        value=csrf_token,
        max_age=604800,
        expires=604800,
        path="/",
        secure=is_prod,
        httponly=False,
        samesite="lax",
    )
    return {"status": "success", "csrf_token": csrf_token}


@router.post(
    "/logout",
    summary="Sign out and record logout event",
)
async def logout(
    response: Response,
    request: Request,
):
    """Acknowledge session termination, clear auth cookies, and record audit log."""
    settings = get_settings()
    is_prod = settings.environment.lower() == "production"
    clear_auth_cookies(response, is_production=is_prod)
    current_user = None
    if request.headers.get("authorization") or request.cookies.get("claimwise_access_token"):
        try:
            current_user = await get_current_user_optional(request.headers.get("authorization"), request.cookies.get("claimwise_access_token"))
        except HTTPException as exc:
            if exc.status_code != 401:
                raise
    user_id = current_user.id if current_user else "anonymous"
    try:
        await audit_repo.record_event(
            AuditEventCreate(
                action="user.logout",
                resource_type="auth",
                resource_id=user_id,
                outcome="success",
                user_id=user_id,
            )
        )
    except Exception:
        logger.error("Logout audit persistence failed; session cookies were cleared.")
    return {"status": "success", "message": "Logged out successfully"}
