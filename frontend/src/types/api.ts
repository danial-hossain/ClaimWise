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
  is_clause?: boolean;
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
  user_id?: string | null;
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
  history?: { role: 'user' | 'assistant'; content: string }[];
}

export interface QAResponse {
  evidence_limitations?: string[];
  question: string;
  answer: string;
  evidence_sufficient: boolean;
  evidence_status: PolicyEvidenceStatus;
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
  analysis_id?: string | null;
  coverage_analysis?: CoverageGapAnalysisResult | null;
  claim_description_draft?: string | null;
  id: string;
  user_id: string;
  policy_id: string;
  claim_reference?: string | null;
  bill_id?: string;
  bill_document_name?: string;
  bill_document_hash?: string;
  incident_date: string;
  total_billed_cents: number;
  status: string;
  line_items: BillLineItem[];
  adjudicated_items: AdjudicatedLineItem[];
  eob?: ExplanationOfBenefits | null;
  sandbox_submission?: Record<string, unknown> | null;
  claim_type?: string | null;
  incident_description?: string | null;
  incident_location?: string | null;
  estimated_loss_cents?: number | null;
  checklist?: ClaimChecklistItem[];
  timeline?: ClaimTimelineEvent[];
  documents?: ClaimDocumentMeta[];
  created_at: string;
  updated_at: string;
}

export interface ClaimChecklistItem {
  id: string;
  title: string;
  description?: string | null;
  mandatory: boolean;
  completed: boolean;
  source_clause_id?: string | null;
}

export interface ClaimTimelineEvent {
  id: string;
  event_type: string;
  summary: string;
  source: 'internal' | 'insurer' | 'simulation' | string;
  created_at: string;
}

export interface ClaimDocumentMeta {
  id: string;
  file_name: string;
  file_size_bytes: number;
  mime_type: string;
  uploaded_at: string;
}

export interface ClaimIntakePayload {
  analysis_id?: string;
  policy_id: string;
  claim_type: string;
  incident_description: string;
  incident_date: string;
  incident_location?: string;
  estimated_loss_cents?: number | null;
  claim_reference?: string;
  checklist?: ClaimChecklistItem[];
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

export interface PriorAuthServiceItem {
  service: string;
  clause_id: string;
  page: number;
  quote: string;
}

export interface PolicyAttributeEvidence {
  attribute_name: string;
  display_name: string;
  raw_value: string | null;
  numeric_value_cents: number | null;
  status: AttributeStatus;
  citations: VerifiedCitation[];
  notes?: string | null;
  required_services?: PriorAuthServiceItem[];
  not_specified_services?: string[];
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

export interface QuestionEvaluationResult {
  question_id: number;
  category: string;
  policy_id: string;
  policy_name: string;
  question: string;
  is_answerable: boolean;
  evidence_sufficient: boolean;
  decision_correct: boolean;
  groundedness_pass: boolean;
  citation_accuracy_pass: boolean;
  abstention_pass: boolean;
  adversarial_defense_pass: boolean;
  hallucination_detected: boolean;
  retrieval_top_1_hit: boolean;
  retrieval_top_k_hit: boolean;
  retrieved_clause_count: number;
  top_retrieved_clause_id?: string | null;
  top_retrieved_rrf_score: number;
  citations_count: number;
  cited_clause_ids: string[];
  answer_preview: string;
  abstention_reason?: string | null;
  clarification_question?: string | null;
  latency_ms: number;
}

export interface BenchmarkRunSummary {
  total_questions: number;
  answerable_count: number;
  unanswerable_count: number;
  decision_accuracy_pct: number;
  groundedness_pct: number;
  citation_accuracy_pct: number;
  honest_abstention_pct: number;
  hallucination_rate_pct: number;
  adversarial_defense_pct: number;
  retrieval_top_1_hit_pct: number;
  retrieval_top_k_recall_pct: number;
  avg_latency_ms: number;
  min_latency_ms: number;
  max_latency_ms: number;
  execution_mode: 'live_gemini' | 'deterministic_mock' | string;
  model_evaluated: string;
  evaluated_at: string;
  all_passed: boolean;
}

export interface BenchmarkExecutionReport {
  summary: BenchmarkRunSummary;
  results: QuestionEvaluationResult[];
}

export type CoverageVerdictType = 'covered' | 'conditional' | 'excluded' | 'uncertain';

export interface PresetScenarioItem {
  id: string;
  category: string;
  situation: string;
  description: string;
  keywords: string[];
}

export interface CoverageScenarioRequest {
  policy_id: string;
  situation: string;
  category?: string | null;
  description?: string | null;
}

export interface CoverageGapAnalysisResult {
  guidance?: { text: string; citations: VerifiedCitation[] }[];
  evidence_limitations?: string[];
  id: string;
  policy_id: string;
  category: string;
  situation: string;
  description: string;
  verdict: CoverageVerdictType;
  evidence_status: PolicyEvidenceStatus;
  explanation: string;
  conditions_summary?: string | null;
  cost_sharing_summary?: string | null;
  prior_auth_required: boolean;
  clauses: VerifiedCitation[];
  insurer_questions: string[];
  confidence_score: number;
  analyzed_at: string;
}

export type PolicyEvidenceStatus =
  | 'supported'
  | 'explicitly_excluded'
  | 'not_specified'
  | 'evidence_unavailable';

export interface CoverageGapReportResponse {
  policy_id: string;
  policy_name: string;
  document_hash: string;
  total_scenarios_evaluated: number;
  covered_count: number;
  conditional_count: number;
  excluded_count: number;
  uncertain_count: number;
  coverage_score_pct: number;
  scenarios: CoverageGapAnalysisResult[];
  evaluated_at: string;
}

export type IncidentCategoryType =
  | 'emergency_room'
  | 'inpatient_hospital'
  | 'outpatient_surgery'
  | 'diagnostic_imaging'
  | 'specialist_consult'
  | 'physical_therapy'
  | 'prescription_drug'
  | 'accident_injury'
  | 'routine_preventative'
  | 'other';

export type NetworkStatusType = 'in_network' | 'out_of_network' | 'emergency_out_of_network' | 'unsure';
export type PriorAuthStatusType = 'obtained' | 'not_obtained' | 'emergency_waived' | 'not_applicable' | 'unsure';
export type ReferralStatusType = 'yes_referred' | 'no_self_referral' | 'not_required';
export type LiabilityTypeOption =
  | 'none_standard'
  | 'motor_vehicle'
  | 'workplace_injury'
  | 'third_party_liability'
  | 'secondary_insurance';

export type GuidanceRiskLevelType = 'low_risk' | 'medium_risk' | 'high_risk';
export type DocumentItemStatusType = 'provided' | 'missing' | 'recommended';

export interface QuestionnaireOption {
  id: string;
  label: string;
  description?: string;
  risk_implication?: string;
}

export interface QuestionnaireField {
  id: string;
  title: string;
  description: string;
  field_type: string;
  required: boolean;
  options?: QuestionnaireOption[];
  help_text?: string;
}

export interface IncidentPresetTemplate {
  id: string;
  title: string;
  description: string;
  category: IncidentCategoryType;
  default_answers: Record<string, unknown>;
}

export interface IncidentQuestionnaireSchema {
  version: string;
  title: string;
  description: string;
  fields: QuestionnaireField[];
  presets: IncidentPresetTemplate[];
}

export interface IncidentQuestionnaireRequest {
  policy_id: string;
  incident_date?: string | null;
  deadline_reference_date?: string | null;
  estimated_loss_cents?: number | null;
  incident_category: IncidentCategoryType;
  network_status: NetworkStatusType;
  prior_auth_status: PriorAuthStatusType;
  referral_status?: ReferralStatusType;
  liability_type?: LiabilityTypeOption;
  has_itemized_bill?: boolean;
  has_medical_records?: boolean;
  has_prior_auth_letter?: boolean;
  has_referral_letter?: boolean;
  has_accident_report?: boolean;
  has_receipt_of_payment?: boolean;
  provided_document_titles?: string[];
  user_notes?: string | null;
}

export interface TimelyFilingAnalysis {
  incident_date: string;
  evaluation_date: string;
  days_elapsed: number;
  timely_filing_limit_days?: number | null;
  days_remaining?: number | null;
  is_timely?: boolean | null;
  filing_deadline_date?: string | null;
  warning_message?: string | null;
  deadline_anchor?: string | null;
  citation?: VerifiedCitation | null;
}

export interface DocumentChecklistItem {
  item_id: string;
  title: string;
  description: string;
  is_mandatory: boolean;
  status: DocumentItemStatusType;
  why_needed: string;
  policy_citation?: VerifiedCitation | null;
}

export interface IdentifiedObstacle {
  id: string;
  title: string;
  severity: 'critical' | 'warning' | 'advisory';
  description: string;
  mitigation_strategy: string;
  citation?: VerifiedCitation | null;
}

export interface ProviderInquiry {
  target: string;
  question: string;
  rationale: string;
}

export interface IncidentGuidanceResult {
  guidance_id: string;
  policy_id: string;
  policy_name: string;
  readiness_score_pct: number;
  risk_level: GuidanceRiskLevelType;
  readiness_summary: string;
  incident_category: IncidentCategoryType;
  timely_filing: TimelyFilingAnalysis;
  document_checklist: DocumentChecklistItem[];
  obstacles: IdentifiedObstacle[];
  action_plan_steps: string[];
  provider_inquiries: ProviderInquiry[];
  claimability_status: 'potentially_claimable' | 'not_supported' | 'cannot_determine' | string;
  claimability_reason: string;
  claimability_citations: VerifiedCitation[];
  claim_amount_cents?: number | null;
  potential_claim_clauses: VerifiedCitation[];
  verified_citations: VerifiedCitation[];
  disclaimer: string;
  evaluated_at: string;
}

// ============================================================================
// F4: Aggregate Portfolio Management & COB Optimizer Types
// ============================================================================

export type PolicyRoleType = 'primary' | 'secondary' | 'supplemental' | 'unspecified';

export type OverlapRedundancyDegreeType =
  | 'full_duplicate'
  | 'partial_complementary'
  | 'differential_cost_sharing'
  | 'prior_auth_asymmetry';

export type AggregateGapSeverityType = 'critical' | 'moderate' | 'advisory';

export type COBRuleType =
  | 'subscriber_employee_rule'
  | 'birthday_rule'
  | 'active_vs_inactive_rule'
  | 'longer_vs_shorter_rule'
  | 'default_order';

export type SubscriberRelationshipType =
  | 'policyholder'
  | 'dependent_spouse'
  | 'dependent_child'
  | 'other_dependent';

export type EmploymentStatusType = 'active' | 'retired' | 'cobra' | 'other';

export interface SubscriberProfile {
  policy_id: string;
  policy_name?: string | null;
  subscriber_name?: string | null;
  relationship: SubscriberRelationshipType;
  employment_status: EmploymentStatusType;
  birthday_month_day?: string | null;
  effective_date?: string | null;
}

export interface PolicyBenefitSnapshot {
  policy_id: string;
  policy_name: string;
  covered: boolean;
  cost_sharing_summary: string;
  prior_auth_required: boolean;
  citations: VerifiedCitation[];
}

export interface CoverageOverlapItem {
  category: string;
  service_name: string;
  redundancy_degree: OverlapRedundancyDegreeType;
  policies: PolicyBenefitSnapshot[];
  coordination_strategy: string;
  notes: string;
}

export interface AggregateGapItem {
  category: string;
  service_name: string;
  severity: AggregateGapSeverityType;
  status_summary: string;
  policies: PolicyBenefitSnapshot[];
  exposure_analysis: string;
  recommended_mitigation: string;
  silence_or_exclusion_proof: VerifiedCitation[];
}

export interface COBDetermination {
  primary_policy_id: string;
  primary_policy_name: string;
  secondary_policy_id?: string | null;
  secondary_policy_name?: string | null;
  rule_applied: COBRuleType;
  determination_reason: string;
  step_by_step_filing_guide: string[];
  non_duplication_clause_alert: string;
  financial_benefit_estimate: string;
}

export interface PortfolioScorecard {
  protection_score_percent: number;
  redundancy_index_percent: number;
  total_policies: number;
  total_overlaps_detected: number;
  total_aggregate_gaps_detected: number;
  aggregate_in_network_deductible_cents?: number | null;
  aggregate_in_network_oop_max_cents?: number | null;
}

export interface PortfolioAnalysisRequest {
  policy_ids: string[];
  subscribers?: SubscriberProfile[] | null;
  patient_relationship?: string | null;
}

export interface PortfolioAnalysisResult {
  id: string;
  created_at: string;
  analyzed_policies: Array<{
    policy_id: string;
    policy_name: string;
    insurer_name: string;
    document_hash: string;
    clause_count: number;
  }>;
  scorecard: PortfolioScorecard;
  cob_guidance: COBDetermination;
  overlaps: CoverageOverlapItem[];
  aggregate_gaps: AggregateGapItem[];
  key_takeaways: string[];
  non_guarantee_disclaimer: string;
}

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  phone_number?: string | null;
  country?: string | null;
  occupation_status?: 'student' | 'employee' | 'self_employed' | 'other' | string | null;
  organization?: string | null;
  address?: string | null;
  tier: 0 | 1 | 2 | 3 | 4;
  created_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
  message: string;
  csrf_token?: string | null;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface SignUpPayload {
  email: string;
  password: string;
  full_name: string;
  role?: string;
  phone_number?: string;
  country?: string;
  occupation_status?: 'student' | 'employee' | 'self_employed' | 'other' | string;
  organization?: string;
}

export interface DemoLoginPayload {
  role: 'policyholder' | 'broker' | 'advocate';
}
