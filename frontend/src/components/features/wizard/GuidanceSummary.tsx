'use client';
import CitationChip from '@/components/ui/CitationChip';
import { guidancePresentation } from '@/lib/evidencePresentation';
import type { CoverageGapAnalysisResult } from '@/types/api';

export default function GuidanceSummary({ analysis }: { analysis: CoverageGapAnalysisResult }) {
  const guidance = guidancePresentation(analysis);
  return <section className="wizard-guidance-summary" aria-label="Guidance based on policy evidence">
    <section className="wizard-guidance-section"><h2>Next steps</h2>
      {guidance.actions.length ? <ul>{guidance.actions.map((action, i) => <li key={i}><p>{action.text}</p><div className="wizard-citations">{action.citations.map(c => <CitationChip key={`${c.policy_id}:${c.clause_id}:${c.page_number}`} citation={c} defaultExpanded />)}</div></li>)}</ul>
        : <p>No separate policy-supported next steps were saved for this analysis. Ask a follow-up question or request document guidance in the claim draft.</p>}
    </section>
    <section className="wizard-guidance-section"><h2>Questions to ask your insurer</h2>
      {guidance.questions.length ? <ul className="wizard-question-list">{guidance.questions.map(question => <li key={question}>{question}</li>)}</ul> : <p>No insurer questions were returned.</p>}
    </section>
    {guidance.limitations.map(item => <p key={item} role="note">Evidence limitation: {item}</p>)}
    <p className="text-xs text-slate-600">Review the coverage analysis for the policy interpretation. These steps do not guarantee claim acceptance or payment. Document checklists and deadlines require the incident details in your claim draft.</p>
  </section>;
}
