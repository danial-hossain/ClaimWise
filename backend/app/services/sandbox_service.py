"""Local Mock Insurer Sandbox Gateway Service for ClaimWise.

Provides a safe, local-only simulated payer gateway for testing claim submissions,
EDI 837P / remittance advice simulation, and payer response handling.

MANDATORY SAFETY RULES:
- Never transmits claims or patient records to real insurance companies.
- Every simulated outcome is explicitly labelled as a simulation.
- Requires explicit user confirmation before executing any simulated submission.
- Enforces idempotency to prevent duplicate mock submissions.
"""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, Optional
import uuid

from app.models.domain import ClaimStatus
from app.schemas.claim import (
    ClaimRecord,
    LineItemDecisionStatus,
    SandboxOutcomeStatus,
    SandboxPayerOutcome,
    SandboxSubmitRequest,
)

logger = logging.getLogger("claimwise.sandbox_service")

MOCK_PAYER_NAME = "Apex National Insurance Payer (Simulated Sandbox Gateway)"
SANDBOX_DISCLAIMER = (
    "LOCAL SANDBOX SIMULATION ONLY: This is a purely educational mock simulation. "
    "No claim data, EDI 837 transactions, or FHIR resources were transmitted to any "
    "real health plan, clearinghouse, or insurance carrier. Real claims require formal insurer filing."
)


class MockInsurerSandboxService:
    """
    Simulated payer gateway managing mock adjudication and response codes.
    """

    def __init__(self):
        # Cache for idempotency keys: idempotency_key -> SandboxPayerOutcome
        self._idempotency_cache: Dict[str, SandboxPayerOutcome] = {}

    def simulate_submission(
        self,
        claim: ClaimRecord,
        request: SandboxSubmitRequest,
    ) -> SandboxPayerOutcome:
        """
        Process a user-confirmed simulated claim submission to the mock payer gateway.
        """
        if not request.user_confirmed:
            raise ValueError("Explicit user confirmation is mandatory before executing a sandbox simulation.")

        # Idempotency check: if key was already submitted, return the cached outcome
        if request.idempotency_key in self._idempotency_cache:
            logger.info("Returning cached mock outcome for idempotency key '%s'.", request.idempotency_key)
            return self._idempotency_cache[request.idempotency_key]

        submission_id = f"sub-{uuid.uuid4().hex[:12]}"
        simulated_claim_ref = f"SIM-APEX-2026-{uuid.uuid4().hex[:6].upper()}"
        simulated_batch_id = f"EDI837P-BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        scenario = (request.requested_scenario or "auto").lower()

        # Determine outcome scenario
        if scenario == "approve":
            outcome = self._scenario_approved(submission_id, claim, simulated_claim_ref, simulated_batch_id)
        elif scenario == "deny_exclusion":
            outcome = self._scenario_denied_exclusion(submission_id, claim, simulated_claim_ref, simulated_batch_id)
        elif scenario == "partial":
            outcome = self._scenario_partial(submission_id, claim, simulated_claim_ref, simulated_batch_id)
        elif scenario == "request_info":
            outcome = self._scenario_request_info(submission_id, claim, simulated_claim_ref, simulated_batch_id)
        elif scenario == "gateway_error":
            outcome = self._scenario_gateway_error(submission_id, claim, simulated_claim_ref, simulated_batch_id)
        else:
            # Auto-detect scenario based on claim's itemized adjudication
            outcome = self._auto_detect_scenario(submission_id, claim, simulated_claim_ref, simulated_batch_id)

        # Store in idempotency cache
        self._idempotency_cache[request.idempotency_key] = outcome
        return outcome

    def _auto_detect_scenario(
        self,
        submission_id: str,
        claim: ClaimRecord,
        claim_ref: str,
        batch_id: str,
    ) -> SandboxPayerOutcome:
        """Auto-derive realistic payer scenario from the claim's evidence evaluation."""
        if not claim.adjudicated_items:
            return self._scenario_request_info(submission_id, claim, claim_ref, batch_id)

        all_excluded = all(
            item.decision_status == LineItemDecisionStatus.POTENTIALLY_EXCLUDED
            for item in claim.adjudicated_items
        )
        if all_excluded:
            return self._scenario_denied_exclusion(submission_id, claim, claim_ref, batch_id)

        has_review = any(
            item.decision_status in (LineItemDecisionStatus.REQUIRES_REVIEW, LineItemDecisionStatus.INSUFFICIENT_EVIDENCE)
            for item in claim.adjudicated_items
        )
        if has_review:
            return self._scenario_request_info(submission_id, claim, claim_ref, batch_id)

        # Check if member has cost sharing
        if claim.eob and claim.eob.total_illustrative_member_cents > 0:
            return self._scenario_partial(submission_id, claim, claim_ref, batch_id)

        return self._scenario_approved(submission_id, claim, claim_ref, batch_id)

    def _scenario_approved(
        self,
        submission_id: str,
        claim: ClaimRecord,
        claim_ref: str,
        batch_id: str,
    ) -> SandboxPayerOutcome:
        paid_cents = claim.eob.total_illustrative_insurer_cents if claim.eob else claim.total_billed_cents
        patient_cents = claim.eob.total_illustrative_member_cents if claim.eob else 0

        return SandboxPayerOutcome(
            submission_id=submission_id,
            claim_id=claim.id,
            outcome_status=SandboxOutcomeStatus.APPROVED_SIMULATION,
            simulated_claim_reference=claim_ref,
            simulated_payer_name=MOCK_PAYER_NAME,
            simulated_remittance_code="REMIT-01: Claim Approved Pursuant to Standard In-Network Schedule",
            simulated_paid_amount_cents=paid_cents,
            simulated_patient_responsibility_cents=patient_cents,
            explanation_notes=(
                "All submitted line items were adjudicated as in-network covered benefits. "
                "Simulated payment issued to provider under electronic funds transfer EFT-SIM-8841."
            ),
            simulated_edi_batch_id=batch_id,
            timestamp=datetime.now(timezone.utc),
            is_simulation=True,
            disclaimer=SANDBOX_DISCLAIMER,
        )

    def _scenario_partial(
        self,
        submission_id: str,
        claim: ClaimRecord,
        claim_ref: str,
        batch_id: str,
    ) -> SandboxPayerOutcome:
        paid_cents = claim.eob.total_illustrative_insurer_cents if claim.eob else max(0, claim.total_billed_cents - 25000)
        patient_cents = claim.eob.total_illustrative_member_cents if claim.eob else 25000

        return SandboxPayerOutcome(
            submission_id=submission_id,
            claim_id=claim.id,
            outcome_status=SandboxOutcomeStatus.PARTIALLY_APPROVED_SIMULATION,
            simulated_claim_reference=claim_ref,
            simulated_payer_name=MOCK_PAYER_NAME,
            simulated_remittance_code="REMIT-02: Partial Payment Applied (Deductible/Coinsurance/Copay)",
            simulated_paid_amount_cents=paid_cents,
            simulated_patient_responsibility_cents=patient_cents,
            explanation_notes=(
                "Claim was approved with cost-sharing deductions applied according to the member's "
                "active deductible balance and coinsurance responsibility."
            ),
            simulated_edi_batch_id=batch_id,
            timestamp=datetime.now(timezone.utc),
            is_simulation=True,
            disclaimer=SANDBOX_DISCLAIMER,
        )

    def _scenario_denied_exclusion(
        self,
        submission_id: str,
        claim: ClaimRecord,
        claim_ref: str,
        batch_id: str,
    ) -> SandboxPayerOutcome:
        return SandboxPayerOutcome(
            submission_id=submission_id,
            claim_id=claim.id,
            outcome_status=SandboxOutcomeStatus.DENIED_EXCLUSION_SIMULATION,
            simulated_claim_reference=claim_ref,
            simulated_payer_name=MOCK_PAYER_NAME,
            simulated_remittance_code="DENIAL-EXCL-104: Non-Covered Policy Exclusion",
            simulated_paid_amount_cents=0,
            simulated_patient_responsibility_cents=claim.total_billed_cents,
            explanation_notes=(
                "Claim denied: The billed services are classified as non-covered under master contract "
                "exclusion guidelines. The member may file a formal administrative appeal within 180 days."
            ),
            simulated_edi_batch_id=batch_id,
            timestamp=datetime.now(timezone.utc),
            is_simulation=True,
            disclaimer=SANDBOX_DISCLAIMER,
        )

    def _scenario_request_info(
        self,
        submission_id: str,
        claim: ClaimRecord,
        claim_ref: str,
        batch_id: str,
    ) -> SandboxPayerOutcome:
        return SandboxPayerOutcome(
            submission_id=submission_id,
            claim_id=claim.id,
            outcome_status=SandboxOutcomeStatus.PENDING_ADDITIONAL_INFO,
            simulated_claim_reference=claim_ref,
            simulated_payer_name=MOCK_PAYER_NAME,
            simulated_remittance_code="PEND-REQ-25: Clinical Chart Notes & Prior-Auth Documentation Required",
            simulated_paid_amount_cents=0,
            simulated_patient_responsibility_cents=0,
            explanation_notes=(
                "Payer has pended the claim awaiting supporting clinical records, physician chart notes, "
                "or prior authorization confirmation from the treating facility."
            ),
            simulated_edi_batch_id=batch_id,
            timestamp=datetime.now(timezone.utc),
            is_simulation=True,
            disclaimer=SANDBOX_DISCLAIMER,
        )

    def _scenario_gateway_error(
        self,
        submission_id: str,
        claim: ClaimRecord,
        claim_ref: str,
        batch_id: str,
    ) -> SandboxPayerOutcome:
        return SandboxPayerOutcome(
            submission_id=submission_id,
            claim_id=claim.id,
            outcome_status=SandboxOutcomeStatus.SIMULATED_TRANSMISSION_ERROR,
            simulated_claim_reference=claim_ref,
            simulated_payer_name=MOCK_PAYER_NAME,
            simulated_remittance_code="ERR-EDI-504: Simulated Gateway Connection Timeout",
            simulated_paid_amount_cents=0,
            simulated_patient_responsibility_cents=0,
            explanation_notes=(
                "Simulated carrier clearinghouse timeout during electronic transaction batch processing. "
                "Retry with identical idempotency key or re-submit."
            ),
            simulated_edi_batch_id=batch_id,
            timestamp=datetime.now(timezone.utc),
            is_simulation=True,
            disclaimer=SANDBOX_DISCLAIMER,
        )


sandbox_service = MockInsurerSandboxService()
