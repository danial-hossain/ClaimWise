import type { CoverageGapAnalysisResult, CoverageScenarioRequest } from '../types/api.ts';

export type NeedEvaluation = { need: string; result: CoverageGapAnalysisResult } | { need: string; error: string };
type Analyze = (payload: CoverageScenarioRequest) => Promise<{ data: CoverageGapAnalysisResult | null; error: string | null }>;

/** The existing analysis endpoint remains the only source of coverage results. */
export async function evaluateNeeds(analyze: Analyze, policyId: string, needs: string[], context: string, category: string): Promise<NeedEvaluation[]> {
  return Promise.all(needs.map(async need => {
    try {
      const response = await analyze({ policy_id: policyId, situation: need, category, description: context || undefined });
      if (response.error || !response.data) return { need, error: response.error || 'The service returned no result.' };
      const result = response.data;
      if (typeof result.id !== 'string' || !result.id || result.policy_id !== policyId || result.situation?.trim() !== need.trim()
        || typeof result.explanation !== 'string' || !result.explanation.trim()
        || !['covered', 'conditional', 'excluded', 'uncertain'].includes(result.verdict)
        || !Array.isArray(result.clauses) || result.clauses.some(c => !c || c.policy_id !== policyId
          || c.verified !== true || typeof c.clause_id !== 'string' || typeof c.exact_quote !== 'string'
          || !Number.isInteger(c.page_number) || c.page_number < 1)
        || !Array.isArray(result.insurer_questions) || result.insurer_questions.some(q => typeof q !== 'string')) {
        return { need, error: 'The service returned an invalid or mismatched analysis. Please retry.' };
      }
      return { need, result };
    } catch (error) {
      return { need, error: error instanceof Error ? error.message : 'Could not analyze this scenario. Please retry.' };
    }
  }));
}

export function coverageRequestGate() {
  let version = 0;
  let pending = false;
  return {
    begin() { if (pending) return null; pending = true; return ++version; },
    isCurrent(ticket: number) { return ticket === version; },
    finish(ticket: number) { if (ticket === version) pending = false; },
    invalidate() { pending = false; return ++version; },
  };
}
