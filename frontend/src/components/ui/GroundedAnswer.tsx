'use client';
import type { ReactNode } from 'react';
import type { QAResponse } from '@/types/api';
import CitationChip from './CitationChip';
import AbstainNotice from './AbstainNotice';

export default function GroundedAnswer({ response, children, policyNames = {} }: {
  response?: QAResponse; children: ReactNode; policyNames?: Record<string, string>;
}) {
  return <>
    {response && !response.evidence_sufficient && <AbstainNotice
      evidenceStatus={response.evidence_status}
      reason={response.abstention_reason || 'The retrieved excerpts do not establish a definitive answer.'}
      suggestedQuestions={response.clarification_question ? [response.clarification_question] : []}
    />}
    {children}
    {response?.evidence_limitations?.map(item => <p key={item} role="note" className="text-xs text-amber-900">Evidence limitation: {item}</p>)}
    {!!response?.citations?.length && <div className="pt-2 border-t border-slate-200/60 space-y-1.5">
      <span className="text-[11px] font-semibold text-slate-500 block">Supporting policy evidence:</span>
      <div className="flex flex-wrap gap-2">{response.citations.map(c => <CitationChip defaultExpanded
        key={`${c.policy_id}:${c.clause_id}:${c.page_number}`} citation={c} policyName={policyNames[c.policy_id]} />)}</div>
    </div>}
  </>;
}
