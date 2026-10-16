import type { CoverageGapAnalysisResult } from '@/types/api';
/** A concise existing benefit/category label; never repeat the entire incident as a heading. */
export function coverageNeedName(analysis: CoverageGapAnalysisResult, index: number): string {
  const category = analysis.category?.trim();
  if (category && !/^(member need|custom|user custom|insurance claim)$/i.test(category)) return category;
  return analysis.clauses.find(citation => citation.clause_heading?.trim())?.clause_heading?.trim() || `Need ${index + 1}`;
}

function scenarioOutcome(scenario: CoverageGapAnalysisResult): string {
  const assessment = scenario.overall_assessment;
  if (assessment && assessment !== 'insufficient_evidence') return assessment;

  const componentOutcomes = (scenario.components || [])
    .filter(component => !component.kind || component.kind === 'insured_loss')
    .map(component => component.verdict)
    .filter((verdict): verdict is NonNullable<typeof verdict> => Boolean(verdict));
  if (!componentOutcomes.length) return assessment || scenario.verdict;

  const outcomes = new Set(componentOutcomes);
  const hasPositive = outcomes.has('covered') || outcomes.has('conditional');
  const hasNegativeOrUnknown = outcomes.has('excluded') || outcomes.has('uncertain');
  if (outcomes.has('partially_covered') || (hasPositive && hasNegativeOrUnknown)) return 'partially_covered';
  if (outcomes.size === 1 && outcomes.has('covered')) return 'potentially_covered';
  if (outcomes.has('conditional') || (outcomes.has('covered') && outcomes.has('conditional'))) return 'conditional_or_limited';
  if (outcomes.size === 1 && outcomes.has('excluded')) return 'potentially_excluded';
  return 'insufficient_evidence';
}

export function coverageOutcomeCounts(scenarios: CoverageGapAnalysisResult[]) {
  return scenarios.reduce((counts, scenario) => {
    counts.total += 1;
    const outcome = scenarioOutcome(scenario);
    if (outcome === 'potentially_covered' || outcome === 'covered') counts.covered += 1;
    else if (outcome === 'partially_covered' || outcome === 'conditional_or_limited' || outcome === 'conditional') counts.partiallyCovered += 1;
    else if (outcome === 'potentially_excluded' || outcome === 'excluded') counts.notCovered += 1;
    else counts.uncertain += 1;
    return counts;
  }, { total: 0, covered: 0, partiallyCovered: 0, notCovered: 0, uncertain: 0 });
}
