import Link from 'next/link';
import { useState } from 'react';
import { Clock3, FileText, HelpCircle } from 'lucide-react';
import type { CoverageGapAnalysisResult } from '@/types/api';
import { analysisLink } from '@/lib/claimWorkflow';
import { coverageNeedName } from '@/lib/coverage-presentation';
import GlassModal from './GlassModal';
import { GlassPanel } from './Glass';
import StatusBadge from './StatusBadge';
import CitationChip from './CitationChip';
import CoverageComponentFindings from './CoverageComponentFindings';

export default function CoverageNeedRow({ analysis: sc, index, isUserCustom, autoOpen = false, onClarify }: { analysis: CoverageGapAnalysisResult; index: number; isUserCustom: boolean; autoOpen?: boolean; onClarify: () => void }) {
  const [open, setOpen] = useState(autoOpen);
  const name = coverageNeedName(sc, index);
  const clause = sc.clauses?.[0];
  const assessment = sc.overall_assessment || sc.verdict;
  const needsClarification = !!sc.insurer_questions?.length;
  const statusLabel = sc.evidence_status === 'evidence_unavailable' ? 'Evidence unavailable' : sc.evidence_status === 'not_specified' && sc.verdict === 'uncertain' && !sc.overall_assessment ? 'Not specified' : undefined;
  return <>
    <GlassPanel as="article" className="cw-need-row cw-need-summary" data-verdict={sc.verdict}>
      <button type="button" className="cw-need-summary-button" aria-haspopup="dialog" onClick={() => setOpen(true)}>
        <span className="cw-need-summary-copy">
          <span className="cw-need-summary-title">{name}</span>
          <span className="cw-need-summary-situation">{sc.situation}</span>
        </span>
        <StatusBadge status={assessment} label={statusLabel} />
        <span className="cw-need-clause-chip"><FileText size={13} />{clause ? `${clause.clause_id} · p. ${clause.page_number}` : 'No clause cited'}</span>
      </button>
      {needsClarification && <div className="flex justify-end border-t border-slate-100 px-4 py-2">
        <button type="button" aria-label={`Clarify ${name} with AI`} onClick={onClarify} className="inline-flex items-center gap-1.5 rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800 transition-colors hover:bg-teal-100">
          <HelpCircle size={15} />Clarify with AI
        </button>
      </div>}
    </GlassPanel>
    <GlassModal open={open} onClose={() => setOpen(false)} title={name} description={sc.situation}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-600">Policy assessment:</span>
        <StatusBadge status={assessment} label={statusLabel} />
      </div>
      {sc.description && <p className="mb-4 text-sm leading-6 text-slate-600">{sc.description}</p>}
      <p className="mb-5 text-sm leading-6 text-slate-700">{sc.explanation}</p>
      {sc.components?.length ? <CoverageComponentFindings components={sc.components} policyName={sc.policy_name || undefined} /> : <div className="cw-need-evidence">
        <section>
          <h4>What your policy says</h4>
          <div className="cw-need-conditions"><p><strong>Conditions:</strong> {sc.conditions_summary || 'Not specified'}</p><p><strong>Limits and cost sharing:</strong> {sc.cost_sharing_summary || 'Not specified'}</p></div>
          {sc.prior_auth_required && <p className="mt-3 inline-flex items-center gap-2 text-amber-800"><Clock3 size={15} />Prior authorization required</p>}
        </section>
        <section><h4>Policy evidence</h4>{sc.clauses?.length ? <div className="cw-evidence-chips">{sc.clauses.map((citation, i) => <CitationChip key={`${citation.clause_id}:${i}`} citation={citation} policyName={sc.policy_name || undefined} defaultExpanded />)}</div> : <p>No verified clause was returned. Missing evidence does not mean this need is excluded.</p>}</section>
      </div>}
      {sc.evidence_limitations?.length ? <section><h4>Evidence limitations</h4><ul className="list-disc pl-5 text-sm">{sc.evidence_limitations.map(item => <li key={item}>{item}</li>)}</ul></section> : null}
      {sc.guidance?.length ? <section><h4>Next steps</h4><div className="space-y-3">{sc.guidance.map((action, i) => <div key={`${action.text}:${i}`}><p className="text-sm leading-6">{action.text}</p><div className="mt-2 space-y-2">{action.citations.map((citation, citationIndex) => <CitationChip key={`${citation.clause_id}:${citation.page_number}:${citationIndex}`} citation={citation} defaultExpanded />)}</div></div>)}</div></section> : null}
      {sc.insurer_questions?.length ? <section className="cw-need-questions"><h4>Questions to ask your insurer</h4><ul>{sc.insurer_questions.map(question => <li key={question}>{question}</li>)}</ul></section> : null}
      <div className="cw-need-actions">
        {isUserCustom && <><Link onClick={() => setOpen(false)} href={analysisLink('claims', sc.id)}>Prepare a claim →</Link><Link onClick={() => setOpen(false)} href={analysisLink('workspace', sc.id)}>Ask ClaimWise</Link></>}
        {needsClarification && <button type="button" onClick={() => { setOpen(false); onClarify(); }}><HelpCircle size={15} />Clarify with AI ({sc.insurer_questions.length})</button>}
      </div>
    </GlassModal>
  </>;
}
