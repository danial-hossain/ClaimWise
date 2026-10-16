'use client';
import Link from 'next/link';
import { analysisPresentation } from '@/lib/evidencePresentation';
import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useScenario } from '@/context/ScenarioContext';
import type { CoverageGapAnalysisResult } from '@/types/api';
import { analysisLink } from '@/lib/claimWorkflow';
import { wizardUrl } from '@/lib/wizard';
import CoverageComponentFindings from './CoverageComponentFindings';
import StatusBadge from './StatusBadge';
export default function AnalysisContext({ analysis }: { analysis: CoverageGapAnalysisResult }) {
  const findings = analysisPresentation(analysis);
  const path = usePathname();
  const { remember, isWizard } = useScenario();
  useEffect(() => { remember({ policyId: analysis.policy_id, analysisId: analysis.id, analysisReady: true, title: analysis.situation }); }, [analysis.id, analysis.policy_id, analysis.situation, remember]);
  return <section className="cw-glass rounded-2xl border border-teal-200 p-5 text-xs space-y-3">
    <h3 className="font-semibold text-teal-950">Your scenario and policy evidence</h3>
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm font-semibold text-slate-900">{analysis.situation}</p><StatusBadge status={analysis.overall_assessment || analysis.verdict} /></div>
    <p className="text-sm leading-6 text-slate-600">{findings.explanation}</p>
    <details open={isWizard}><summary className="cursor-pointer font-medium text-teal-800">Review findings, conditions and cited clauses</summary><div className="mt-3 space-y-3">
    <p className="font-medium">{analysis.situation}</p><p className="whitespace-pre-wrap">{analysis.description}</p>
    {analysis.components?.length ? <CoverageComponentFindings components={analysis.components} policyName={analysis.policy_name || undefined} /> : <>
      {analysis.conditions_summary && <p>Conditions: {analysis.conditions_summary}</p>}
      {analysis.cost_sharing_summary && <p>Limits and cost sharing: {analysis.cost_sharing_summary}</p>}
      {findings.citations.map(c => <blockquote key={`${c.clause_id}-${c.page_number}`} className="border-l-2 border-teal-300 pl-3"><strong>{analysis.policy_name ? `${analysis.policy_name} · ` : ''}{c.clause_heading ? `${c.clause_heading} · ` : ''}Clause {c.clause_id} · PDF page {c.page_number}{c.printed_page_label ? ` · printed page ${c.printed_page_label}` : ''}</strong><p>{c.exact_quote}</p></blockquote>)}
    </>}
    {!!analysis.insurer_questions?.length && <div>Information to confirm:<ul className="list-disc pl-5">{analysis.insurer_questions.map(q => <li key={q}>{q}</li>)}</ul></div>}
    {findings.limitations.map(item => <p key={item} role="note">Evidence limitation: {item}</p>)}
    <p className="text-slate-600">Policy evidence is limited to the uploaded document. This assessment does not guarantee coverage, payment, or claim approval.</p>
    </div></details>
    <nav aria-label="Scenario actions" className="analysis-context-actions flex flex-wrap items-center gap-3 border-t border-teal-900/10 pt-3 text-xs font-semibold">
      {path !== '/coverage' && <Link className="text-slate-600 hover:text-teal-800" href={analysisLink('coverage', analysis.id)}>Review coverage</Link>}
      {path !== '/workspace' && <Link className={path === '/coverage' ? 'cw-primary-button rounded-lg px-4 py-2.5' : 'text-teal-800'} href={wizardUrl('guidance', { policyId: analysis.policy_id, analysisId: analysis.id })}>{path === '/coverage' ? 'Next: Ask ClaimWise →' : 'Ask ClaimWise'}</Link>}
      {path !== '/claims' && <Link className={path === '/workspace' ? 'cw-primary-button rounded-lg px-4 py-2.5' : 'text-slate-600 hover:text-teal-800'} href={wizardUrl('draft', { policyId: analysis.policy_id, analysisId: analysis.id })}>{path === '/workspace' ? 'Next: Prepare a claim →' : 'Prepare a claim'}</Link>}
    </nav>
  </section>;
}
