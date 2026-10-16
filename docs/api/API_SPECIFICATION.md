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

### GET `/api/v1/qa/benchmark`
Execute or retrieve systematic 40-question benchmark report (25 answerable, 15 honest abstentions).
- **Query Params**:
  - `live: bool` (default `false`): If `true`, invokes Google Gemini LLM API; if `false`, executes deterministic offline verification against ground-truth.
  - `max_questions: Optional[int]`: Optional question count limit for rapid subset benchmarking.
- **Response**: `200 OK` (`BenchmarkExecutionReport`)
  - `summary`: `BenchmarkRunSummary` (Decision Accuracy %, Groundedness %, Citation Accuracy %, Honest Abstention %, Hallucination %, Adversarial Defense %, Retrieval Recall %, Latency).
  - `results`: `List[QuestionEvaluationResult]` (Question ID, category, decision, citations, top retrieval hits, and verbatim quotes).

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

### GET `/api/v1/claims/guidance/questions`
Retrieve the interactive incident intake questionnaire schema, fields, options, and starter preset templates.
- **Response**: `200 OK` (`IncidentQuestionnaireSchema`)
  - Fields: Care setting (`incident_category`), service date (`incident_date`), network affiliation (`network_status`), prior authorization (`prior_auth_status`), third-party liability (`liability_type`), documentation checklist, user clinical notes.
  - Presets: ER visit, Inpatient surgery, MRI imaging, Auto accident trauma.

### POST `/api/v1/claims/guidance/evaluate`
Evaluate user incident questionnaire against policy clauses and generate an evidence-grounded claims guidance plan.
- **Request**: `IncidentQuestionnaireRequest`
- **Response**: `200 OK` (`IncidentGuidanceResult`)
  - `readiness_score_pct`: Claim readiness percentage (0–100%).
  - `risk_level`: `low_risk` | `medium_risk` | `high_risk`.
  - `timely_filing`: `TimelyFilingAnalysis` evaluating elapsed days against contractual filing deadline (Clause 8.1 / 90 days), with citation and deadline countdown.
  - `document_checklist`: Dynamic required/recommended document list tailored to the incident category.
  - `obstacles`: Identified contractual hurdles (missing inpatient pre-auth, workers' comp exclusion, out-of-network balance billing) with mitigation strategies and citations.
  - `action_plan_steps`: Numbered priority steps before filing.
  - `provider_inquiries`: Questions to ask the hospital billing office.

### GET `/api/v1/claims/{claim_id}/guidance`
Generate evidence-grounded claims guidance for an existing claim record.
- **Response**: `200 OK` (`IncidentGuidanceResult`)


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

---

## 9. Coverage-Gap Analysis Engine (F2)

### GET `/api/v1/coverage/presets`
Retrieve standard clinical care preset scenarios for gap analysis.
- **Response**: `200 OK` (`List[PresetScenarioItem]`)
  - Standard presets: Emergency Room Care, Outpatient MRI Scan, Elective Inpatient Surgery, Specialty Biologic Medication, Cosmetic Rhinoplasty, Adult Routine Dental Cleaning, Physical Therapy (20 visits), Mental Health Outpatient Counseling.

### POST `/api/v1/coverage/analyze`
Analyze an individual medical care need or situation against contractual policy terms.
- **Request**: `CoverageScenarioRequest` (`policy_id: str`, `situation: str`, `category?: Optional[str]`, `description?: Optional[str]`)
- **Response**: `200 OK` (`CoverageGapAnalysisResult`)
  - `verdict`: `covered` | `conditional` | `excluded` | `uncertain`
  - `explanation`: Fact-grounded summary of contractual terms.
  - `conditions_summary`: Precertification or referral requirements if conditional.
  - `cost_sharing_summary`: Copayment, coinsurance, or deductible terms.
  - `prior_auth_required`: Boolean flag.
  - `clauses`: List of `VerifiedCitation` objects with exact verbatim quotes and page numbers.
  - `insurer_questions`: 1–3 concrete, high-leverage clarifying questions to ask the insurer before receiving care.
  - `confidence_score`: Float between 0.0 and 1.0.
- **Guarantees**:
  - **Zero Hallucination**: Silent/unstated terms return `uncertain` with insurer questions; never fabricates terms.
  - **Prompt Injection Defense**: Situation text is treated strictly as untrusted plain data; system prompt instructions cannot be overridden.
  - **Verbatim Citations**: Quotes are cross-verified against actual policy text via `validate_citations`.

### GET `/api/v1/coverage/report/{policy_id}`
Generate a complete multi-scenario coverage gap audit report for a policy.
- **Path Param**: `policy_id` (Auto-hydrates test policies if queried without prior upload).
- **Response**: `200 OK` (`CoverageGapReportResponse`)
  - `coverage_score_pct`: Overall in-network coverage percentage based on evaluated scenarios.
  - `covered_count`, `conditional_count`, `excluded_count`, `uncertain_count`: Verdict category counts.
  - `scenarios`: Complete list of evaluated `CoverageGapAnalysisResult` items.

---

## 10. Interactive Incident Questioning & Claims Guidance (F3)

### GET `/api/v1/claims/guidance/questions`
Retrieve the interactive incident intake questionnaire schema and preset incident scenario templates.
- **Response**: `200 OK` (`IncidentQuestionnaireSchema`)
  - `fields`: Dynamic questionnaire fields (`incident_category`, `incident_date`, `network_status`, `prior_auth_status`, `liability_type`, `has_itemized_bill`, `has_medical_records`, `has_receipt_of_payment`, `user_notes`).
  - `presets`: Standard preset templates (`Emergency Room Visit`, `Elective Inpatient Surgery`, `Motor Vehicle Collision / Third-Party`, `Specialty Rx Out-of-Network`).

### POST `/api/v1/claims/guidance/evaluate`
Evaluate member incident intake answers against contractual policy rules, providing real-time readiness scoring, timely filing deadlines, obstacle mitigations, and provider inquiry scripts.
- **Request**: `IncidentQuestionnaireRequest`
- **Response**: `200 OK` (`IncidentGuidanceResult`)
  - `readiness_score_pct`: Claim readiness metric (0–100%).
  - `risk_level`: `low` | `medium` | `high` | `critical`.
  - `timely_filing`: `TimelyFilingAnalysis` (days elapsed, timely filing limit, days remaining, deadline date, verbatim policy citation).
  - `document_checklist`: Mandatory and recommended documentation checklist with status badges.
  - `obstacles`: Contractual obstacles detected (e.g. Inpatient Prior Auth, Specialty Rx Step Therapy, Workers' Comp Exclusion, Out-of-Network Balance Billing) with actionable mitigation strategies.
  - `provider_inquiries`: Tailored questions to ask doctors and billing departments.
  - `verified_citations`: Verbatim contract citations grounding the evaluation.

### GET `/api/v1/claims/{claim_id}/guidance`
Retrieve or generate dynamic policy guidance for an existing claim record.
- **Response**: `200 OK` (`IncidentGuidanceResult`)

---

## 11. Aggregate Portfolio Management & COB Optimizer (F4)

### POST `/api/v1/portfolio/analyze`
Evaluate an aggregate portfolio of 2 to 4 health insurance policies held simultaneously.
- **Request**: `PortfolioAnalysisRequest`
  - `policy_ids`: List of 2 to 4 policy IDs.
  - `subscribers`: Optional list of `SubscriberProfile` items (policyholder, spouse, dependent child; active, COBRA, retired; birthday MM-DD; effective date).
  - `patient_relationship`: Context of claimant (`policyholder`, `dependent_spouse`, `dependent_child`).
- **Response**: `200 OK` (`PortfolioAnalysisResult`)
  - `scorecard`: Executive health scorecard:
    - `protection_score_percent`: Breadth of coverage across core clinical domains (0–100%).
    - `redundancy_index_percent`: Proportion of duplicated benefits indicating duplicate premium overhead (0–100%).
    - `total_policies`: Count of analyzed policies.
    - `total_overlaps_detected`: Overlapping benefit count.
    - `total_aggregate_gaps_detected`: Uninsurable collective gaps count.
    - `aggregate_in_network_deductible_cents`: Best in-network deductible in the portfolio.
    - `aggregate_in_network_oop_max_cents`: Best out-of-pocket maximum ceiling.
  - `cob_guidance`: Coordination of Benefits priority and filing protocol:
    - `primary_policy_id` / `primary_policy_name`: Designated Primary Payer.
    - `secondary_policy_id` / `secondary_policy_name`: Designated Secondary Payer.
    - `rule_applied`: NAIC rule applied (`subscriber_employee_rule`, `birthday_rule`, `active_vs_inactive_rule`, `longer_vs_shorter_rule`).
    - `determination_reason`: Verbatim statutory priority explanation.
    - `step_by_step_filing_guide`: 5-step claim submission protocol.
    - `non_duplication_clause_alert`: Warning on secondary carve-out / non-duplication provisions.
    - `financial_benefit_estimate`: Estimated savings from dual coverage coordination.
  - `overlaps`: `List[CoverageOverlapItem]` (Benefit category, redundancy degree, dual policy cost-sharing snapshots, prior auth mandates, coordination strategy, citations).
  - `aggregate_gaps`: `List[AggregateGapItem]` (Collective gaps uncovered by all held policies: Adult Routine Dental, Vision Hardware, Long-Term Custodial Care, Acupuncture, Cosmetic Surgery, Ambulance; severity, financial exposure analysis, recommended mitigations, citations).
  - `key_takeaways`: Executive bullet points synthesizing strengths and vulnerabilities.
  - `non_guarantee_disclaimer`: Mandatory non-guarantee legal advisory notice.

### GET `/api/v1/portfolio/sample`
Retrieve pre-configured aggregate analysis for Sample Policy A and Policy B with default dual-subscriber profiles.
- **Query Params**: `patient_relationship` (optional, default `"policyholder"`).
- **Response**: `200 OK` (`PortfolioAnalysisResult`)

### GET `/api/v1/portfolio/rules`
Retrieve statutory NAIC Model Regulation #120 Coordination of Benefits rules and priority hierarchy reference.
- **Response**: `200 OK` (JSON reference object detailing rule names, priorities, definitions, and non-duplication mechanics).

---

## 12. Security, PII Masking & Permission Tiers (0–4)

### POST `/api/v1/security/mask-pii`
Detect and sanitize Personally Identifiable Information (PII) and Protected Health Information (PHI).
- **Request**: `PIIMaskRequest` (`text: str`, `preserve_last_4: bool = true`, `categories?: Optional[List[PIICategory]]`)
- **Response**: `200 OK` (`PIIMaskResult`)
  - `original_char_count`: Input text character count.
  - `masked_text`: Sanitized text with redacted/tokenized identifiers.
  - `pii_detected_count`: Number of PII entities detected and redacted.
  - `categories_detected`: List of identified categories (`ssn`, `member_id`, `date_of_birth`, `phone_number`, `email_address`, `credit_card`, `npi_provider_id`, `patient_name`).
  - `detections`: Granular item details (`start_pos`, `end_pos`, `masked_value`, `confidence`).

### GET `/api/v1/security/permission-tiers`
Retrieve canonical specifications of the formal 5-Tier Permission Security Model.
- **Response**: `200 OK` (`List[PermissionTierDetail]`)
  - Specifications for Tiers 0 through 4:
    - `tier`: Integer 0 to 4.
    - `name` / `title` / `description`: Operational boundary definitions.
    - `allowed_actions`: Permitted operations in this tier.
    - `prohibited_actions`: Blocked/denied operations.
    - `requires_human_confirmation`: Boolean flag mandating human review.

### GET `/api/v1/security/self-assessment`
Retrieve the comprehensive, programmatic Security & Compliance Self-Assessment Report.
- **Response**: `200 OK` (`SecuritySelfAssessmentReport`)
  - `overall_compliance_score_pct`: `100.0`.
  - `frameworks_evaluated`: HIPAA (45 CFR § 164), SOC 2 Type II, OWASP Top 10 for LLMs (2025), NIST SP 800-53 Rev. 5, NAIC Model #120.
  - `subsystem_evaluations`: Detailed evaluation matrices for Hash-Chain, Prompt Injection, PII Masking, Permission Tiers, Tenant Isolation, and PDF Export Controls.
  - `test_verification_summary`: 22 passed automated security tests across test modules.
  - `compliance_officer_statement`: Executive assertion of zero live transmission and defense-in-depth data safety.


