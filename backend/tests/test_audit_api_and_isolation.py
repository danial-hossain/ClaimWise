import io
import uuid
import pytest
import pymupdf
from starlette.testclient import TestClient

from app.core.security import (
    COOKIE_ACCESS_TOKEN_KEY,
    COOKIE_CSRF_TOKEN_KEY,
    create_access_token,
)
from app.db.audit_repo import audit_repo
from app.schemas.audit import AuditEventCreate
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_a_client():
    c = TestClient(app)
    token = create_access_token(
        user_id="usr-audit-test-a",
        email="user_a@example.com",
        role="policyholder",
        tier=1,
    )
    c.cookies.set(COOKIE_ACCESS_TOKEN_KEY, token)
    c.cookies.set(COOKIE_CSRF_TOKEN_KEY, "csrf-test-token-a")
    return c


@pytest.fixture
def user_b_client():
    c = TestClient(app)
    token = create_access_token(
        user_id="usr-audit-test-b",
        email="user_b@example.com",
        role="policyholder",
        tier=1,
    )
    c.cookies.set(COOKIE_ACCESS_TOKEN_KEY, token)
    c.cookies.set(COOKIE_CSRF_TOKEN_KEY, "csrf-test-token-b")
    return c


def test_audit_events_unauthenticated_rejected(client: TestClient):
    """Verify unauthenticated requests to GET /api/v1/audit/events are rejected with 401."""
    response = client.get("/api/v1/audit/events")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_audit_verify_unauthenticated_rejected(client: TestClient):
    """Verify unauthenticated requests to POST /api/v1/audit/verify are rejected with 401."""
    response = client.post("/api/v1/audit/verify")
    assert response.status_code == 401


@pytest.mark.database
@pytest.mark.asyncio
async def test_audit_tenant_isolation(user_a_client: TestClient, user_b_client: TestClient):
    """Verify strict user-level isolation: User B cannot see User A's audit events."""
    # Record event for User A
    await audit_repo.record_event(
        AuditEventCreate(
            user_id="usr-audit-test-a",
            action="policy.upload",
            resource_type="policy",
            resource_id="pol-test-user-a-secret",
            outcome="success",
            metadata={
                "document_name": "confidential_health_plan.pdf",
                "validation_check": {"pdf_integrity": "valid"},
            },
        )
    )

    # Record event for User B
    await audit_repo.record_event(
        AuditEventCreate(
            user_id="usr-audit-test-b",
            action="claim.create",
            resource_type="claim",
            resource_id="clm-test-user-b-claim",
            outcome="success",
            metadata={"claim_type": "dental"},
        )
    )

    # User A queries events
    resp_a = user_a_client.get("/api/v1/audit/events")
    assert resp_a.status_code == 200
    events_a = resp_a.json()
    ids_a = [e["resource_id"] for e in events_a]
    assert "pol-test-user-a-secret" in ids_a
    assert "clm-test-user-b-claim" not in ids_a

    # User B queries events
    resp_b = user_b_client.get("/api/v1/audit/events")
    assert resp_b.status_code == 200
    events_b = resp_b.json()
    ids_b = [e["resource_id"] for e in events_b]
    assert "clm-test-user-b-claim" in ids_b
    assert "pol-test-user-a-secret" not in ids_b


@pytest.mark.database
@pytest.mark.asyncio
async def test_audit_filtering_and_pagination():
    """Verify query filters (action, resource_type, resource_id, outcome) and pagination with X-Total-Count."""
    user_id = f"usr-audit-test-filter-{uuid.uuid4()}"
    client = TestClient(app)
    token = create_access_token(user_id=user_id, email="filter@example.com", role="policyholder")
    client.cookies.set(COOKIE_ACCESS_TOKEN_KEY, token)

    # Record 3 distinct events
    await audit_repo.record_event(
        AuditEventCreate(
            user_id=user_id,
            action="coverage.analyze",
            resource_type="coverage",
            resource_id="cov-filter-1",
            outcome="covered",
            metadata={
                "clauses": [{"clause_id": "P1-C1", "heading": "Inpatient", "page_number": 1}],
                "validation_check": {"prior_auth": "satisfied"},
            },
        )
    )
    await audit_repo.record_event(
        AuditEventCreate(
            user_id=user_id,
            action="coverage.analyze",
            resource_type="coverage",
            resource_id="cov-filter-2",
            outcome="denied",
            metadata={"reason": "exclusion"},
        )
    )
    await audit_repo.record_event(
        AuditEventCreate(
            user_id=user_id,
            action="claim.adjudicate",
            resource_type="claim",
            resource_id="clm-filter-1",
            outcome="adjudicated",
            metadata={"payout_cents": 50000},
        )
    )

    # Filter by action=coverage.analyze
    resp_action = client.get("/api/v1/audit/events?action=coverage.analyze")
    assert resp_action.status_code == 200
    events_action = resp_action.json()
    assert len(events_action) == 2
    assert all(e["action"] == "coverage.analyze" for e in events_action)

    # Filter by outcome=denied
    resp_outcome = client.get("/api/v1/audit/events?outcome=denied")
    assert resp_outcome.status_code == 200
    events_outcome = resp_outcome.json()
    assert len(events_outcome) == 1
    assert events_outcome[0]["resource_id"] == "cov-filter-2"

    # Filter by resource_id
    resp_res = client.get("/api/v1/audit/events?resource_id=clm-filter-1")
    assert resp_res.status_code == 200
    events_res = resp_res.json()
    assert len(events_res) == 1
    assert events_res[0]["action"] == "claim.adjudicate"

    # Test pagination: limit=1, offset=0
    resp_page1 = client.get("/api/v1/audit/events?limit=1&offset=0")
    assert resp_page1.status_code == 200
    assert len(resp_page1.json()) == 1
    assert resp_page1.headers.get("X-Total-Count") == "3"

    # Test pagination: limit=1, offset=1
    resp_page2 = client.get("/api/v1/audit/events?limit=1&offset=1")
    assert resp_page2.status_code == 200
    assert len(resp_page2.json()) == 1
    assert resp_page2.json()[0]["event_id"] != resp_page1.json()[0]["event_id"]


@pytest.mark.database
@pytest.mark.asyncio
async def test_audit_chain_cryptographic_verification(user_a_client: TestClient):
    """Verify POST /api/v1/audit/verify successfully verifies the SHA-256 hash chain with CSRF token."""
    resp = user_a_client.post(
        "/api/v1/audit/verify",
        headers={"X-CSRF-Token": "csrf-test-token-a"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["total_events"] >= 0
    assert data["verified_count"] == data["total_events"]
    assert "verified_at" in data


def create_sample_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Section 1.1: Standard In-Network Coverage\nInpatient hospital care is 80% covered.")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.database
def test_real_policy_upload_creates_audit_record_with_clauses(user_a_client: TestClient, user_b_client: TestClient):
    """
    Verification:
    1. Perform a real policy upload as authenticated user A.
    2. Confirm that the action creates an audit record in the backend with clauses and validation_check.
    3. User A queries /api/v1/audit/events and verifies the record appears.
    4. User B queries and cannot see User A's policy upload audit record.
    """
    pdf_data = create_sample_pdf()
    files = {"file": ("audit_test_policy.pdf", io.BytesIO(pdf_data), "application/pdf")}

    # Upload as user A
    upload_resp = user_a_client.post(
        "/api/v1/policies/upload",
        files=files,
        headers={"X-CSRF-Token": "csrf-test-token-a"},
    )
    assert upload_resp.status_code == 201
    policy_id = upload_resp.json()["policy_id"]

    # Verify audit record appears for user A
    audit_resp_a = user_a_client.get(f"/api/v1/audit/events?resource_id={policy_id}")
    assert audit_resp_a.status_code == 200
    events_a = audit_resp_a.json()
    assert len(events_a) == 1
    event = events_a[0]
    assert event["action"] == "policy.upload"
    assert event["resource_id"] == policy_id
    assert event["outcome"] == "success"
    assert event["user_id"] == "usr-audit-test-a"

    # Verify clauses and validation check are recorded in metadata
    assert "clauses" in event["metadata"]
    assert len(event["metadata"]["clauses"]) > 0
    assert "validation_check" in event["metadata"]
    assert event["metadata"]["validation_check"]["pdf_signature"] == "verified"
    assert event["metadata"]["validation_check"]["magic_bytes"] == "%PDF-"

    # Verify user B cannot see user A's audit record
    audit_resp_b = user_b_client.get(f"/api/v1/audit/events?resource_id={policy_id}")
    assert audit_resp_b.status_code == 200
    assert len(audit_resp_b.json()) == 0

