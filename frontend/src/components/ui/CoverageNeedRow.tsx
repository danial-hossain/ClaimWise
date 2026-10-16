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

export default function CoverageNeedRow({ analysis: sc, index, isUserCustom, onClarify }: { analysis: CoverageGapAnalysisResult; index: number; isUserCustom: boolean; onClarify: () => void }) {
  const [open, setOpen] = useState(false);
  const name = coverageNeedName(sc, index);
  const clause = sc.clauses?.[0];
  return <>
    <GlassPanel as="article" className="cw-need-row cw-need-summary" data-verdict={sc.verdict}>
      <button type="button" className="cw-need-summary-button" aria-haspopup="dialog" onClick={() => setOpen(true)}>
        <span className="cw-need-summary-copy">
          <span className="cw-need-summary-title">{name}</span>
          <span className="cw-need-summary-situation">{sc.situation}</span>
        </span>
        <StatusBadge status={sc.verdict} label={sc.evidence_status === 'evidence_unavailable' ? 'Evidence unavailable' : sc.evidence_status === 'not_specified' && sc.verdict === 'uncertain' ? 'Not specified' : undefined} />
        <span className="cw-need-clause-chip"><FileText size={13} />{clause ? `${clause.clause_id} · p. ${clause.page_number}` : 'No clause cited'}</span>
      </button>
    </GlassPanel>
    <GlassModal open={open} onClose={() => setOpen(false)} title={name} description={sc.situation}>
      {sc.description && <p className="mb-4 text-sm leading-6 text-slate-600">{sc.description}</p>}
      <div className="cw-need-evidence">
        <section>
          <h4>What your policy says</h4><p>{sc.explanation}</p>
          <div className="cw-need-conditions"><p><strong>Conditions:</strong> {sc.conditions_summary || 'Not specified'}</p><p><strong>Limits and cost sharing:</strong> {sc.cost_sharing_summary || 'Not specified'}</p></div>
          {sc.prior_auth_required && <p className="mt-3 inline-flex items-center gap-2 text-amber-800"><Clock3 size={15} />Prior authorization required</p>}
        </section>
        <section><h4>Policy evidence</h4>{sc.clauses?.length ? <div className="cw-evidence-chips">{sc.clauses.map((citation, i) => <CitationChip key={`${citation.clause_id}:${i}`} citation={citation} defaultExpanded />)}</div> : <p>No verified clause was returned. Missing evidence does not mean this need is excluded.</p>}</section>
      </div>
      <section className="cw-need-questions"><h4>Questions to ask your insurer <span>· {name}</span></h4>{sc.insurer_questions?.length ? <ul>{sc.insurer_questions.map(question => <li key={question}>{question}</li>)}</ul> : <p>Not specified — no insurer questions were returned.</p>}</section>
      <div className="cw-need-actions">
        {isUserCustom && <><Link onClick={() => setOpen(false)} href={analysisLink('claims', sc.id)}>Prepare a claim →</Link><Link onClick={() => setOpen(false)} href={analysisLink('workspace', sc.id)}>Ask ClaimWise</Link></>}
        {!!sc.insurer_questions?.length && <button type="button" onClick={onClarify}><HelpCircle size={15} />Clarify with AI ({sc.insurer_questions.length})</button>}
      </div>
    </GlassModal>
  </>;
}
