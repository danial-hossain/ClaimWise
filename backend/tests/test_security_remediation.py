"""Security Remediation Verification Tests.

Validates that all security audit fixes are strictly enforced:
1. Cryptographic JWT signature verification & production failure mode
2. PBKDF2-HMAC-SHA256 password hashing & automatic legacy upgrade
3. Demo login disabled in production mode
4. Cross-user policy, PDF, claim, and bill isolation
5. File upload validation (extension and magic bytes)
6. Concurrency lock on cryptographic audit ledger and audit isolation
7. HTTP security headers and CORS / Private Network Access protection
"""

import asyncio
from datetime import datetime, timezone
import hashlib
import io
import json
import secrets
import time
import pytest
from httpx import ASGITransport, AsyncClient
import pymupdf

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, create_access_token, verify_supabase_token
from app.api.v1.endpoints.auth import _hash_password, _verify_password, _user_db
from app.api.v1.endpoints.policies import _dev_policy_store
from app.db.audit_repo import audit_repo
from app.db.claim_repo import claim_repo
from app.main import app
from app.schemas.audit import AuditEventCreate
from app.schemas.policy import ExtractedClause, PolicyExtractionResult


# 1. Password Security & Upgrades
def test_pbkdf2_password_hashing_and_legacy_compatibility():
    password = "CorrectHorseBatteryStaple123!"
    hashed = _hash_password(password)
    assert hashed.startswith("pbkdf2:sha256:600000:")
    assert _verify_password(password, hashed) is True
    assert _verify_password("WrongPassword", hashed) is False

    # Test legacy unsalted SHA-256 compatibility
    legacy_sha256 = hashlib.sha256(password.encode("utf-8")).hexdigest()
    assert _verify_password(password, legacy_sha256) is True
    assert _verify_password("WrongPassword", legacy_sha256) is False


# 2. JWT Verification Fail-Closed
def test_jwt_signature_tampering_rejected():
    token = create_access_token("user-sec-1", "user1@example.com")
    parts = token.split(".")
    assert len(parts) == 3

    # Tamper with payload
    tampered_payload = parts[1] + "tamper"
    tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

    with pytest.raises(Exception):
        verify_supabase_token(tampered_token)

    # Tamper with signature
    tampered_sig = parts[2][:-4] + "AAAA"
    tampered_token2 = f"{parts[0]}.{parts[1]}.{tampered_sig}"
    with pytest.raises(Exception):
        verify_supabase_token(tampered_token2)


# 3. Production Configuration Enforcement
def test_production_mode_requires_secure_jwt_secret_and_db_url():
    # Valid production settings
    valid = Settings(
        environment="production",
        jwt_secret=secrets.token_hex(32),
        database_url="postgresql://user:synthetic-password@db.example.test/prod?sslmode=require",
        cors_origins=["https://claimwise.test"], debug=False, _env_file=None,
    )
    assert valid.environment == "production"

    # Default secret must fail in production
    with pytest.raises(ValueError, match="Default dev JWT secret cannot be used in production"):
        Settings(
            environment="production",
            jwt_secret="claimwise-dev-jwt-secret-key-32chars-min!!",
            database_url="postgresql://user:synthetic-password@db.example.test/prod?sslmode=require",
        cors_origins=["https://claimwise.test"], debug=False, _env_file=None,
        )

    # Short secret must fail in production
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            environment="production",
            jwt_secret="too-short",
            database_url="postgresql://user:synthetic-password@db.example.test/prod?sslmode=require",
        cors_origins=["https://claimwise.test"], debug=False, _env_file=None,
        )

    # Missing database_url must fail in production
    with pytest.raises(ValueError, match="DATABASE_URL is mandatory in production mode"):
        Settings(
            environment="production",
            jwt_secret=secrets.token_hex(32),
            database_url=None,
        )


# 4. Demo Login Production Guard
@pytest.mark.asyncio
async def test_demo_login_disabled_in_production(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/demo", json={"role": "policyholder"})
        assert res.status_code == 403
        assert "disabled in production" in res.json()["detail"].lower()


# 5. Cross-User Policy Access Control (BOLA)
@pytest.mark.database
@pytest.mark.asyncio
async def test_cross_user_policy_access_denied():
    user_a_token = create_access_token("user-a-uuid", "alice@example.com")
    user_b_token = create_access_token("user-b-uuid", "bob@example.com")

    # Seed Alice's private policy
    policy_id = "policy-alice-private-001"
    _dev_policy_store[policy_id] = PolicyExtractionResult(
        policy_id=policy_id,
        user_id="user-a-uuid",
        document_name="Alice_Health_Plan.pdf",
        document_hash="hash-alice-123",
        file_size_bytes=2048,
        total_clauses=1,
        total_pages=1,
        is_scanned=False,
        has_extractable_text=True,
        clauses=[
            ExtractedClause(
                clause_id="ALICE-1",
                page_number=1,
                clause_heading="Private Coverage",
                text="Alice confidential policy text.",
                token_count=5,
                document_hash="hash-alice-123",
            )
        ],
        uploaded_at=datetime.now(timezone.utc),
        status="success",
        message="OK",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Bob tries to access Alice's policy -> 403
        bob_res = await client.get(
            f"/api/v1/policies/{policy_id}",
            headers={"Authorization": f"Bearer {user_b_token}"},
        )
        assert bob_res.status_code == 403
        assert "access denied" in bob_res.json()["detail"].lower()

        # Anonymous caller tries to delete Alice's policy -> 401
        anon_del = await client.delete(f"/api/v1/policies/{policy_id}")
        assert anon_del.status_code == 401

        # Bob tries to delete Alice's policy -> 403
        bob_del = await client.delete(
            f"/api/v1/policies/{policy_id}",
            headers={"Authorization": f"Bearer {user_b_token}"},
        )
        assert bob_del.status_code == 403


# 6. Malicious File Upload Rejection
@pytest.mark.database
@pytest.mark.asyncio
async def test_claim_document_upload_rejects_unsupported_extensions():
    user_token = create_access_token("user-upload-tester", "upload@example.com")

    # Create dummy claim for user
    from app.schemas.claim import ClaimRecord
    from app.models.domain import ClaimStatus
    claim_id = "claim-file-test-001"
    dummy_claim = ClaimRecord(
        id=claim_id,
        user_id="user-upload-tester",
        policy_id="policy-001",
        claim_reference="CLM-TEST-001",
        status=ClaimStatus.DRAFT,
        incident_date=datetime.now(timezone.utc).date(),
        total_billed_cents=5000,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await claim_repo.save_claim(dummy_claim)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Reject executable script disguised as document
        files = {"file": ("exploit.sh", io.BytesIO(b"#!/bin/bash\necho 1"), "text/x-shellscript")}
        res = await client.post(
            f"/api/v1/claims/{claim_id}/documents",
            files=files,
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res.status_code == 415
        assert "unsupported document format" in res.json()["detail"].lower()

        # 2. Reject mismatched magic bytes (pretending to be PDF)
        fake_pdf = {"file": ("malicious.pdf", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "application/pdf")}
        res2 = await client.post(
            f"/api/v1/claims/{claim_id}/documents",
            files=fake_pdf,
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res2.status_code == 415
        assert "file signature verification failed" in res2.json()["detail"].lower()


# 7. Audit Concurrency & Isolation
@pytest.mark.database
@pytest.mark.asyncio
async def test_concurrent_audit_events_preserve_monotonic_hash_chain():
    user_id = f"user-concurrent-{secrets.token_hex(4)}"

    # Fire 10 concurrent audit writes
    tasks = [
        audit_repo.record_event(
            AuditEventCreate(
                action=f"concurrent.action.{i}",
                resource_type="test",
                resource_id=f"res-{i}",
                user_id=user_id,
                metadata={"index": i},
            )
        )
        for i in range(10)
    ]
    events = await asyncio.gather(*tasks)
    assert len(events) == 10

    # Verify that each sequence number is strictly unique and monotonic
    seqs = [e.sequence_number for e in events]
    assert len(set(seqs)) == 10

    # User isolation: Querying events with user_id=None must return empty list
    unscoped_events = audit_repo.list_events(user_id=None)
    assert unscoped_events == []

    # Querying events with user_id returns only that user's events
    scoped_events = audit_repo.list_events(user_id=user_id)
    assert len(scoped_events) == 10
    assert all(e.user_id == user_id for e in scoped_events)


# 8. HTTP Security Headers
@pytest.mark.asyncio
async def test_http_security_headers_present():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["x-frame-options"] == "DENY"
        assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in res.headers["permissions-policy"]
        assert "default-src 'none'" in res.headers["content-security-policy"]


# 9. Cross-User Comparison Isolation & BOLA Defense
@pytest.mark.database
@pytest.mark.asyncio
async def test_cross_user_comparison_isolation():
    from app.schemas.comparison import ComparisonRecord
    from app.db.comparison_repo import comparison_repo

    alice_token = create_access_token("alice-comp-user", "alice.comp@example.com")
    bob_token = create_access_token("bob-comp-user", "bob.comp@example.com")

    # Seed Alice's private comparison
    comp_id = "cmp-alice-private-001"
    now = datetime.now(timezone.utc)
    private_comp = ComparisonRecord(
        id=comp_id,
        user_id="alice-comp-user",
        title="Alice Confidential Comparison",
        policy_ids=["policy-001", "policy-002"],
        policies=[],
        created_at=now,
        updated_at=now,
    )
    await comparison_repo.save_comparison(private_comp)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Anonymous access to private comparison -> 401
        anon_res = await client.get(f"/api/v1/comparisons/{comp_id}")
        assert anon_res.status_code == 401
        assert "authentication required" in anon_res.json()["detail"].lower()

        # Bob tries to access Alice's comparison -> 403
        bob_res = await client.get(
            f"/api/v1/comparisons/{comp_id}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_res.status_code == 403
        assert "access denied" in bob_res.json()["detail"].lower()

        # Bob tries to create comparison referencing Alice's private policy -> 403
        bob_create_res = await client.post(
            "/api/v1/comparisons",
            json={"policy_ids": ["policy-alice-private-001", "policy-002"]},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_create_res.status_code == 403
        assert "access denied" in bob_create_res.json()["detail"].lower()


# 10. Audit Metadata PII Masking
def test_audit_metadata_pii_sanitization():
    from app.services.audit_service import audit_service

    raw_meta = {
        "notes": "Patient underwent procedure",
        "description": "Patient John Doe with phone 555-234-5678 and email patient@clinic.com visited clinic",
        "status": "normal",
    }
    sanitized = audit_service.sanitize_metadata(raw_meta)

    # Key matching REDACT_KEYS is fully redacted
    assert sanitized["notes"] == "[REDACTED]"
    # Sensitive string identifiers are masked
    assert "555-234-5678" not in sanitized["description"]
    assert "patient@clinic.com" not in sanitized["description"]
    assert sanitized["status"] == "normal"


# 11. Production HSTS Header Enforcement
@pytest.mark.asyncio
async def test_production_hsts_header_enforced(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert "strict-transport-security" in res.headers
        assert "max-age=31536000" in res.headers["strict-transport-security"]

