import type { CoverageGapAnalysisResult } from '@/types/api';
/** A concise existing benefit/category label; never repeat the entire incident as a heading. */
export function coverageNeedName(analysis: CoverageGapAnalysisResult, index: number): string {
  const category = analysis.category?.trim();
  if (category && !/^(member need|custom|user custom|insurance claim)$/i.test(category)) return category;
  return analysis.clauses.find(citation => citation.clause_heading?.trim())?.clause_heading?.trim() || `Need ${index + 1}`;
}
