export interface HealthResponse {
  status: string;
  app_name: string;
  environment: string;
  version: string;
  timestamp: string;
}

export interface ServiceComponentStatus {
  status: 'healthy' | 'configured' | 'unconfigured' | 'unreachable' | 'degraded' | 'staged_for_milestone_2';
  configured: boolean;
  required: boolean;
  message: string;
  details?: Record<string, string> | null;
}

export interface ReadinessResponse {
  ready: boolean;
  status: 'operational' | 'partial' | 'unready';
  app_name: string;
  environment: string;
  version: string;
  services: Record<string, ServiceComponentStatus>;
  unconfigured_optional_services: string[];
  timestamp: string;
}

export interface ConnectivityState {
  isChecking: boolean;
  isOnline: boolean | null;
  latencyMs: number | null;
  lastChecked: Date | null;
  health: HealthResponse | null;
  readiness: ReadinessResponse | null;
  error: string | null;
}

export interface ExtractedClause {
  clause_id: string;
  page_number: number;
  clause_heading: string | null;
  heading_confidence: 'high' | 'heuristic' | 'uncertain' | 'none';
  section_number: string | null;
  text: string;
  token_count: number;
  document_hash: string;
}

export interface PageSummary {
  page_number: number;
  clause_count: number;
  char_count: number;
  has_images: boolean;
  sample_heading: string | null;
}

export interface PolicyExtractionResult {
  document_name: string;
  document_hash: string;
  file_size_bytes: number;
  total_pages: number;
  total_clauses: number;
  is_scanned: boolean;
  has_extractable_text: boolean;
  status: string;
  message: string;
  pages: PageSummary[];
  clauses: ExtractedClause[];
  persistence_mode: string;
  policy_id: string | null;
  uploaded_at: string;
}

export interface CostCalculationInput {
  eligible_expense_cents: number;
  remaining_deductible_cents: number;
  member_coinsurance_percentage: number;
  remaining_out_of_pocket_max_cents: number;
  policy_coverage_limit_cents?: number | null;
  deductible_counts_towards_oop?: boolean;
}

export interface CostCalculationResult {
  eligible_expense_cents: number;
  member_total_cents: number;
  insurer_total_cents: number;
  deductible_paid_cents: number;
  member_coinsurance_cents: number;
  insurer_coinsurance_cents: number;
  uncovered_exceeding_limit_cents: number;
  new_remaining_deductible_cents: number;
  new_remaining_out_of_pocket_max_cents: number;
  new_remaining_coverage_limit_cents: number | null;
  oop_max_reached: boolean;
  deductible_met: boolean;
  calculation_steps: string[];
  disclaimer: string;
  display_summary: Record<string, string>;
}

export interface RetrievedEvidenceClause {
  clause_id: string;
  page_number: number;
  policy_id: string;
  document_hash: string;
  clause_heading: string | null;
  text: string;
  lexical_rank?: number | null;
  dense_rank?: number | null;
  fused_rank?: number | null;
  rrf_score?: number | null;
}

export interface VerifiedCitation {
  clause_id: string;
  page_number: number;
  exact_quote: string;
  policy_id: string;
  clause_heading?: string | null;
  verified: boolean;
}

export interface QARequest {
  question: string;
  policy_id?: string | null;
  policy_ids?: string[] | null;
  top_k?: number;
}

export interface QAResponse {
  question: string;
  answer: string;
  evidence_sufficient: boolean;
  abstention_reason: string | null;
  clarification_question: string | null;
  citations: VerifiedCitation[];
  retrieval_mode: string;
  retrieved_evidence: RetrievedEvidenceClause[];
  model_used: string;
  latency_ms: number;
  created_at: string;
}

export interface QAPipelineStatus {
  gemini_engine: {
    configured: boolean;
    model_name: string;
    status: string;
  };
  dense_embeddings: {
    provider: string;
    dimensions: number;
    status: string;
    blocker_reason?: string | null;
    disk_ram_requirement?: string;
  };
  bm25_lexical: {
    indexed_policies_count: number;
    indexed_clauses_count: number;
    status: string;
  };
  hybrid_fusion: {
    algorithm: string;
    rrf_k: number;
    status: string;
  };
  timestamp: string;
}

export interface BillLineItem {
  line_id: string;
  service_date: string | null;
  description: string;
  cpt_code: string | null;
  billed_charge_cents: number;
  quantity: number;
  provider_name: string | null;
  source_page_number: number;
  raw_text_excerpt: string;
  is_ambiguous: boolean;
  ambiguity_notes?: string | null;
}

export interface BillExtractionResult {
  bill_id: string;
  document_name: string;
  document_hash: string;
  file_size_bytes: number;
  total_pages: number;
  total_billed_cents: number;
  is_scanned: boolean;
  has_extractable_text: boolean;
  line_items: BillLineItem[];
  uploaded_at: string;
  message: string;
  persistence_mode: string;
}

export interface AdjudicatedLineItem {
  line_id: string;
  service_date: string | null;
  description: string;
  cpt_code: string | null;
  billed_charge_cents: number;
  allowed_amount_cents: number | null;
  potentially_covered_cents: number;
  deductible_applied_cents: number;
  copay_cents: number;
  member_coinsurance_cents: number;
  uncovered_amount_cents: number;
  uncovered_reason: string | null;
  illustrative_member_cents: number;
  illustrative_insurer_cents: number;
  decision_status: 'potentially_covered' | 'potentially_excluded' | 'requires_review' | 'insufficient_evidence' | 'not_evaluated';
  decision_rationale: string;
  evidence_citations: VerifiedCitation[];
  assumptions_and_missing_facts: string[];
  requires_manual_review: boolean;
}

export interface ExplanationOfBenefits {
  eob_id: string;
  claim_id: string;
  policy_id: string;
  policy_name?: string | null;
  bill_document_hash: string;
  policy_document_hash?: string | null;
  created_at: string;
  simulation_disclaimer: string;
  total_billed_cents: number;
  total_allowed_cents?: number | null;
  total_deductible_applied_cents: number;
  total_copay_cents: number;
  total_member_coinsurance_cents: number;
  total_uncovered_cents: number;
  total_illustrative_member_cents: number;
  total_illustrative_insurer_cents: number;
  items: AdjudicatedLineItem[];
  calculation_audit_steps: string[];
}

export interface ClaimRecord {
  id: string;
  user_id: string;
  policy_id: string;
  claim_reference?: string | null;
  bill_id: string;
  bill_document_name: string;
  bill_document_hash: string;
  incident_date: string;
  total_billed_cents: number;
  status: string;
  line_items: BillLineItem[];
  adjudicated_items: AdjudicatedLineItem[];
  eob?: ExplanationOfBenefits | null;
  sandbox_submission?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface SandboxPayerOutcome {
  submission_id: string;
  claim_id: string;
  outcome_status: string;
  simulated_claim_reference: string;
  simulated_payer_name: string;
  simulated_remittance_code: string;
  simulated_paid_amount_cents: number;
  simulated_patient_responsibility_cents: number;
  explanation_notes: string;
  simulated_edi_batch_id: string;
  timestamp: string;
  is_simulation: boolean;
  disclaimer: string;
}

// ==============================================================================
// MULTI-POLICY COMPARISON TYPES (MILESTONE 5)
// ==============================================================================

export type AttributeStatus = 'verified' | 'unknown' | 'conflicting' | 'not_applicable';

export interface PolicyAttributeEvidence {
  attribute_name: string;
  display_name: string;
  raw_value: string | null;
  numeric_value_cents: number | null;
  status: AttributeStatus;
  citations: VerifiedCitation[];
  notes?: string | null;
}

export interface PolicyComparisonCard {
  policy_id: string;
  policy_name: string;
  insurer_name: string;
  document_hash: string;
  attributes: Record<string, PolicyAttributeEvidence>;
}

export interface CostSimulationAssumption {
  service_type: string;
  billed_charges_cents: number;
  allowed_amount_cents?: number | null;
  is_allowed_amount_known: boolean;
  network_status?: string;
  prior_deductible_paid_cents?: number;
  prior_oop_paid_cents?: number;
}

export interface PolicyCostEstimate {
  policy_id: string;
  policy_name: string;
  is_complete: boolean;
  member_responsibility_cents: number | null;
  insurer_responsibility_cents: number | null;
  deductible_portion_cents?: number | null;
  coinsurance_portion_cents?: number | null;
  copay_portion_cents?: number | null;
  calculation_audit: string[];
  caveats_and_assumptions: string[];
}

export interface ComparisonCostSimulation {
  assumptions: CostSimulationAssumption;
  policy_estimates: PolicyCostEstimate[];
  comparative_analysis: string[];
  disclaimer: string;
}

export interface ComparisonCreateRequest {
  policy_ids: string[];
  title?: string;
  cost_assumptions?: CostSimulationAssumption | null;
}

export interface ComparisonRecord {
  id: string;
  user_id: string;
  title: string;
  policy_ids: string[];
  policies: PolicyComparisonCard[];
  cost_simulation?: ComparisonCostSimulation | null;
  tradeoff_summary: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

// ==============================================================================
// EVIDENCE-BASED DENIAL APPEAL TYPES (MILESTONE 5)
// ==============================================================================

export type AppealStatus = 'generated' | 'user_edited' | 'exported';

export interface AppealChecklistItem {
  item_name: string;
  description: string;
  is_available: boolean;
  source: 'claim_record' | 'user_uploaded' | 'missing_action_required';
}

export interface AppealDraftCreateRequest {
  denial_reason_code?: string | null;
  user_provided_denial_notes?: string | null;
  user_additional_facts?: string | null;
  supporting_document_names?: string[];
}

export interface AppealDraftUpdateRequest {
  statement_of_issue?: string | null;
  factual_background?: string | null;
  rebuttal_narrative?: string | null;
  requested_action?: string | null;
}

export interface ClaimAppealDraft {
  draft_id: string;
  claim_id: string;
  policy_id: string;
  policy_title: string;
  insurer_name: string;
  claim_reference: string;
  incident_date: string;
  denial_reason_code: string;
  denial_source: string;
  statement_of_issue: string;
  factual_background: string;
  policy_clauses_cited: VerifiedCitation[];
  rebuttal_narrative: string;
  evidence_gaps_identified: string[];
  missing_documents_checklist: AppealChecklistItem[];
  requested_action: string;
  status: AppealStatus;
  disclaimer: string;
  is_editable: boolean;
  created_at: string;
  updated_at: string;
}

export interface AppealExportPackage {
  export_id: string;
  draft_id: string;
  claim_id: string;
  formatted_markdown_letter: string;
  citation_index: VerifiedCitation[];
  evidence_checklist: AppealChecklistItem[];
  mandatory_disclaimer: string;
  exported_at: string;
}

export interface AuditEvent {
  event_id: string;
  sequence_number: number;
  timestamp: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  outcome: string;
  metadata: Record<string, unknown>;
  previous_hash: string;
  event_hash: string;
  schema_version: string;
}

export interface AuditVerificationResult {
  is_valid: boolean;
  total_events: number;
  verified_count: number;
  chain_head_hash?: string | null;
  genesis_hash?: string | null;
  tampered_event_id?: string | null;
  tampered_sequence?: number | null;
  error_reason?: string | null;
  verified_at: string;
}



