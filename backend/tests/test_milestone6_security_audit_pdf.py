"""Comprehensive integration and unit tests for Milestone 6:
Production Security Hardening, Tenant Isolation, Server-Side PDF Exports, and Cryptographic Audit Trail.

Tagline: "Evidence first. If no proof, no answer."
"""

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
import time
from typing import Optional
import pytest
from httpx import ASGITransport, AsyncClient
import pymupdf

from app.api.v1.endpoints.policies import _dev_policy_store
from app.main import app
from app.core.config import get_settings
from app.core.security import AuthenticatedUser, verify_supabase_token
from app.db.audit_repo import audit_repo
from app.db.claim_repo import claim_repo
from app.db.comparison_repo import comparison_repo
from app.schemas.audit import AuditEventCreate
from app.schemas.appeal import AppealDraftUpdateRequest, AppealStatus
from app.schemas.policy import ExtractedClause, PolicyExtractionResult
from app.services.audit_service import audit_service
from app.services.retrieval.hybrid_service import hybrid_retrieval_service


TEST_JWT_SECRET = "test-jwt-secret-for-milestone6-verification-32chars"


def create_signed_token(
    user_id: str,
    secret: str = TEST_JWT_SECRET,
    expires_in: int = 3600,
    alg: str = "HS256",
    aud: str = "authenticated",
) -> str:
    """Generate a RFC 7519 compliant HS256 JWT for testing."""
    header = {"alg": alg, "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": f"{user_id}@example.com",
        "aud": aud,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
        "iss": get_settings().jwt_issuer,
    }
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    s_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    return f"{h_b64}.{p_b64}.{s_b64}"


def create_synthetic_bill_pdf() -> bytes:
    """Create a minimal synthetic medical bill for testing."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "ST. JUDE REGIONAL MEDICAL CENTER")
    page.insert_text((50, 90), "2026-04-10 99213 Specialist Consultation Office Visit $350.00")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _create_mock_policy_record(policy_id: str, name: str, owner: str = "dev-user-001") -> PolicyExtractionResult:
    """Helper to register and index a mock policy for comparison & claims testing."""
    clauses = [
        ExtractedClause(
            clause_id=f"{policy_id}-DED",
            page_number=1,
            clause_heading="Deductible Schedule",
            text="Individual annual in-network deductible is $1,000.",
            token_count=12,
            document_hash=f"hash-{policy_id}",
        ),
        ExtractedClause(
            clause_id=f"{policy_id}-VISIT",
            page_number=2,
            clause_heading="Specialist Office Visit",
            text="Specialist visits require a $40 copayment per visit.",
            token_count=14,
            document_hash=f"hash-{policy_id}",
        ),
    ]
    pol = PolicyExtractionResult(
        policy_id=policy_id,
        user_id=owner,
        document_name=f"{name}.pdf",
        document_hash=f"hash-{policy_id}",
        file_size_bytes=10240,
        total_clauses=len(clauses),
        total_pages=2,
        is_scanned=False,
        has_extractable_text=True,
        status="success",
        pages=[],
        clauses=clauses,
        uploaded_at=datetime.now(timezone.utc),
        message="Policy indexed for testing.",
    )
    _dev_policy_store[policy_id] = pol
    hybrid_retrieval_service.index_policy(policy_id, clauses, pol.document_hash)
    return pol


@pytest.fixture(autouse=True)
def setup_m6_test_environment(monkeypatch, request):
    if not request.node.get_closest_marker("database"):
        request.getfixturevalue("memory_policy_store")
    """Configure settings and seed policies for Milestone 6 test execution."""
    settings = get_settings()
    monkeypatch.setattr(settings, "supabase_jwt_secret", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "environment", "development")

    # Seed policies
    owner = {
        "test_tenant_isolation_cross_user_access_rejected": "user-alice-001",
        "test_eob_pdf_export_success": "user-pdf-tester",
        "test_appeal_pdf_reviewed_status_enforcement": "user-appeal-pdf-tester",
        "test_comparison_pdf_export_success": "user-compare-pdf-tester",
    }.get(request.node.name, "dev-user-001")
    _create_mock_policy_record("m6-test-policy", "Standard Policy", owner)
    _create_mock_policy_record("m6-test-policy-1", "Gold Shield Plan", owner)
    _create_mock_policy_record("m6-test-policy-2", "Silver Care Plan", owner)


# ==============================================================================
# 1. AUTHENTICATION & SECURITY HARDENING TESTS
# ==============================================================================

def test_token_verification_success():
    """Verify that a validly signed HS256 token is verified and returns authenticated user."""
    token = create_signed_token("user-valid-123")
    user = verify_supabase_token(token)
    assert isinstance(user, AuthenticatedUser)
    assert user.id == "user-valid-123"
    assert user.email == "user-valid-123@example.com"


def test_token_verification_expired():
    """Verify that an expired token raises HTTP 401."""
    token = create_signed_token("user-expired-123", expires_in=-60)
    with pytest.raises(Exception) as exc_info:
        verify_supabase_token(token)
    assert "401" in str(exc_info.value)
    assert "expired" in str(exc_info.value).lower()


def test_token_verification_invalid_signature():
    """Verify that tampering with the token signature raises HTTP 401."""
    token = create_signed_token("user-tampered-123", secret="wrong-secret-key-000000000000000")
    with pytest.raises(Exception) as exc_info:
        verify_supabase_token(token)
    assert "401" in str(exc_info.value)
    assert "signature" in str(exc_info.value).lower()


def test_token_verification_unsupported_algorithm():
    """Verify that non-HS256 tokens are rejected."""
    token = create_signed_token("user-alg-123", alg="RS256")
    with pytest.raises(Exception) as exc_info:
        verify_supabase_token(token)
    assert "401" in str(exc_info.value)
    assert "unsupported jwt algorithm" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_production_mode_fails_closed_without_token(monkeypatch):
    """Verify that in production mode, requests without a valid token fail closed (401)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without Authorization header
        res = await client.get("/api/v1/claims")
        assert res.status_code == 401
        assert "authentication required" in res.json().get("detail", "").lower()


@pytest.mark.database
@pytest.mark.asyncio
async def test_production_mode_accepts_valid_token(monkeypatch):
    """Verify that in production mode, a valid JWT is accepted."""
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")

    token = create_signed_token("user-prod-alice")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/claims",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200


# ==============================================================================
# 2. TENANT ISOLATION / HORIZONTAL PRIVILEGE ESCALATION TESTS
# ==============================================================================

@pytest.mark.database
@pytest.mark.asyncio
async def test_tenant_isolation_cross_user_access_rejected():
    """
    Test horizontal privilege escalation:
    User Alice creates resources. User Bob must NOT be able to view,
    adjudicate, or export Alice's claims, EOBs, appeals, or comparisons.
    """
    alice_token = create_signed_token("user-alice-001")
    bob_token = create_signed_token("user-bob-002")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Alice creates a claim
        bill_bytes = create_synthetic_bill_pdf()
        files = {"file": ("alice_bill.pdf", io.BytesIO(bill_bytes), "application/pdf")}
        up_res = await client.post(
            "/api/v1/claims/upload-bill",
            files=files,
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert up_res.status_code == 201
        bill_id = up_res.json()["bill_id"]

        create_res = await client.post(
            "/api/v1/claims",
            json={
                "policy_id": "m6-test-policy",
                "bill_id": bill_id,
                "provider_name": "St. Jude Clinic",
                "incident_date": "2026-04-10",
            },
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert create_res.status_code == 201
        alice_claim_id = create_res.json()["id"]

        # Alice adjudicates claim
        adj_res = await client.post(
            f"/api/v1/claims/{alice_claim_id}/adjudicate",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert adj_res.status_code == 200

        # 2. Bob attempts to access Alice's claim -> 403 Forbidden
        bob_get_claim = await client.get(
            f"/api/v1/claims/{alice_claim_id}",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_get_claim.status_code == 403
        assert "access denied" in bob_get_claim.json()["detail"].lower()

        # 3. Bob attempts to download Alice's EOB PDF -> 403 Forbidden
        bob_eob_pdf = await client.get(
            f"/api/v1/claims/{alice_claim_id}/eob/pdf",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_eob_pdf.status_code == 403

        # 4. Bob attempts to generate appeal for Alice's claim -> 403 Forbidden
        bob_appeal = await client.post(
            f"/api/v1/claims/{alice_claim_id}/appeal-draft",
            json={"denial_reason_code": "DENIAL-01"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_appeal.status_code == 403

        # 5. Bob attempts to download Alice's appeal PDF -> 403 Forbidden
        bob_appeal_pdf = await client.get(
            f"/api/v1/claims/{alice_claim_id}/appeal-draft/pdf",
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert bob_appeal_pdf.status_code == 403


# ==============================================================================
# 3. SERVER-SIDE PDF EXPORT TESTS
# ==============================================================================

@pytest.mark.database
@pytest.mark.asyncio
async def test_eob_pdf_export_success():
    """Verify that an adjudicated claim generates a valid, styled EOB PDF."""
    user_token = create_signed_token("user-pdf-tester")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create and adjudicate claim
        bill_bytes = create_synthetic_bill_pdf()
        up_res = await client.post(
            "/api/v1/claims/upload-bill",
            files={"file": ("bill.pdf", io.BytesIO(bill_bytes), "application/pdf")},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        bill_id = up_res.json()["bill_id"]

        create_res = await client.post(
            "/api/v1/claims",
            json={
                "policy_id": "m6-test-policy",
                "bill_id": bill_id,
                "provider_name": "City Specialist Center",
                "incident_date": "2026-04-10",
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        claim_id = create_res.json()["id"]

        await client.post(
            f"/api/v1/claims/{claim_id}/adjudicate",
            headers={"Authorization": f"Bearer {user_token}"},
        )

        # Download EOB PDF
        pdf_res = await client.get(
            f"/api/v1/claims/{claim_id}/eob/pdf",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert "attachment" in pdf_res.headers["content-disposition"]
        assert pdf_res.content.startswith(b"%PDF-")
        assert len(pdf_res.content) > 1000

        # Validate that PyMuPDF can parse the generated PDF
        doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
        assert doc.page_count >= 1
        page_text = doc[0].get_text()
        assert "Explanation of Benefits" in page_text or "EOB" in page_text
        doc.close()


@pytest.mark.database
@pytest.mark.asyncio
async def test_appeal_pdf_reviewed_status_enforcement():
    """
    Verify state enforcement:
    1. Unreviewed draft (status = 'generated') must REJECT PDF export (400 Bad Request).
    2. Reviewed/edited draft (status = 'user_edited') must SUCCEED (200 OK, valid PDF).
    """
    user_token = create_signed_token("user-appeal-pdf-tester")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create and adjudicate claim
        bill_bytes = create_synthetic_bill_pdf()
        up_res = await client.post(
            "/api/v1/claims/upload-bill",
            files={"file": ("bill.pdf", io.BytesIO(bill_bytes), "application/pdf")},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        bill_id = up_res.json()["bill_id"]
        create_res = await client.post(
            "/api/v1/claims",
            json={
                "policy_id": "m6-test-policy",
                "bill_id": bill_id,
                "provider_name": "Specialist",
                "incident_date": "2026-04-10",
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        claim_id = create_res.json()["id"]
        await client.post(
            f"/api/v1/claims/{claim_id}/adjudicate",
            headers={"Authorization": f"Bearer {user_token}"},
        )

        # 1. Generate appeal draft (initial state is 'generated')
        draft_res = await client.post(
            f"/api/v1/claims/{claim_id}/appeal-draft",
            json={"denial_reason_code": "DENIAL-EXCL-101"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert draft_res.status_code == 201
        assert draft_res.json()["status"] == "generated"

        # 2. Attempt PDF download before user review -> Expect 400 Bad Request
        unreviewed_pdf_res = await client.get(
            f"/api/v1/claims/{claim_id}/appeal-draft/pdf",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert unreviewed_pdf_res.status_code == 400
        assert "must be reviewed" in unreviewed_pdf_res.json()["detail"].lower()

        # 3. User reviews and saves edits -> state becomes 'user_edited'
        update_res = await client.put(
            f"/api/v1/claims/{claim_id}/appeal-draft",
            json={
                "statement_of_issue": "Dispute of denial code DENIAL-EXCL-101.",
                "rebuttal_narrative": "Service was pre-authorized and medically necessary.",
                "requested_action": "Reverse denial and process payment.",
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["status"] == "user_edited"

        # 4. Attempt PDF download after review -> Expect 200 OK, valid PDF
        reviewed_pdf_res = await client.get(
            f"/api/v1/claims/{claim_id}/appeal-draft/pdf",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert reviewed_pdf_res.status_code == 200
        assert reviewed_pdf_res.headers["content-type"] == "application/pdf"
        assert reviewed_pdf_res.content.startswith(b"%PDF-")

        # Validate with PyMuPDF
        doc = pymupdf.open(stream=reviewed_pdf_res.content, filetype="pdf")
        assert doc.page_count >= 1
        page_text = doc[0].get_text()
        assert "Denial Appeal" in page_text or "Appeal" in page_text
        assert "Reverse denial" in page_text or "REBUTTAL" in page_text
        doc.close()


@pytest.mark.database
@pytest.mark.asyncio
async def test_comparison_pdf_export_success():
    """Verify that a policy comparison report generates a valid PDF."""
    user_token = create_signed_token("user-compare-pdf-tester")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create comparison record with 2 valid policies
        comp_res = await client.post(
            "/api/v1/comparisons",
            json={
                "policy_ids": ["m6-test-policy-1", "m6-test-policy-2"],
                "title": "Comprehensive Benefit Comparison",
                "cost_assumptions": {
                    "service_type": "Specialist Visit",
                    "billed_charges_cents": 50000,
                    "allowed_amount_cents": 40000,
                    "is_allowed_amount_known": True,
                },
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert comp_res.status_code == 201
        comp_id = comp_res.json()["id"]

        # Export comparison PDF
        pdf_res = await client.get(
            f"/api/v1/comparisons/{comp_id}/pdf",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content.startswith(b"%PDF-")

        doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
        assert doc.page_count >= 1
        page_text = doc[0].get_text()
        assert "Multi-Policy Comparison" in page_text or "COMPARISON" in page_text.upper()
        doc.close()


# ==============================================================================
# 4. CRYPTOGRAPHIC AUDIT TRAIL & TAMPER-EVIDENT HASH CHAIN TESTS
# ==============================================================================

@pytest.mark.database
@pytest.mark.asyncio
async def test_audit_hash_chain_sequential_integrity():
    """
    Verify SHA-256 hash chaining:
    Each event includes the SHA-256 of its predecessor.
    Verification across untampered events returns valid=True.
    """
    user_id = "user-audit-chain-001"

    # Record 3 sequential events
    e1 = await audit_repo.record_event(
        AuditEventCreate(
            action="policy.upload",
            resource_type="policy",
            resource_id="pol-101",
            user_id=user_id,
            metadata={"document_name": "GoldPlan.pdf"},
        )
    )
    e2 = await audit_repo.record_event(
        AuditEventCreate(
            action="claim.create",
            resource_type="claim",
            resource_id="clm-202",
            user_id=user_id,
            metadata={"provider": "Clinic A"},
        )
    )
    e3 = await audit_repo.record_event(
        AuditEventCreate(
            action="claim.adjudicate",
            resource_type="claim",
            resource_id="clm-202",
            user_id=user_id,
            metadata={"items_adjudicated": 3},
        )
    )

    assert e1.sequence_number < e2.sequence_number < e3.sequence_number
    assert e2.previous_hash == e1.event_hash
    assert e3.previous_hash == e2.event_hash

    # Verify chain
    result = audit_service.verify_chain([e1, e2, e3])
    assert result.is_valid is True
    assert result.total_events == 3
    assert result.verified_count == 3
    assert result.chain_head_hash == e3.event_hash


def test_audit_tamper_detection_modified_payload():
    """Verify that tampering with an event payload breaks mathematical verification."""
    user_id = "user-tamper-tester"
    e1 = audit_service.build_event(
        action="policy.upload",
        resource_type="policy",
        resource_id="pol-1",
        user_id=user_id,
        metadata={"name": "Original.pdf"},
        sequence_number=1,
        previous_hash=audit_service.GENESIS_HASH,
    )
    e2 = audit_service.build_event(
        action="claim.create",
        resource_type="claim",
        resource_id="clm-1",
        user_id=user_id,
        metadata={"amount": 100},
        sequence_number=2,
        previous_hash=e1.event_hash,
    )

    # Tamper with event 1's action without updating its cryptographic hash
    tampered_e1 = e1.model_copy(update={"action": "unauthorized.admin.override"})

    result = audit_service.verify_chain([tampered_e1, e2])
    assert result.is_valid is False
    assert result.tampered_event_id == tampered_e1.event_id
    assert "hash mismatch" in result.error_reason.lower() or "tamper" in result.error_reason.lower()


def test_audit_tamper_detection_broken_chain_link():
    """Verify that deleting or reordering events breaks the sequence."""
    user_id = "user-reorder-tester"
    e1 = audit_service.build_event(
        action="action.1",
        resource_type="res",
        user_id=user_id,
        sequence_number=1,
        previous_hash=audit_service.GENESIS_HASH,
    )
    e2 = audit_service.build_event(
        action="action.2",
        resource_type="res",
        user_id=user_id,
        sequence_number=2,
        previous_hash=e1.event_hash,
    )
    e3 = audit_service.build_event(
        action="action.3",
        resource_type="res",
        user_id=user_id,
        sequence_number=4,  # Intentionally skip sequence 3 to simulate deleted record
        previous_hash=e2.event_hash,
    )

    # Chain with sequence gap
    result = audit_service.verify_chain([e1, e2, e3])
    assert result.is_valid is False
    assert "sequence break" in result.error_reason.lower()


def test_audit_sensitive_data_redaction():
    """Verify that sensitive PHI/credentials are automatically redacted from audit logs."""
    raw_meta = {
        "user_token": "secret-bearer-token-12345",
        "password": "SuperSecretPassword!",
        "ssn": "123-45-6789",
        "clinical_notes": "Patient diagnosed with confidential condition.",
        "allowed_charge": 5000,
    }
    redacted = audit_service.sanitize_metadata(raw_meta)
    assert redacted["user_token"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["ssn"] == "[REDACTED]"
    assert redacted["clinical_notes"] == "[REDACTED]"
    assert redacted["allowed_charge"] == 5000


@pytest.mark.database
@pytest.mark.asyncio
async def test_audit_api_verification_endpoint():
    """Verify the POST /api/v1/audit/verify endpoint via HTTP API."""
    user_token = create_signed_token("user-audit-api-caller")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create an event first
        await audit_repo.record_event(
            AuditEventCreate(
                action="settings.inspect",
                resource_type="system",
                user_id="user-audit-api-caller",
                metadata={"test": True},
            )
        )

        res = await client.post(
            "/api/v1/audit/verify",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_valid"] is True
        assert data["verified_count"] >= 1
        assert data["chain_head_hash"] is not None
