"""Integration tests for Claims API, Adjudication, and Mock Sandbox Gateway Endpoints."""

import io
import pytest
from httpx import ASGITransport, AsyncClient
import pymupdf

from app.main import app
from app.schemas.policy import ExtractedClause
from app.services.retrieval.hybrid_service import hybrid_retrieval_service


def create_test_bill_pdf() -> bytes:
    """Create synthetic test medical bill."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 40), "CITY MEMORIAL HOSPITAL")
    page.insert_text((50, 80), "2026-03-15 99284 Emergency Dept Visit Level 4 Qty: 1 $1,250.00")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture(autouse=True)
def index_clauses_for_api_tests():
    """Seed hybrid retrieval with clauses for api tests."""
    policy_id = "dev-policy-claims-test"
    clauses = [
        ExtractedClause(
            clause_id="SEC-1.1",
            page_number=1,
            clause_heading="Emergency Room Services",
            heading_confidence="high",
            section_number="1.1",
            text="Section 1.1: Emergency Room Services require a $250 copayment followed by deductible.",
            token_count=15,
            document_hash="doc-hash-test",
        )
    ]
    hybrid_retrieval_service.index_policy(policy_id, clauses, "doc-hash-test")


@pytest.mark.asyncio
async def test_claims_end_to_end_workflow():
    """Verify complete bill upload -> claim creation -> adjudication -> sandbox submission."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Upload medical bill
        bill_bytes = create_test_bill_pdf()
        files = {"file": ("hospital_bill.pdf", io.BytesIO(bill_bytes), "application/pdf")}
        upload_res = await client.post("/api/v1/claims/upload-bill", files=files)
        assert upload_res.status_code == 201
        bill_data = upload_res.json()
        assert bill_data["total_pages"] == 1
        assert len(bill_data["line_items"]) == 1
        bill_id = bill_data["bill_id"]

        # 2. Create claim from bill
        create_payload = {
            "policy_id": "dev-policy-claims-test",
            "bill_id": bill_id,
            "claim_reference": "CW-TEST-001",
        }
        create_res = await client.post("/api/v1/claims", json=create_payload)
        assert create_res.status_code == 201
        claim_data = create_res.json()
        assert claim_data["status"] == "draft"
        claim_id = claim_data["id"]

        # 3. List claims
        list_res = await client.get("/api/v1/claims")
        assert list_res.status_code == 200
        assert any(c["id"] == claim_id for c in list_res.json())

        # 4. Get specific claim
        get_res = await client.get(f"/api/v1/claims/{claim_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == claim_id

        # 5. EOB should return 400 before adjudication
        pre_eob_res = await client.get(f"/api/v1/claims/{claim_id}/eob")
        assert pre_eob_res.status_code == 400

        # 6. Run adjudication
        adj_payload = {
            "member_coinsurance_percentage": 20.0,
            "initial_remaining_deductible_cents": 50000,
            "initial_remaining_oop_max_cents": 300000,
        }
        adj_res = await client.post(f"/api/v1/claims/{claim_id}/adjudicate", json=adj_payload)
        assert adj_res.status_code == 200
        eob_data = adj_res.json()
        assert len(eob_data["items"]) == 1
        assert eob_data["total_billed_cents"] == 125000
        assert eob_data["items"][0]["decision_status"] == "potentially_covered"

        # 7. Retrieve EOB
        post_eob_res = await client.get(f"/api/v1/claims/{claim_id}/eob")
        assert post_eob_res.status_code == 200
        assert post_eob_res.json()["eob_id"] == eob_data["eob_id"]

        # 8. Sandbox submission without user confirmation must be rejected
        unconfirmed_submit = {
            "user_confirmed": False,
            "idempotency_key": "idemp-001",
        }
        rej_res = await client.post(f"/api/v1/claims/{claim_id}/sandbox-submit", json=unconfirmed_submit)
        assert rej_res.status_code == 400
        assert "user confirmation" in rej_res.json()["detail"].lower()

        # 9. Successful sandbox submission with explicit confirmation
        confirmed_submit = {
            "user_confirmed": True,
            "idempotency_key": "idemp-001",
            "requested_scenario": "approve",
        }
        submit_res = await client.post(f"/api/v1/claims/{claim_id}/sandbox-submit", json=confirmed_submit)
        assert submit_res.status_code == 200
        sandbox_outcome = submit_res.json()
        assert sandbox_outcome["is_simulation"] is True
        assert sandbox_outcome["outcome_status"] == "APPROVED_SIMULATION"
        assert "Apex National" in sandbox_outcome["simulated_payer_name"]

        # 10. Idempotency test: submit with identical idempotency_key returns identical submission_id
        dup_submit_res = await client.post(f"/api/v1/claims/{claim_id}/sandbox-submit", json=confirmed_submit)
        assert dup_submit_res.status_code == 200
        assert dup_submit_res.json()["submission_id"] == sandbox_outcome["submission_id"]

        # 11. Retrieve sandbox status
        status_res = await client.get(f"/api/v1/claims/{claim_id}/sandbox-status")
        assert status_res.status_code == 200
        assert status_res.json()["outcome_status"] == "APPROVED_SIMULATION"


@pytest.mark.asyncio
async def test_claims_upload_bill_rejections():
    """Verify invalid file uploads (non-PDF, empty) are rejected properly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Non-PDF file
        txt_files = {"file": ("bill.txt", io.BytesIO(b"billed $500"), "text/plain")}
        res = await client.post("/api/v1/claims/upload-bill", files=txt_files)
        assert res.status_code == 415

        # Empty PDF
        empty_files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        res2 = await client.post("/api/v1/claims/upload-bill", files=empty_files)
        assert res2.status_code == 400


@pytest.mark.asyncio
async def test_sandbox_scenarios_deterministic():
    """Verify each deterministic sandbox scenario returns the expected mock status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup claim
        bill_bytes = create_test_bill_pdf()
        files = {"file": ("hospital_bill.pdf", io.BytesIO(bill_bytes), "application/pdf")}
        upload_res = await client.post("/api/v1/claims/upload-bill", files=files)
        bill_id = upload_res.json()["bill_id"]

        create_res = await client.post(
            "/api/v1/claims",
            json={"policy_id": "dev-policy-claims-test", "bill_id": bill_id},
        )
        claim_id = create_res.json()["id"]

        # Adjudicate first so state is 'analyzed'
        await client.post(f"/api/v1/claims/{claim_id}/adjudicate")

        # Scenario: deny_exclusion
        deny_res = await client.post(
            f"/api/v1/claims/{claim_id}/sandbox-submit",
            json={"user_confirmed": True, "idempotency_key": "idemp-deny-01", "requested_scenario": "deny_exclusion"},
        )
        assert deny_res.status_code == 200
        assert deny_res.json()["outcome_status"] == "DENIED_EXCLUSION_SIMULATION"
        assert deny_res.json()["simulated_paid_amount_cents"] == 0

        # Scenario: partial
        part_res = await client.post(
            f"/api/v1/claims/{claim_id}/sandbox-submit",
            json={"user_confirmed": True, "idempotency_key": "idemp-part-01", "requested_scenario": "partial"},
        )
        assert part_res.status_code == 200
        assert part_res.json()["outcome_status"] == "PARTIALLY_APPROVED_SIMULATION"

        # Scenario: request_info
        req_res = await client.post(
            f"/api/v1/claims/{claim_id}/sandbox-submit",
            json={"user_confirmed": True, "idempotency_key": "idemp-req-01", "requested_scenario": "request_info"},
        )
        assert req_res.status_code == 200
        assert req_res.json()["outcome_status"] == "PENDING_ADDITIONAL_INFO"

        # Scenario: gateway_error
        err_res = await client.post(
            f"/api/v1/claims/{claim_id}/sandbox-submit",
            json={"user_confirmed": True, "idempotency_key": "idemp-err-01", "requested_scenario": "gateway_error"},
        )
        assert err_res.status_code == 200
        assert err_res.json()["outcome_status"] == "SIMULATED_TRANSMISSION_ERROR"


@pytest.mark.asyncio
async def test_claim_create_with_edited_line_items():
    """Verify user can provide reviewed/corrected line items during claim creation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        bill_bytes = create_test_bill_pdf()
        files = {"file": ("hospital_bill.pdf", io.BytesIO(bill_bytes), "application/pdf")}
        upload_res = await client.post("/api/v1/claims/upload-bill", files=files)
        bill_id = upload_res.json()["bill_id"]

        edited_items = [
            {
                "line_id": "LINE-01",
                "service_date": "2026-03-20",
                "description": "Corrected ED Visit Description",
                "cpt_code": "99284",
                "billed_charge_cents": 110000,  # Corrected to $1,100.00
                "quantity": 1,
                "source_page_number": 1,
                "raw_text_excerpt": "Raw excerpt line",
            }
        ]

        create_res = await client.post(
            "/api/v1/claims",
            json={
                "policy_id": "dev-policy-claims-test",
                "bill_id": bill_id,
                "line_items": edited_items,
            },
        )
        assert create_res.status_code == 201
        data = create_res.json()
        assert data["total_billed_cents"] == 110000
        assert data["line_items"][0]["description"] == "Corrected ED Visit Description"


@pytest.mark.asyncio
async def test_claim_not_found_errors():
    """Verify 404 returned for nonexistent claim references."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/claims/nonexistent-claim-id-999")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

