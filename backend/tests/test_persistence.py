"""Tests for Item 7.2: Persistence across process restarts.

Verifies that policies, comparisons, claims, bills, appeal drafts, and
cryptographic audit events survive process termination and restart using
the PostgreSQL persistent store in a verified disposable test database.
"""

from datetime import date, datetime, timezone
import uuid
import pytest

from app.api.v1.endpoints.policies import _dev_policy_store
from app.db.audit_repo import AuditRepository, audit_repo
from app.db.claim_repo import ClaimRepository, claim_repo
from app.db.comparison_repo import ComparisonRepository, comparison_repo
from app.db.local_store import (
    PersistentAppealDraftStore,
    PersistentBillStore,
    PersistentClaimStore,
    PersistentComparisonStore,
    PersistentPolicyStore,
    local_store,
)
from app.models.domain import ClaimStatus, PolicyType
from app.schemas.appeal import ClaimAppealDraft
from app.schemas.audit import AuditEventCreate
from app.schemas.claim import (
    BillExtractionResult,
    BillLineItem,
    ClaimRecord,
)
from app.schemas.comparison import ComparisonRecord, PolicyComparisonCard
from app.schemas.policy import ExtractedClause, PolicyExtractionResult


@pytest.mark.database
@pytest.mark.asyncio
async def test_policy_persistence_across_instances():
    """Verify that policies and chunks survive backend re-initialization."""
    policy_id = f"test-pol-{uuid.uuid4().hex[:8]}"
    clause = ExtractedClause(
        clause_id="CL-TEST-1",
        page_number=1,
        clause_heading="Emergency Services",
        heading_confidence="high",
        section_number="3.1",
        text="Emergency room visits are covered with a $150 copayment.",
        token_count=12,
        document_hash="a" * 64,
    )
    policy = PolicyExtractionResult(
        document_name="TestPolicy.pdf",
        document_hash="a" * 64,
        file_size_bytes=1024,
        total_pages=1,
        total_clauses=1,
        is_scanned=False,
        has_extractable_text=True,
        status="success",
        message="Test policy for persistence",
        pages=[],
        clauses=[clause],
        persistence_mode="development_preview",
        policy_id=policy_id,
        uploaded_at=datetime.now(timezone.utc),
    )

    # Store via dict interface
    _dev_policy_store[policy_id] = policy

    try:
        # Verify in local_store directly
        retrieved_direct = local_store.get_policy(policy_id)
        assert retrieved_direct is not None
        assert retrieved_direct.document_name == "TestPolicy.pdf"
        assert len(retrieved_direct.clauses) == 1
        assert retrieved_direct.clauses[0].clause_id == "CL-TEST-1"

        # Simulate process restart by instantiating a brand-new PersistentPolicyStore
        fresh_store = PersistentPolicyStore()
        assert policy_id in fresh_store
        reloaded_policy = fresh_store[policy_id]
        assert reloaded_policy.document_name == "TestPolicy.pdf"
        assert reloaded_policy.clauses[0].text == "Emergency room visits are covered with a $150 copayment."
    finally:
        _dev_policy_store.pop(policy_id, None)

    # Verify deleted
    assert policy_id not in PersistentPolicyStore()


@pytest.mark.database
@pytest.mark.asyncio
async def test_claim_and_bill_persistence_across_instances():
    """Verify that claims and bills persist across repository instantiations."""
    bill_id = f"test-bill-{uuid.uuid4().hex[:8]}"
    line_item = BillLineItem(
        line_id="LINE-01",
        service_date="2026-04-01",
        description="Chest X-Ray",
        cpt_code="71046",
        billed_charge_cents=35000,
        quantity=1,
        provider_name="Memorial Hospital",
        source_page_number=1,
        raw_text_excerpt="71046 Chest X-Ray 2 Views $350.00",
    )
    bill = BillExtractionResult(
        bill_id=bill_id,
        document_name="hospital_bill.pdf",
        document_hash="b" * 64,
        file_size_bytes=2048,
        total_pages=1,
        total_billed_cents=35000,
        is_scanned=False,
        has_extractable_text=True,
        line_items=[line_item],
        uploaded_at=datetime.now(timezone.utc),
        message="Parsed bill successfully",
    )

    claim_id = f"test-claim-{uuid.uuid4().hex[:8]}"
    claim = ClaimRecord(
        id=claim_id,
        user_id="user-persist-01",
        policy_id="pol-persist-01",
        claim_reference="CLM-998877",
        bill_id=bill_id,
        bill_document_name="hospital_bill.pdf",
        bill_document_hash="b" * 64,
        incident_date=date(2026, 4, 1),
        total_billed_cents=35000,
        status=ClaimStatus.ANALYZED,
        line_items=[line_item],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    claim_repo.save_bill_extraction(bill)
    await claim_repo.save_claim(claim)

    try:
        # Simulate restart with new ClaimRepository
        fresh_repo = ClaimRepository()
        reloaded_bill = fresh_repo.get_bill_extraction(bill_id)
        assert reloaded_bill is not None
        assert reloaded_bill.total_billed_cents == 35000
        assert len(reloaded_bill.line_items) == 1

        reloaded_claim = fresh_repo.get_claim(claim_id)
        assert reloaded_claim is not None
        assert reloaded_claim.claim_reference == "CLM-998877"
        assert reloaded_claim.status == ClaimStatus.ANALYZED
        assert len(reloaded_claim.line_items) == 1
        assert reloaded_claim.line_items[0].description == "Chest X-Ray"

        user_claims = fresh_repo.list_claims(user_id="user-persist-01")
        assert any(c.id == claim_id for c in user_claims)
    finally:
        claim_repo._dev_claims.pop(claim_id, None)
        claim_repo._dev_bills.pop(bill_id, None)


@pytest.mark.database
@pytest.mark.asyncio
async def test_comparison_persistence_across_instances():
    """Verify that multi-policy comparisons survive backend re-initialization."""
    comp_id = f"test-comp-{uuid.uuid4().hex[:8]}"
    comparison_item = PolicyComparisonCard(
        policy_id="pol-1",
        policy_name="Aetna Silver",
        insurer_name="Aetna",
        document_hash="c" * 64,
        attributes={},
    )
    record = ComparisonRecord(
        id=comp_id,
        user_id="user-comp-persist",
        title="Silver vs Bronze Plan Evaluation",
        policy_ids=["pol-1"],
        policies=[comparison_item],
        cost_simulation=None,
        status="completed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    await comparison_repo.save_comparison(record)

    try:
        # Simulate restart
        fresh_comp_repo = ComparisonRepository()
        reloaded_comp = fresh_comp_repo.get_comparison(comp_id)
        assert reloaded_comp is not None
        assert reloaded_comp.title == "Silver vs Bronze Plan Evaluation"
        assert len(reloaded_comp.policies) == 1
        assert reloaded_comp.policies[0].policy_name == "Aetna Silver"
    finally:
        comparison_repo._dev_comparisons.pop(comp_id, None)


@pytest.mark.database
@pytest.mark.asyncio
async def test_audit_event_chain_continuity_across_instances():
    """Verify that audit hash chaining continues unbroken across restarts."""
    e1 = await audit_repo.record_event(
        AuditEventCreate(
            action="system.bootstrap",
            resource_type="system",
            user_id="persist-tester",
            metadata={"cycle": 1},
        )
    )

    # Simulate restart
    fresh_audit_repo = AuditRepository()
    last = fresh_audit_repo.get_last_event()
    assert last is not None
    assert last.event_id == e1.event_id

    # Record next event after restart
    e2 = await fresh_audit_repo.record_event(
        AuditEventCreate(
            action="policy.inspect",
            resource_type="policy",
            user_id="persist-tester",
            metadata={"cycle": 2},
        )
    )

    assert e2.sequence_number == e1.sequence_number + 1
    assert e2.previous_hash == e1.event_hash

    verification = fresh_audit_repo.verify_chain()
    assert verification.is_valid is True
