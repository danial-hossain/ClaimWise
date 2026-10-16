"""Integration tests for Policy Q&A API endpoints."""

import io
import json
import pytest
from app.core.security import create_access_token
from httpx import ASGITransport, AsyncClient
import pymupdf

from app.main import app
from app.services.qa_service import qa_service


def create_primary_care_policy_pdf(include_benefit: bool) -> bytes:
    """Create a complete synthetic policy with or without primary-care wording."""
    doc = pymupdf.open()
    page = doc.new_page()
    text = (
        "Section 4.2: Primary Care Office Visits. Primary care office visits are covered "
        "subject to a $25 copayment per visit."
        if include_benefit
        else "Section 1.1: Vehicle Damage. The insurer covers accidental damage to the insured vehicle."
    )
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_sample_policy_pdf() -> bytes:
    """Create synthetic test PDF with clear clauses."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Section 1.1: Emergency Room Copayment\n"
        "Emergency room visits require a mandatory copayment of 250 dollars before coverage applies."
    )
    page.insert_text(
        (50, 160),
        "Section 2.0: Annual Deductible\n"
        "The individual annual deductible is set at 1000 dollars for standard in-network care."
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.asyncio
async def test_get_qa_status_endpoint():
    """Verify GET /api/v1/qa/status returns operational status of all pipeline components."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        res = await client.get("/api/v1/qa/status")

    assert res.status_code == 200
    data = res.json()
    assert "gemini_engine" in data
    assert "dense_embeddings" in data
    assert "bm25_lexical" in data
    assert "hybrid_fusion" in data
    assert data["hybrid_fusion"]["algorithm"] == "Reciprocal Rank Fusion (RRF)"


@pytest.mark.database
@pytest.mark.asyncio
async def test_qa_ask_policy_not_found():
    """Verify POST /api/v1/qa/ask with nonexistent policy ID returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        payload = {
            "question": "What is the deductible?",
            "policy_id": "nonexistent-policy-9999",
        }
        res = await client.post("/api/v1/qa/ask", json=payload)

    assert res.status_code == 404
    assert "not found in active session" in res.json()["detail"]


@pytest.mark.asyncio
async def test_qa_ask_short_question_rejected():
    """Verify question shorter than 3 characters returns 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        payload = {
            "question": "ab",
            "policy_id": "some-policy",
        }
        res = await client.post("/api/v1/qa/ask", json=payload)

    assert res.status_code == 422 or res.status_code == 400


@pytest.mark.database
@pytest.mark.asyncio
async def test_qa_ask_successful_workflow(monkeypatch):
    """Verify complete upload -> retrieval -> grounded Q&A workflow with mocked Gemini response."""
    # 1. Upload policy
    pdf_bytes = create_sample_policy_pdf()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {"file": ("benefit_schedule.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_res = await client.post("/api/v1/policies/upload", files=files)
        assert upload_res.status_code == 201
        assert upload_res.status_code == 201
        policy_id = upload_res.json()["policy_id"]

        # 2. Mock Gemini API call in qa_service for offline determinism
        def mock_call(prompt, model_name, api_key):
            return json.dumps({
                "answer": "Emergency room visits require a mandatory copayment of 250 dollars before coverage applies.",
                "evidence_sufficient": True,
                "abstention_reason": None,
                "clarification_question": None,
                "citations": [
                    {
                        "clause_id": "SEC-1.1",
                        "page_number": 1,
                        "exact_quote": "Emergency room visits require a mandatory copayment of 250 dollars",
                        "policy_id": policy_id,
                    }
                ],
            })

        monkeypatch.setattr(qa_service, "_call_gemini_api", mock_call)
        monkeypatch.setattr(qa_service, "is_configured", lambda: True)

        # 3. Query the policy
        ask_payload = {
            "question": "What is the emergency room copay under this policy?",
            "policy_id": policy_id,
        }
        ask_res = await client.post("/api/v1/qa/ask", json=ask_payload)

    assert ask_res.status_code == 200
    data = ask_res.json()
    assert data["evidence_sufficient"] is True
    assert data["evidence_status"] == "supported"
    assert "250 dollars" in data["answer"]
    assert len(data["citations"]) == 1
    assert data["citations"][0]["clause_id"] == "SEC-1.1"
    assert data["citations"][0]["page_number"] == 1
    assert len(data["retrieved_evidence"]) >= 1


@pytest.mark.database
@pytest.mark.asyncio
async def test_qa_ask_recovers_primary_care_clause_after_hybrid_miss(monkeypatch):
    """A direct scan of the selected complete policy recovers and cites PCP wording."""
    from app.api.v1.endpoints.qa import hybrid_retrieval_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {
            "file": (
                "primary_care.pdf",
                io.BytesIO(create_primary_care_policy_pdf(include_benefit=True)),
                "application/pdf",
            )
        }
        upload_res = await client.post("/api/v1/policies/upload", files=files)
        assert upload_res.status_code == 201
        policy_data = upload_res.json()
        policy_id = policy_data["policy_id"]
        clause = next(
            item for item in policy_data["clauses"]
            if "Primary care office visits are covered" in item["text"]
        )

        monkeypatch.setattr(
            hybrid_retrieval_service,
            "retrieve",
            lambda **kwargs: ([], "hybrid"),
        )

        def mock_call(prompt, model_name, api_key):
            return json.dumps({
                "answer": "Primary care office visits are covered subject to a $25 copayment per visit.",
                "evidence_sufficient": True,
                "evidence_status": "supported",
                "abstention_reason": None,
                "clarification_question": None,
                "citations": [{
                    "clause_id": clause["clause_id"],
                    "page_number": clause["page_number"],
                    "exact_quote": clause["text"],
                    "policy_id": policy_id,
                }],
            })

        monkeypatch.setattr(qa_service, "_call_gemini_api", mock_call)
        monkeypatch.setattr(qa_service, "is_configured", lambda: True)
        ask_res = await client.post(
            "/api/v1/qa/ask",
            json={"question": "What is the primary care office visit copayment?", "policy_id": policy_id},
        )

    assert ask_res.status_code == 200
    data = ask_res.json()
    assert data["evidence_sufficient"] is True
    assert data["evidence_status"] == "supported"
    assert len(data["citations"]) == 1
    assert data["citations"][0]["clause_id"] == clause["clause_id"]
    assert data["citations"][0]["page_number"] == clause["page_number"]
    assert data["citations"][0]["exact_quote"] == clause["text"]


@pytest.mark.database
@pytest.mark.asyncio
async def test_qa_ask_silent_complete_policy_returns_not_specified():
    """A complete unrelated policy returns not_specified, not an exclusion."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {
            "file": (
                "vehicle_policy.pdf",
                io.BytesIO(create_primary_care_policy_pdf(include_benefit=False)),
                "application/pdf",
            )
        }
        upload_res = await client.post("/api/v1/policies/upload", files=files)
        assert upload_res.status_code == 201
        assert upload_res.status_code == 201
        policy_id = upload_res.json()["policy_id"]
        ask_res = await client.post(
            "/api/v1/qa/ask",
            json={"question": "Is routine primary care covered?", "policy_id": policy_id},
        )

    assert ask_res.status_code == 200
    data = ask_res.json()
    assert data["evidence_sufficient"] is False
    assert data["evidence_status"] == "not_specified"
    assert data["citations"] == []
    assert "does not specify this benefit" in data["answer"]
    assert "not evidence that the benefit is excluded" in data["answer"]


@pytest.mark.database
@pytest.mark.asyncio
async def test_qa_ask_gemini_unconfigured_safe_abstention(monkeypatch):
    """Verify that when GEMINI_API_KEY is not configured, QA endpoint abstains safely."""
    pdf_bytes = create_sample_policy_pdf()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {"file": ("benefit_schedule.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_res = await client.post("/api/v1/policies/upload", files=files)
        assert upload_res.status_code == 201
        policy_id = upload_res.json()["policy_id"]

        monkeypatch.setattr(qa_service, "is_configured", lambda: False)

        ask_res = await client.post(
            "/api/v1/qa/ask",
            json={"question": "What is the deductible?", "policy_id": policy_id},
        )

    assert ask_res.status_code == 200
    data = ask_res.json()
    assert data["evidence_sufficient"] is False
    assert "GEMINI_API_KEY is not configured" in data["abstention_reason"]
    assert data["citations"] == []


@pytest.mark.database
@pytest.mark.asyncio
async def test_qa_ask_provider_error_handled_safely(monkeypatch):
    """Verify that when Gemini API raises a timeout or quota error, endpoint handles it safely."""
    pdf_bytes = create_sample_policy_pdf()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")}) as client:
        files = {"file": ("benefit_schedule.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        upload_res = await client.post("/api/v1/policies/upload", files=files)
        assert upload_res.status_code == 201
        policy_id = upload_res.json()["policy_id"]

        def mock_error_call(prompt, model_name, api_key):
            raise RuntimeError("Gemini API Error 429: Resource has been exhausted (quota exceeded).")

        monkeypatch.setattr(qa_service, "_call_gemini_api", mock_error_call)
        monkeypatch.setattr(qa_service, "is_configured", lambda: True)

        ask_res = await client.post(
            "/api/v1/qa/ask",
            json={"question": "What is the deductible?", "policy_id": policy_id},
        )

    assert ask_res.status_code == 200
    data = ask_res.json()
    assert data["evidence_sufficient"] is False
    assert "LLM synthesis failure" in data["abstention_reason"]
    assert "quota exceeded" not in str(data).lower()
    assert "Resource has been exhausted" not in str(data)
