from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import claims
from app.core.security import AuthenticatedUser
from app.models.domain import ClaimStatus
from app.schemas.claim import ClaimRecord, SandboxOutcomeStatus, SandboxSubmitRequest


def make_claim(status: ClaimStatus) -> ClaimRecord:
    now = datetime.now(timezone.utc)
    return ClaimRecord(
        id="draft-sandbox-claim",
        user_id="member-1",
        policy_id="policy-1",
        incident_date=date(2026, 10, 1),
        total_billed_cents=0,
        status=status,
        claim_type="Travel claim",
        incident_description="A checked bag was delayed during the trip.",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_preparing_claim_can_be_confirmed_for_sandbox_and_requests_information(monkeypatch):
    claim = make_claim(ClaimStatus.PREPARING_DOCUMENTS)
    saved = []
    audited = []

    monkeypatch.setattr(claims.claim_repo, "get_claim", lambda claim_id: claim)

    async def save_claim(value):
        saved.append(value)

    async def record_event(event):
        audited.append(event)

    monkeypatch.setattr(claims.claim_repo, "save_claim", save_claim)
    monkeypatch.setattr(claims.audit_repo, "record_event", record_event)

    result = await claims.submit_claim_to_sandbox(
        claim.id,
        SandboxSubmitRequest(user_confirmed=True, idempotency_key="draft-sandbox-1"),
        AuthenticatedUser(id="member-1", email="member@example.test", role="authenticated", tier=1),
    )

    assert result.outcome_status == SandboxOutcomeStatus.PENDING_ADDITIONAL_INFO
    assert result.is_simulation
    assert claim.status == ClaimStatus.SANDBOX_SUBMITTED
    assert saved == [claim]
    assert len(audited) == 1


@pytest.mark.asyncio
async def test_terminal_claim_cannot_be_submitted_to_sandbox(monkeypatch):
    claim = make_claim(ClaimStatus.CLOSED)
    monkeypatch.setattr(claims.claim_repo, "get_claim", lambda claim_id: claim)

    with pytest.raises(HTTPException) as error:
        await claims.submit_claim_to_sandbox(
            claim.id,
            SandboxSubmitRequest(user_confirmed=True, idempotency_key="closed-sandbox-1"),
            AuthenticatedUser(id="member-1", email="member@example.test", role="authenticated", tier=1),
        )

    assert error.value.status_code == 400
    assert "cannot be submitted" in error.value.detail
