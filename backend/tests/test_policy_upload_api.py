"""Integration tests for Policy Upload and Rules API endpoints."""

import io
import pytest
from app.core.security import create_access_token
from httpx import ASGITransport, AsyncClient
import pymupdf

from app.main import app
from app.core.config import get_settings


def create_sample_pdf() -> bytes:
    """Create a minimal valid PDF in memory."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Section 1.1: Standard In-Network Coverage\nInpatient care is 80% covered.")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.database
@pytest.mark.asyncio
async def test_upload_valid_pdf():
    """Verify POST /api/v1/policies/upload with valid PDF."""
    pdf_data = create_sample_pdf()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {"file": ("test_policy.pdf", io.BytesIO(pdf_data), "application/pdf")}
        response = await client.post("/api/v1/policies/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["document_name"] == "test_policy.pdf"
    assert data["status"] == "success"
    assert data["total_pages"] == 1
    assert data["total_clauses"] >= 1
    assert len(data["document_hash"]) == 64
    assert data["persistence_mode"] in ("persistent_db", "development_preview")
    assert len(data["policy_id"]) > 0


@pytest.mark.asyncio
async def test_upload_non_pdf_extension():
    """Verify rejection of non-PDF extension."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {"file": ("notes.txt", io.BytesIO(b"Hello text file"), "text/plain")}
        response = await client.post("/api/v1/policies/upload", files=files)

    assert response.status_code == 415
    assert "Unsupported file extension" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_disguised_fake_pdf():
    """Verify rejection of non-PDF file disguised with .pdf extension."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        # File named .pdf but containing plaintext bytes (no %PDF header)
        files = {"file": ("malicious.pdf", io.BytesIO(b"NOT_A_PDF_FILE_HEADER"), "application/pdf")}
        response = await client.post("/api/v1/policies/upload", files=files)

    assert response.status_code == 415
    assert "Invalid file signature" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file():
    """Verify rejection of 0-byte uploaded file."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        response = await client.post("/api/v1/policies/upload", files=files)

    assert response.status_code == 400
    assert "empty (0 bytes)" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_oversized_file():
    """Verify rejection of file exceeding max_upload_size_bytes."""
    settings = get_settings()
    # Temporarily set max_size to 100 bytes for testing
    orig_max = settings.max_upload_size_bytes
    settings.max_upload_size_bytes = 100

    try:
        pdf_data = create_sample_pdf()  # > 100 bytes
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
            files = {"file": ("large.pdf", io.BytesIO(pdf_data), "application/pdf")}
            response = await client.post("/api/v1/policies/upload", files=files)

        assert response.status_code == 413
        assert "exceeds maximum allowed upload size" in response.json()["detail"]
    finally:
        settings.max_upload_size_bytes = orig_max


@pytest.mark.database
@pytest.mark.asyncio
async def test_list_and_get_policy_endpoints():
    """Verify GET /api/v1/policies and GET /api/v1/policies/{id}."""
    pdf_data = create_sample_pdf()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {"file": ("my_policy.pdf", io.BytesIO(pdf_data), "application/pdf")}
        upload_res = await client.post("/api/v1/policies/upload", files=files)
        assert upload_res.status_code == 201
        policy_id = upload_res.json()["policy_id"]

        list_res = await client.get("/api/v1/policies")
        assert list_res.status_code == 200
        policies = list_res.json()
        assert any(p["policy_id"] == policy_id for p in policies)

        get_res = await client.get(f"/api/v1/policies/{policy_id}")
        assert get_res.status_code == 200
        assert get_res.json()["policy_id"] == policy_id


@pytest.mark.asyncio
async def test_rules_calculate_endpoint():
    """Verify POST /api/v1/rules/calculate with valid payload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        payload = {
            "eligible_expense_cents": 100000,
            "remaining_deductible_cents": 50000,
            "member_coinsurance_percentage": 20.0,
            "remaining_out_of_pocket_max_cents": 200000,
        }
        res = await client.post("/api/v1/rules/calculate", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert data["member_total_cents"] == 60000
    assert data["insurer_total_cents"] == 40000
    assert data["deductible_paid_cents"] == 50000
    assert data["member_coinsurance_cents"] == 10000
    assert "educational calculations" in data["disclaimer"]


@pytest.mark.asyncio
async def test_rules_calculate_validation_error():
    """Verify POST /api/v1/rules/calculate rejects negative amounts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        payload = {
            "eligible_expense_cents": -500,
            "remaining_deductible_cents": 50000,
            "member_coinsurance_percentage": 20.0,
            "remaining_out_of_pocket_max_cents": 200000,
        }
        res = await client.post("/api/v1/rules/calculate", json=payload)

    assert res.status_code == 400
    assert "Validation failed" in res.json()["detail"]
