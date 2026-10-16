export const WIZARD_STEPS = [
  { id: 'policy', label: 'My policies', title: 'My Policies', description: 'Select or upload the policy you want to check.', page: '/policies' },
  { id: 'analysis', label: 'Coverage', title: 'Coverage', description: 'Describe what happened and review the findings against your policy evidence.', page: '/coverage' },
  { id: 'guidance', label: 'Ask ClaimWise', title: 'Ask ClaimWise', description: 'Ask follow-up questions while keeping your policy and analysis in context.', page: '/workspace' },
  { id: 'draft', label: 'My claims', title: 'My Claims', description: 'Review the incident, checklist, and supporting evidence before saving a draft.', page: '/claims' },
] as const;
export type WizardStep = typeof WIZARD_STEPS[number]['id'];
export type WizardReferences = { policyId?: string; analysisId?: string; claimId?: string };
export function wizardStep(value: string | null): WizardStep {
  return WIZARD_STEPS.find(step => step.id === value)?.id || 'policy';
}
export function wizardUrl(step: WizardStep, references: WizardReferences = {}) {
  const params = new URLSearchParams({ step });
  if (references.policyId) params.set('policy_id', references.policyId);
  if (references.analysisId && step !== 'policy') params.set('analysis_id', references.analysisId);
  if (references.claimId && (step === 'guidance' || step === 'draft')) params.set('claim_id', references.claimId);
  return `/claims/new?${params}`;
}
export type WizardProgress = WizardReferences & { policyReady?: boolean; analysisReady?: boolean; claimReady?: boolean; guidanceReviewed?: boolean; visited?: WizardStep[] };
export function completedSteps(state: WizardProgress): Record<WizardStep, boolean> {
  return { policy: Boolean(state.policyId && state.policyReady), analysis: Boolean(state.analysisId && state.analysisReady), guidance: Boolean(state.guidanceReviewed), draft: Boolean(state.claimId && state.claimReady) };
}
export function canVisitStep(step: WizardStep, state: WizardProgress) {
  return step === 'policy' || Boolean(state.visited?.includes(step)) || completedSteps(state)[step];
}
