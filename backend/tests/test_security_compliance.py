"""Automated Pytest Suite for Security & Compliance Engine.

Verifies:
- Automated PII & PHI Detection & Redaction (SSN, Phone, Email, DOB, Member ID, Cards, NPI, Names)
- Recursive dictionary and metadata sanitization
- 5-Tier Permission Security Model (Tiers 0 through 4)
- FastAPI Security Endpoints: POST /security/mask-pii, GET /security/permission-tiers, GET /security/self-assessment
"""

import pytest
from app.core.security import create_access_token
from starlette.testclient import TestClient

from app.main import app
from app.schemas.security import PermissionTier, PIICategory
from app.services.pii_service import pii_service


@pytest.fixture
def client():
    return TestClient(app, headers={"Authorization": "Bearer " + create_access_token("dev-user-001", "test@example.test")})


def test_pii_masking_ssn():
    """Verify detection and masking of Social Security Numbers."""
    text_with_ssn = "The subscriber's Social Security Number is 123-45-6789."
    
    # Preserve last 4
    res_masked = pii_service.mask_text(text_with_ssn, preserve_last_4=True)
    assert "***-**-6789" in res_masked.masked_text
    assert "123-45-6789" not in res_masked.masked_text
    assert res_masked.pii_detected_count == 1
    assert PIICategory.SSN in res_masked.categories_detected

    # Full redaction
    res_redacted = pii_service.mask_text(text_with_ssn, preserve_last_4=False)
    assert "[REDACTED_SSN]" in res_redacted.masked_text
    assert "123-45-6789" not in res_redacted.masked_text


def test_pii_masking_phone_and_email():
    """Verify detection and masking of phone numbers and email addresses."""
    text = "Contact Jane Doe at (555) 234-5678 or via email at patient.jane@clinic.com for records."
    result = pii_service.mask_text(text, preserve_last_4=True)

    assert "(***) ***-5678" in result.masked_text
    assert "p***@clinic.com" in result.masked_text
    assert "patient.jane@clinic.com" not in result.masked_text
    assert "(555) 234-5678" not in result.masked_text
    assert PIICategory.PHONE in result.categories_detected
    assert PIICategory.EMAIL in result.categories_detected


def test_pii_masking_dob_and_member_id():
    """Verify detection and masking of Dates of Birth and Member/Policy IDs."""
    text = "Patient details: DOB: 08/24/1985 and Member ID: MEM-98765432."
    result = pii_service.mask_text(text, preserve_last_4=True)

    assert "[REDACTED_DOB]" in result.masked_text
    assert "***-****-5432" in result.masked_text
    assert "08/24/1985" not in result.masked_text
    assert "MEM-98765432" not in result.masked_text
    assert PIICategory.DOB in result.categories_detected
    assert PIICategory.MEMBER_ID in result.categories_detected


def test_pii_masking_credit_card_and_npi():
    """Verify detection and masking of 16-digit payment cards and 10-digit NPIs."""
    text = "Billed to card 4111-2222-3333-4444. Treating physician NPI: 1234567890."
    result = pii_service.mask_text(text, preserve_last_4=True)

    assert "****-****-****-4444" in result.masked_text
    assert "[REDACTED_NPI_******]" in result.masked_text
    assert "4111-2222-3333-4444" not in result.masked_text
    assert "1234567890" not in result.masked_text
    assert PIICategory.CREDIT_CARD in result.categories_detected
    assert PIICategory.NPI in result.categories_detected


def test_pii_masking_patient_name():
    """Verify detection of patient and claimant names in clinical context."""
    text = "Encounter Record: Patient Name: Robert Smith was admitted for observation."
    result = pii_service.mask_text(text)

    assert "[REDACTED_PATIENT_NAME]" in result.masked_text
    assert "Robert Smith" not in result.masked_text
    assert PIICategory.PATIENT_NAME in result.categories_detected


def test_pii_sanitize_dictionary_recursive():
    """Verify recursive sanitization of nested dictionaries and lists."""
    raw_payload = {
        "user_id": "usr-101",
        "ssn": "123-45-6789",
        "api_token": "secret-jwt-token",
        "metadata": {
            "contact_email": "support@user.org",
            "notes": "Spoke with Patient Name: Alice Johnson regarding bill.",
        },
        "billing_history": [
            "Paid with card 5555-4444-3333-2222",
            {"phone": "555-888-9999"},
        ],
    }

    sanitized = pii_service.sanitize_dictionary(raw_payload)
    assert sanitized["ssn"] == "[REDACTED]"
    assert sanitized["api_token"] == "[REDACTED]"
    assert "s***@user.org" in sanitized["metadata"]["contact_email"]
    assert "Alice Johnson" not in sanitized["metadata"]["notes"]
    assert "****-****-****-2222" in sanitized["billing_history"][0]
    assert "(***) ***-9999" in sanitized["billing_history"][1]["phone"]


def test_permission_tiers_specification():
    """Verify formal definitions and structural invariants of the 5-Tier Model."""
    tiers = pii_service.get_permission_tiers()
    assert len(tiers) == 5

    tier_map = {t.tier: t for t in tiers}
    assert 0 in tier_map
    assert 1 in tier_map
    assert 2 in tier_map
    assert 3 in tier_map
    assert 4 in tier_map

    # Tier 0 (Read only) has no suggestions
    assert tier_map[0].name == "read_only"
    assert "qa.ask" in tier_map[0].prohibited_actions

    # Tier 1 (Suggest mode) cannot create claims or transmit
    assert tier_map[1].name == "suggest_mode"
    assert "qa.ask" in tier_map[1].allowed_actions
    assert "claim.create" in tier_map[1].prohibited_actions

    # Tier 2 (Draft mode) mandates human confirmation
    assert tier_map[2].requires_human_confirmation is True

    # Tier 3 (Sandbox submit) mandates confirmation and blocks live payer
    assert tier_map[3].requires_human_confirmation is True
    assert "live_payer.connect" in tier_map[3].prohibited_actions

    # Tier 4 (Blocked) has zero allowed actions
    assert tier_map[4].name == "blocked_prohibited"
    assert len(tier_map[4].allowed_actions) == 0
    assert "live_carrier.transmission" in tier_map[4].prohibited_actions


def test_security_api_mask_endpoint(client):
    """Test POST /api/v1/security/mask-pii."""
    req = {
        "text": "Member ID: BCBS-12345678 filed claim for John Doe with SSN 123-45-6789.",
        "preserve_last_4": True,
    }
    response = client.post("/api/v1/security/mask-pii", json=req)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["pii_detected_count"] >= 2
    assert "***-**-6789" in data["masked_text"]
    assert "***-****-5678" in data["masked_text"]
    assert "123-45-6789" not in data["masked_text"]


def test_security_api_permission_tiers_endpoint(client):
    """Test GET /api/v1/security/permission-tiers."""
    response = client.get("/api/v1/security/permission-tiers")
    assert response.status_code == 200, response.text
    tiers = response.json()

    assert len(tiers) == 5
    tier_nums = [t["tier"] for t in tiers]
    assert tier_nums == [0, 1, 2, 3, 4]


def test_security_api_self_assessment_endpoint(client):
    """Test GET /api/v1/security/self-assessment."""
    response = client.get("/api/v1/security/self-assessment")
    assert response.status_code == 200, response.text
    report = response.json()

    assert report["overall_compliance_score_pct"] == 100.0
    assert "HIPAA Security & Privacy Rule (45 CFR § 164 Subparts C & E)" in report["frameworks_evaluated"]
    assert "SOC 2 Type II Trust Services Criteria (Security & Confidentiality)" in report["frameworks_evaluated"]

    # Verify all 6 evaluated subsystems pass
    subsystems = report["subsystem_evaluations"]
    assert subsystems["cryptographic_audit_hash_chain"]["status"] == "PASS"
    assert subsystems["prompt_injection_defense"]["status"] == "PASS"
    assert subsystems["pii_phi_masking_engine"]["status"] == "PASS"
    assert subsystems["permission_tiers_model"]["status"] == "PASS"
    assert subsystems["tenant_isolation_rbac"]["status"] == "PASS"
    assert subsystems["server_side_pdf_export_controls"]["status"] == "PASS"

    assert len(report["permission_tiers"]) == 5
    assert report["test_verification_summary"]["total_security_tests"] >= 20
