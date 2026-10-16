'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, FileText, GitCompare, RefreshCw, Sparkles } from 'lucide-react';
import { fetchUploadedPolicies } from '@/lib/api';
import { workflowRequest } from '@/lib/claimWorkflow';
import type { PolicyExtractionResult, VerifiedCitation } from '@/types/api';
import PageHero from '@/components/ui/PageHero';
import { GlassPanel } from '@/components/ui/Glass';
import CitationChip from '@/components/ui/CitationChip';
import GlassModal from '@/components/ui/GlassModal';

type OverlapResult = {
  status: 'overlaps_found' | 'no_verified_overlaps' | 'incomplete';
  overlaps: { benefit: string; explanation: string; qualifications: string; citations: VerifiedCitation[] }[];
  policies: { policy_id: string; policy_name: string; reviewed_clauses: number; total_clauses: number; complete: boolean }[];
  rejected_findings: number;
  model_used: string;
};

export default function ComparePage() {
  const [policies, setPolicies] = useState<PolicyExtractionResult[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [comparisonOpen, setComparisonOpen] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<OverlapResult | null>(null);
  const revision = useRef(0);

  useEffect(() => {
    let active = true;
    async function load() {
      const response = await fetchUploadedPolicies();
      if (!active) return;
      setPolicies(response.data || []);
      setError(response.error || '');
      setLoading(false);
    }
    void load();
    return () => { active = false; };
  }, []);

  function toggle(id: string) {
    revision.current += 1;
    setResult(null);
    setError('');
    setSelected(current => current.includes(id) ? current.filter(value => value !== id) : current.length < 4 ? [...current, id] : current);
  }

  async function compare() {
    if (selected.length < 2 || busy) return;
    const currentRevision = revision.current;
    setComparisonOpen(true);
    setBusy(true); setError(''); setResult(null);
    try {
      const response = await workflowRequest<OverlapResult>('comparisons/overlaps', 'POST', { policy_ids: selected });
      if (revision.current === currentRevision) setResult(response);
    } catch (error) {
      if (revision.current === currentRevision) setError(error instanceof Error ? error.message : 'Could not compare these policies. Please retry.');
    } finally { setBusy(false); }
  }

  return <div className="app-page mx-auto max-w-7xl space-y-7 px-4 py-8 sm:px-7 lg:px-10">
    <PageHero currentPage="Compare policies" title="Find where your policies overlap" illustrated={{ eyebrow: 'Compare policies', firstLine: 'Different policies.', secondLine: 'A clearer picture.', variant: 'compare' }} description="AI reviews the actual wording of your selected policies to identify shared coverage, explain differences, and show the source clauses behind each finding." />
    <GlassPanel className="p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="text-lg font-semibold text-slate-900">Choose policies to compare</h2><p className="mt-1 text-sm text-slate-600">Select 2 to 4 documents from your policy library.</p></div><span className="rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800">{selected.length} selected</span></div>
      {loading ? <p role="status" className="mt-6 text-sm text-slate-600">Loading your policies…</p> : policies.length === 0 ? <div className="mt-6 rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-600">Your saved policies will appear here. <Link href="/policies" className="font-semibold text-teal-800 underline">Add policies</Link> to start a comparison.</div> : <div className="mt-5 grid gap-3 md:grid-cols-2">{policies.map(policy => {
        const id = policy.policy_id || '';
        const usable = Boolean(id && policy.status === 'success' && policy.has_extractable_text && policy.clauses.length);
        return <label key={policy.document_hash} className={`flex min-w-0 items-start gap-3 rounded-2xl border p-4 ${selected.includes(id) ? 'border-teal-500 bg-teal-50/80' : 'border-slate-200 bg-white/90'} ${busy || !usable ? 'opacity-60' : 'cursor-pointer'}`}>
          <input type="checkbox" className="mt-1 h-4 w-4 accent-teal-700" checked={selected.includes(id)} disabled={busy || !usable || (!selected.includes(id) && selected.length >= 4)} onChange={() => toggle(id)} />
          <FileText className="mt-0.5 h-5 w-5 shrink-0 text-teal-700" /><span className="min-w-0"><span className="block break-words text-sm font-semibold text-slate-900">{policy.document_name}</span><span className="mt-1 block text-xs text-slate-500">{usable ? `${policy.total_pages} pages · ${policy.total_clauses.toLocaleString()} clauses` : 'Text extraction required before comparison'}</span></span>
        </label>;
      })}</div>}
      {!loading && policies.length < 2 && <p className="mt-4 text-sm text-slate-600">Add at least two policies to identify overlapping coverage.</p>}
      <button type="button" disabled={busy || selected.length < 2} onClick={() => void compare()} className="hero-section-primary mt-6 disabled:cursor-not-allowed disabled:opacity-50">{busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}{busy ? 'AI is reviewing your policies…' : 'Analyze coverage overlaps'}</button>
      {(result || busy) && <button type="button" onClick={() => setComparisonOpen(true)} aria-haspopup="dialog" className="hero-section-secondary mt-6 ml-3">{busy ? 'View progress' : 'View comparison'}</button>}
    </GlassPanel>
    {error && !comparisonOpen && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    <GlassModal open={comparisonOpen} onClose={() => setComparisonOpen(false)} title="Policy comparison" description="Review shared coverage, conditions, and the supporting policy clauses." className="comparison-results-modal">
    {busy && <div role="status" className="flex flex-col items-center gap-4 py-14 text-center"><RefreshCw className="h-8 w-8 animate-spin text-teal-700" /><p className="font-semibold text-slate-900">Comparing your policies?</p><p className="max-w-md text-sm leading-6 text-slate-600">Reading policy clauses and checking citations across the selected documents. You can close this popup while the review continues.</p></div>}
    {error && <div role="alert" className="flex gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800"><AlertCircle className="h-5 w-5 shrink-0" />{error}</div>}
    {result && <section className="space-y-5" aria-live="polite">
      <div><h2 className="flex items-center gap-2 text-xl font-semibold text-slate-900"><Sparkles className="h-5 w-5 text-teal-700" />AI coverage overlap review</h2><p className="mt-2 text-sm text-slate-600">{result.overlaps.length ? `${result.overlaps.length} shared coverage area${result.overlaps.length === 1 ? '' : 's'} supported by quotes from multiple policies.` : 'No overlap could be verified from the reviewed clauses. This does not establish that the policies have no overlapping coverage.'}</p></div>
      {result.overlaps.length > 0 && <div className="comparison-matrix-scroll" role="region" aria-label="Side-by-side policy comparison" tabIndex={0}>
        <table className="comparison-matrix">
          <caption className="sr-only">Shared coverage with policy evidence side by side</caption>
          <thead><tr><th scope="col">Coverage area</th>{result.policies.map(policy => <th scope="col" key={policy.policy_id}><FileText className="mb-2 h-5 w-5 text-teal-700" /><span>{policy.policy_name}</span></th>)}</tr></thead>
          {result.overlaps.map((finding, index) => <tbody key={`${index}:${finding.benefit}`}>
            <tr><th scope="row">{finding.benefit}</th>{result.policies.map(policy => {
              const citations = finding.citations.filter(citation => citation.policy_id === policy.policy_id);
              return <td key={policy.policy_id}>{citations.length ? <div className="space-y-3"><span className="comparison-matrix-match">Shared coverage evidence</span>{citations.map((citation, i) => <CitationChip className="comparison-matrix-citation" key={`${citation.clause_id}:${i}`} citation={citation} policyName={policy.policy_name} defaultExpanded />)}</div> : <p className="text-sm leading-6 text-slate-500">No verified overlap evidence returned for this policy in this area. This does not establish that coverage is absent.</p>}</td>;
            })}</tr>
            <tr className="comparison-matrix-analysis"><td colSpan={result.policies.length + 1}><div className="grid gap-4 md:grid-cols-2"><div><h4>How the policies overlap</h4><p>{finding.explanation}</p></div><div><h4>Conditions and differences</h4><p>{finding.qualifications}</p></div></div></td></tr>
          </tbody>)}
        </table>
      </div>}
      <GlassPanel className="p-5 text-xs leading-6 text-slate-600"><h3 className="font-semibold text-slate-900">Documents reviewed</h3>{result.policies.map(policy => <p key={policy.policy_id}>{policy.policy_name}: {policy.reviewed_clauses.toLocaleString()} of {policy.total_clauses.toLocaleString()} extracted clauses reviewed{!policy.complete ? ' — partial review; other overlaps may remain unidentified' : ''}.</p>)}{result.rejected_findings > 0 && <p className="mt-2 text-amber-800">Some proposed findings were omitted because their citations could not be verified.</p>}<p className="mt-2">Shared coverage does not guarantee payment or double reimbursement. Review policy conditions and coordination terms with the insurers before making changes.</p></GlassPanel>
    </section>}
    </GlassModal>
  </div>;
}
