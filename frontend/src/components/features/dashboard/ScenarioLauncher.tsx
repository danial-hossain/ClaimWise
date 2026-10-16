"use client";
import { useState } from 'react';
import { GlassPanel } from '@/components/ui/Glass';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useScenario } from '@/context/ScenarioContext';
import type { PolicyExtractionResult } from '@/types/api';

export default function ScenarioLauncher({ policies, loading }: { policies: PolicyExtractionResult[]; loading: boolean }) {
  const router = useRouter();
  const { scenario, remember, wizardHref } = useScenario();
  const [policyId, setPolicyId] = useState('');
  const incident = scenario.incidentDraft || '';
  const setIncident = (value: string) => remember({ incidentDraft: value, title: value });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selected = policyId || (policies.some(p => p.policy_id === scenario.policyId) ? scenario.policyId : '') || policies[0]?.policy_id || '';
  return <GlassPanel className="scenario-launcher mt-6 p-5 sm:p-7" aria-labelledby="scenario-start-title">
    <p className="cw-label">Start with what happened</p>
    <h2 id="scenario-start-title" className="mt-2 text-xl font-semibold text-slate-900">Let’s work through your situation.</h2>
    <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Choose a policy and tell us what happened. We’ll guide you from there.</p>
    {(scenario.analysisId || scenario.incidentDraft || scenario.claimDraft) && <Link href={wizardHref(scenario.lastStep || (scenario.claimId ? 'draft' : 'analysis'))} className="mt-4 block rounded-xl border border-teal-200 bg-teal-50 p-3 text-sm font-semibold text-teal-900">Continue: {scenario.title || 'Your saved scenario'} →</Link>}
    {loading ? <p role="status" className="mt-5 text-sm text-slate-500">Loading your portfolio…</p> : !policies.length ? <div className="mt-5 rounded-xl bg-teal-50 p-4"><p className="text-sm text-teal-950">Add your policy first so every answer can be checked against your insurance contract.</p><Link href="/claims/new?step=policy" className="cw-primary-button mt-3 inline-block px-4 py-2 text-xs font-semibold text-white">Upload your first policy →</Link></div> : <form className="mt-5 space-y-4" onSubmit={async event => {
      event.preventDefault(); if (busy || !selected) return;
      setBusy(true); setError('');
      try {
        const policy = policies.find(item => item.policy_id === selected);
        remember({ policyId: selected, incidentDraft: incident.trim(), title: incident.trim(), policyReady: Boolean(policy?.has_extractable_text && policy.clauses.length && policy.status === 'success'), analysisId: undefined, analysisReady: false, claimId: undefined, claimReady: false, guidanceReviewed: false, claimDraft: undefined, claimEditDraft: undefined, questionDraft: undefined, guidanceMessages: undefined, visited: ['policy', 'analysis'] });
        router.push(wizardHref('analysis', { policyId: selected, analysisId: undefined, claimId: undefined }));
      } catch (error) { setError(error instanceof Error ? error.message : 'Could not analyze this scenario.'); }
      finally { setBusy(false); }
    }}>
      <label className="block text-xs font-semibold text-slate-700">Policy to check<select disabled={busy} value={selected} onChange={e => setPolicyId(e.target.value)} className="mt-2 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm">{policies.map(p => <option key={p.policy_id} value={p.policy_id || ''}>{p.document_name}</option>)}</select></label>
      <label className="block text-xs font-semibold text-slate-700">Your incident or concern<textarea required minLength={5} maxLength={2000} rows={3} disabled={busy} value={incident} onChange={e => setIncident(e.target.value)} placeholder="For example: My luggage was lost during my trip. What might my policy cover, and what should I collect?" className="mt-2 block w-full rounded-xl border border-slate-300 p-3 text-sm font-normal" /></label>
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <div className="flex flex-wrap items-center gap-4"><button type="submit" disabled={busy || incident.trim().length < 5} className="cw-primary-button px-5 py-3 text-sm font-semibold disabled:opacity-50">{busy ? 'Checking your policy…' : 'Find my next step →'}</button><Link href={`/workspace?policy_id=${encodeURIComponent(selected)}&scenario=${encodeURIComponent(incident)}`} className="text-xs font-semibold text-teal-800">Ask a policy question first</Link></div>
      <p className="text-[11px] text-slate-500">Next: Coverage & Gap Analysis. Review your findings there, then continue to Ask ClaimWise for guidance. Coverage and approval are never guaranteed.</p>
    </form>}
  </GlassPanel>;
}
