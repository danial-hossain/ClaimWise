// UI gates only. Server records and eligibility remain authoritative.
export function autoAdvanceDelay(step: string, state: {
  policyId?: string; policyReady?: boolean; policyAdvancedId?: string;
  analysisId?: string; analysisReady?: boolean; analysisAdvancePending?: string; analysisAdvancedId?: string;
}): number | null {
  if (step === 'policy' && state.policyReady && state.policyId && state.policyAdvancedId !== state.policyId) return 700;
  return null;
}
export function sandboxEligibility(status?: string): boolean {
  return status != null && [
    'draft',
    'evidence_gathering',
    'preparing_documents',
    'ready_to_submit',
    'analyzed',
    'sandbox_submitted',
  ].includes(status);
}
