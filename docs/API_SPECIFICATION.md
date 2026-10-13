# ClaimWise API Specification (v1)

## Base URL
- Local Development: `http://127.0.0.1:8000`
- API Prefix: `/api/v1`

---

## 1. System Endpoints

### GET `/`
Root metadata endpoint.
- **Response**: `200 OK`
```json
{
  "name": "ClaimWise API",
  "version": "0.1.0",
  "tagline": "Evidence first. If no proof, no answer.",
  "docs": "/docs",
  "health": "/api/v1/health",
  "ready": "/api/v1/ready",
  "environment": "development"
}
```

### GET `/api/v1/health`
Liveness probe.
- **Response**: `200 OK`

### GET `/api/v1/ready`
Readiness probe. Inspects database connectivity and status of optional external services.
- **Response**: `200 OK`

---

## 2. Policy Ingestion & Rules Endpoints

### POST `/api/v1/policies/upload`
Upload and extract page-level clauses and SHA-256 integrity hash from PDF document.
- **Request**: `multipart/form-data` with `file: UploadFile` (.pdf format, magic byte verified).
- **Response**: `201 Created` (`PolicyExtractionResult`)

### GET `/api/v1/policies`
List extracted policies available in active session.
- **Response**: `200 OK` (`List[PolicyExtractionResult]`)

### GET `/api/v1/policies/{policy_id}`
Retrieve extracted policy details and clauses.
- **Response**: `200 OK` (`PolicyExtractionResult`)

### POST `/api/v1/rules/calculate`
Deterministic cost-sharing calculation engine. Financial arithmetic calculated in integer cents.
- **Request**: `CostCalculationInput`
- **Response**: `200 OK` (`CostCalculationResult`)

---

## 3. Evidence-Grounded Q&A Endpoints

### POST `/api/v1/qa/ask`
Query an insurance policy with strict evidence grounding and post-generation citation validation.
- **Request**: `QARequest` (`policy_id`, `question`)
- **Response**: `200 OK` (`QAResponse`)

### GET `/api/v1/qa/status`
Retrieve operational status of the retrieval pipeline and Gemini synthesis engine.
- **Response**: `200 OK`

---

## 4. Claims, Adjudication & Mock Sandbox Endpoints

### POST `/api/v1/claims/upload-bill`
Upload medical bill PDF and extract itemized line items with CPT codes, charges, and page numbers.
- **Request**: `multipart/form-data` with `file: UploadFile` (.pdf)
- **Response**: `201 Created` (`BillExtractionResult`)

### POST `/api/v1/claims`
Create a new claim record associating a reviewed medical bill with a policy schedule.
- **Request**: `ClaimCreateFromBillRequest`
- **Response**: `201 Created` (`ClaimRecord`)

### GET `/api/v1/claims`
List claims in active session.
- **Response**: `200 OK` (`List[ClaimRecord]`)

### GET `/api/v1/claims/{claim_id}`
Retrieve detailed claim record.
- **Response**: `200 OK` (`ClaimRecord`)

### POST `/api/v1/claims/{claim_id}/adjudicate`
Run evidence-based adjudication comparing bill line items against policy terms.
- **Request**: `ClaimAdjudicateRequest`
- **Response**: `200 OK` (`ExplanationOfBenefits`)

### GET `/api/v1/claims/{claim_id}/eob`
Retrieve structured Explanation of Benefits (EOB).
- **Response**: `200 OK` (`ExplanationOfBenefits`)

### POST `/api/v1/claims/{claim_id}/sandbox-submit`
Simulate claim submission to local mock payer sandbox with mandatory user confirmation.
- **Request**: `SandboxSubmitRequest` (`user_confirmed: true`, `idempotency_key`, `requested_scenario`)
- **Response**: `200 OK` (`SandboxPayerOutcome`)

### GET `/api/v1/claims/{claim_id}/sandbox-status`
Retrieve mock sandbox remittance outcome.
- **Response**: `200 OK` (`SandboxPayerOutcome`)

---

## 5. Multi-Policy Comparison Engine (Milestone 5)

### POST `/api/v1/comparisons`
Generate side-by-side comparison across 2 to 4 authorized policies.
- **Request**: `ComparisonCreateRequest` (`policy_ids: List[str]` [2–4 items], `title`, `cost_assumptions`)
- **Response**: `201 Created` (`ComparisonRecord`)
- **Status Tracking**: Each policy attribute has transparent status: `verified`, `unknown`, `conflicting`, `not_applicable`.
- **Cost Simulation**: Integer-cents deterministic rules engine calculation. Distinguishes billed charges from allowed amounts. If allowed amount is unknown, calculation is marked illustrative/incomplete.

### GET `/api/v1/comparisons/{comparison_id}`
Retrieve saved comparison matrix and cost simulation.
- **Response**: `200 OK` (`ComparisonRecord`)

### POST `/api/v1/comparisons/{comparison_id}/simulate-cost`
Recalculate illustrative cost simulation under updated user assumptions.
- **Request**: `CostSimulationAssumption`
- **Response**: `200 OK` (`ComparisonCostSimulation`)

### GET `/api/v1/comparisons`
List all comparisons in active session.
- **Response**: `200 OK` (`List[ComparisonRecord]`)

---

## 6. Evidence-Based Denial Appeal Generator (Milestone 5)

### POST `/api/v1/claims/{claim_id}/appeal-draft`
Generate an evidence-grounded denial appeal draft for a claim.
- **Request**: `AppealDraftCreateRequest` (`denial_reason_code`, `user_provided_denial_notes`, `user_additional_facts`, `supporting_document_names`)
- **Response**: `201 Created` (`ClaimAppealDraft`)
- **Structure**: Statement of the issue, factual background, exact verified policy clauses, rebuttal narrative, evidence gap alerts, missing evidence checklist, requested action, and review disclaimer.
- **Security**: Treats user input and uploaded documents as untrusted plain text (defense against prompt injection). Never fabricates legal rights or deadlines.

### GET `/api/v1/claims/{claim_id}/appeal-draft`
Retrieve active appeal draft for a claim.
- **Response**: `200 OK` (`ClaimAppealDraft`)

### PUT `/api/v1/claims/{claim_id}/appeal-draft`
Update appeal draft with human user edits.
- **Request**: `AppealDraftUpdateRequest` (`statement_of_issue`, `factual_background`, `rebuttal_narrative`, `requested_action`)
- **Response**: `200 OK` (`ClaimAppealDraft` with `status: "user_edited"`)

### POST `/api/v1/claims/{claim_id}/appeal-draft/export`
Finalize and export reviewed appeal package for offline member filing.
- **Response**: `200 OK` (`AppealExportPackage`)
- **Guarantees**: Includes formatted markdown letter, citation index, evidence checklist, and mandatory human review disclaimer. Never transmits appeals to real insurers.

---

## 7. Server-Side PDF Export System (Milestone 6)

### GET `/api/v1/claims/{claim_id}/eob/pdf`
Generate and stream a professional, styled Explanation of Benefits (EOB) PDF in A4 format.
- **Authorization**: Caller must own the target claim.
- **Headers**: `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="ClaimWise_EOB_{claim_id}.pdf"`
- **Content**: Itemized line-by-line charges, allowed amounts (or explicit "Pending" status if unknown), deductible, copay, coinsurance breakdown, total member responsibility, illustrative insurer share, mathematical audit reconciliation, verified policy citations, and educational simulation disclaimer.
- **Engine**: In-memory generation via PyMuPDF with zero temporary files left on disk.

### GET `/api/v1/claims/{claim_id}/appeal-draft/pdf`
Generate and stream a formal denial appeal package PDF.
- **State Enforcement**: The appeal draft MUST be in reviewed status (`user_edited` or `exported`). Requests for unreviewed drafts return `400 Bad Request`.
- **Authorization**: Caller must own the target claim.
- **Headers**: `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="ClaimWise_Appeal_{claim_id}.pdf"`
- **Content**: Claim and denial metadata, statement of issue, factual background, rebuttal narrative, user-requested relief, verified citations, evidence submission checklist, and legal review disclaimer.

### GET `/api/v1/comparisons/{comparison_id}/pdf`
Generate and stream a multi-policy side-by-side comparison report PDF.
- **Authorization**: Caller must own the target comparison.
- **Headers**: `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="ClaimWise_Comparison_{comparison_id}.pdf"`
- **Content**: Evaluated policies with SHA-256 hashes, side-by-side coverage terms matrix with explicit evidence statuses, illustrative cost modeling estimates, and comparative trade-off summary.

---

## 8. Cryptographic Audit Trail & Security (Milestone 6)

### GET `/api/v1/audit/events`
Query authorized immutable audit events.
- **Authorization**: Returns only audit records where `user_id` matches the authenticated caller (tenant isolation enforced).
- **Query Params**: `action` (string), `resource_type` (string), `limit` (int, 1-500, default 50), `offset` (int).
- **Response**: `200 OK` (`List[AuditEvent]`)

### POST `/api/v1/audit/verify`
Cryptographically verify the integrity of the audit hash chain.
- **Authorization**: Scoped to the caller's audit event sequence.
- **Response**: `200 OK` (`AuditVerificationResult`)
  - `is_valid: bool`: True if every SHA-256 hash and previous_hash link is mathematically sound.
  - `total_events: int`: Total events checked.
  - `verified_count: int`: Number of verified contiguous events.
  - `chain_head_hash: str`: Cryptographic root hash of the chain.
  - `tampered_event_id: Optional[str]`: ID of first tampered event if verification failed.
  - `error_reason: Optional[str]`: Failure diagnostic if tampering or sequence gap detected.

