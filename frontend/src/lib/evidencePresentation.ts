import type { VerifiedCitation } from '../types/api.ts';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function text(value: unknown): string { return typeof value === 'string' ? value : ''; }
function strings(value: unknown): string[] { return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []; }
function citations(value: unknown): VerifiedCitation[] {
  return Array.isArray(value) ? value.filter((item): item is VerifiedCitation => {
    const c = record(item);
    return c.verified === true && typeof c.exact_quote === 'string' && typeof c.clause_id === 'string'
      && typeof c.policy_id === 'string' && Number.isInteger(c.page_number) && Number(c.page_number) > 0;
  }) : [];
}
export function analysisPresentation(value: unknown) {
  const source = record(value);
  return { explanation: text(source.explanation) || 'Policy interpretation is unavailable for this saved response.',
    citations: citations(source.clauses), limitations: strings(source.evidence_limitations) };
}
export function guidancePresentation(value: unknown) {
  const source = record(value);
  const actions = Array.isArray(source.guidance) ? source.guidance.flatMap(item => {
    const action = record(item), proof = citations(action.citations), content = text(action.text);
    return content && proof.length && content !== text(source.explanation) ? [{ text: content, citations: proof }] : [];
  }) : [];
  return { actions, questions: strings(source.insurer_questions), limitations: strings(source.evidence_limitations) };
}

/** In-flight responses from another scope must never update the visible chat. */
export function requestEpoch() {
  let current = 0;
  return { begin: () => ++current, invalidate: () => { ++current; }, isCurrent: (id: number) => id === current };
}
