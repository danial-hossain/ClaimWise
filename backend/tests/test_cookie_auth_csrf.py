"""Tests for Cookie-based JWT authentication, Session Restoration, and CSRF Protection."""

import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.security import (
    COOKIE_ACCESS_TOKEN_KEY,
    COOKIE_CSRF_TOKEN_KEY,
    create_access_token,
)
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.database
def test_login_issues_secure_httponly_and_csrf_cookies(client: TestClient):
    """Verify login sets HttpOnly claimwise_access_token and client-accessible claimwise_csrf_token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "alex.morgan@claimwise-demo.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "csrf_token" in data
    assert data["csrf_token"] is not None

    # Check cookies
    cookies = response.cookies
    assert COOKIE_ACCESS_TOKEN_KEY in cookies
    assert COOKIE_CSRF_TOKEN_KEY in cookies

    # Inspect Set-Cookie header flags
    raw_cookies = response.headers.get_list("set-cookie")
    access_cookie_header = next((c for c in raw_cookies if COOKIE_ACCESS_TOKEN_KEY in c), None)
    assert access_cookie_header is not None
    assert "httponly" in access_cookie_header.lower()
    assert "samesite=lax" in access_cookie_header.lower()

    csrf_cookie_header = next((c for c in raw_cookies if COOKIE_CSRF_TOKEN_KEY in c), None)
    assert csrf_cookie_header is not None
    assert "samesite=lax" in csrf_cookie_header.lower()


@pytest.mark.database
def test_demo_login_issues_auth_and_csrf_cookies(client: TestClient):
    """Verify demo login issues both authentication and CSRF cookies."""
    response = client.post(
        "/api/v1/auth/demo",
        json={"role": "policyholder"},
    )
    assert response.status_code == 200
    assert COOKIE_ACCESS_TOKEN_KEY in response.cookies
    assert COOKIE_CSRF_TOKEN_KEY in response.cookies
    data = response.json()
    assert data["user"]["role"] == "policyholder"
    assert data["csrf_token"] is not None


@pytest.mark.database
def test_session_restoration_via_cookie(client: TestClient):
    """Verify session can be restored via claimwise_access_token cookie without Authorization header."""
    token = create_access_token(
        user_id="usr-demo-broker",
        email="marcus.vance@vancebenefits.com",
        role="broker",
        tier=1,
    )
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, token)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "usr-demo-broker"
    assert data["email"] == "marcus.vance@vancebenefits.com"
    assert data["role"] == "broker"


def test_session_restoration_rejects_tampered_cookie(client: TestClient, monkeypatch):
    """Verify tampered JWT in cookie is rejected with 401."""
    monkeypatch.setattr(get_settings(), "environment", "production")
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, "invalid.tampered.token")

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_csrf_token_endpoint(client: TestClient):
    """Verify GET /api/v1/auth/csrf generates and sets a fresh CSRF cookie."""
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    data = response.json()
    assert "csrf_token" in data
    assert COOKIE_CSRF_TOKEN_KEY in response.cookies
    assert response.cookies[COOKIE_CSRF_TOKEN_KEY] == data["csrf_token"]


def test_csrf_protection_rejects_missing_header_when_cookie_auth_active(client: TestClient):
    """Verify state-changing request using cookie auth is rejected with 403 if X-CSRF-Token is omitted."""
    token = create_access_token(
        user_id="usr-demo-policyholder",
        email="alex.morgan@claimwise-demo.com",
        role="policyholder",
    )
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, token)
    client.cookies.set(COOKIE_CSRF_TOKEN_KEY, "test-csrf-secret-1234567890")

    # Logout is a POST request that terminates session
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert "CSRF validation failed" in response.json()["detail"]


def test_csrf_protection_rejects_mismatched_token(client: TestClient):
    """Verify state-changing request using cookie auth is rejected with 403 if X-CSRF-Token does not match."""
    token = create_access_token(
        user_id="usr-demo-policyholder",
        email="alex.morgan@claimwise-demo.com",
        role="policyholder",
    )
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, token)
    client.cookies.set(COOKIE_CSRF_TOKEN_KEY, "legitimate-server-csrf-token")

    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": "forged-attacker-token"},
    )
    assert response.status_code == 403
    assert "CSRF validation failed" in response.json()["detail"]


def test_csrf_protection_accepts_valid_matching_token(client: TestClient):
    """Verify state-changing request succeeds when X-CSRF-Token matches the cookie."""
    token = create_access_token(
        user_id="usr-demo-policyholder",
        email="alex.morgan@claimwise-demo.com",
        role="policyholder",
    )
    csrf_val = "valid-matching-csrf-token-abc123456"
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, token)
    client.cookies.set(COOKIE_CSRF_TOKEN_KEY, csrf_val)

    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_val},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_bearer_token_bypasses_cookie_csrf_requirement(client: TestClient):
    """Verify API callers using Authorization: Bearer <token> are exempt from CSRF checks."""
    token = create_access_token(
        user_id="usr-demo-policyholder",
        email="alex.morgan@claimwise-demo.com",
        role="policyholder",
    )
    # No cookies set, only Bearer header
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_origin_validation_blocks_unauthorized_browser_origin(client: TestClient):
    """Verify request with untrusted Origin header is rejected with 403."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "alex.morgan@claimwise-demo.com", "password": "password123"},
        headers={"Origin": "https://evil-hacker-site.com"},
    )
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"]


def test_logout_clears_auth_and_csrf_cookies(client: TestClient):
    """Verify logout removes authentication and CSRF cookies."""
    token = create_access_token(
        user_id="usr-demo-policyholder",
        email="alex.morgan@claimwise-demo.com",
        role="policyholder",
    )
    csrf_val = "csrf-val-to-clear"
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, token)
    client.cookies.set(COOKIE_CSRF_TOKEN_KEY, csrf_val)

    response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_val},
    )
    assert response.status_code == 200

    raw_cookies = response.headers.get_list("set-cookie")
    access_clear = next((c for c in raw_cookies if COOKIE_ACCESS_TOKEN_KEY in c), None)
    assert access_clear is not None
    assert ('max-age=0' in access_clear.lower() or 'expires=' in access_clear.lower() or '""' in access_clear)
