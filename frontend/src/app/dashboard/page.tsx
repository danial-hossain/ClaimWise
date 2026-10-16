"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, RefreshCw, X } from 'lucide-react';
import ScenarioLauncher from '@/components/features/dashboard/ScenarioLauncher';
import HeroSection from '@/components/ui/HeroSection';
import HeroIllustration from '@/components/ui/HeroIllustration';
import SummaryStrip from '@/components/features/dashboard/SummaryStrip';
import AttentionList, { type AttentionItem } from '@/components/features/dashboard/AttentionList';
import { Skeleton, StaggerGroup, StaggerItem } from '@/components/ui/Motion';
import { useAuth } from '@/context/AuthContext';
import { fetchClaims, fetchUploadedPolicies } from '@/lib/api';
import type { ClaimRecord, PolicyExtractionResult } from '@/types/api';

export default function DashboardPage() {
  const { openAuthModal, user } = useAuth();
  const scenarioDialog = useRef<HTMLDialogElement>(null);
  const [policies, setPolicies] = useState<PolicyExtractionResult[]>([]);
  const [claims, setClaims] = useState<ClaimRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [policiesAvailable, setPoliciesAvailable] = useState(false);
  const [claimsAvailable, setClaimsAvailable] = useState(false);
  const requiresSignIn = /401|unauthori[sz]ed|authentication required|bearer token/i.test(error);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [policyResult, claimResult] = await Promise.all([fetchUploadedPolicies(), fetchClaims()]);
      const errors = [policyResult.error, claimResult.error].filter(Boolean);
      setPoliciesAvailable(Boolean(policyResult.data));
      setClaimsAvailable(Boolean(claimResult.data));
      if (errors.length) setError(errors.join(' '));
      if (policyResult.data) setPolicies(policyResult.data);
      if (claimResult.data) setClaims([...claimResult.data].sort((a,b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)));
      setLoaded(true);
    } catch (error) { setError(error instanceof Error ? error.message : 'Your overview could not be loaded.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    window.addEventListener('claimwise_profile_updated', load);
    return () => { window.clearTimeout(timer); window.removeEventListener('claimwise_profile_updated', load); };
  }, [load]);
  // Present existing preparation facts; do not infer new coverage gaps from policy text.
  const attention: AttentionItem[] = [
    ...policies.filter(policy => policy.status !== 'success' || !policy.has_extractable_text).map(policy => ({ id: policy.document_hash, title: policy.document_name, explanation: policy.message, status: 'uncertain' as const, statusLabel: 'Policy needs review', actionLabel: 'Review policy', actionHref: '/policies' })),
    ...claims.flatMap(claim => (claim.checklist || []).filter(item => !item.completed).map(item => {
      const clause = policies.find(policy => policy.policy_id === claim.policy_id)?.clauses.find(clause => clause.clause_id === item.source_clause_id);
      return { id: `${claim.id}:${item.id}`, title: item.title, explanation: item.description || 'This saved checklist item is incomplete.', status: 'conditional' as const, statusLabel: 'Preparation', clauseRef: clause ? `Clause ${clause.clause_id} · p. ${clause.page_number}` : undefined, quote: clause?.text, actionLabel: 'Review claim', actionHref: `/claims?claim_id=${encodeURIComponent(claim.id)}` };
    })),
  ];
  return <div className="overview-shell mx-auto max-w-6xl px-4 py-8 sm:px-7 sm:py-12 lg:px-10">
    <header className="cw-overview-heading"><div><p className="cw-label">Overview</p><h1>{user?.full_name ? `Welcome back, ${user.full_name.split(' ')[0]}.` : 'Your insurance, in focus.'}</h1><p>A clear view of your policies and the next steps that need your attention.</p></div><nav aria-label="Quick actions"><Link href="/policies">Upload a policy</Link><Link href="/workspace">Ask a question</Link><Link href="/claims">View claims</Link></nav></header>
    {loading && !loaded ? <div role="status" aria-label="Loading portfolio figures" className="cw-metrics-loading"><Skeleton /><Skeleton /><Skeleton /></div> : <SummaryStrip metrics={[
      { id: 'policies-count', label: 'Saved policies', value: policiesAvailable ? policies.length : '—', subtext: policiesAvailable ? 'Documents in your portfolio' : 'Policy count unavailable' },
      { id: 'saved-claims', label: 'Saved claims', value: claimsAvailable ? claims.length : '—', subtext: claimsAvailable ? 'Internal claim records' : 'Sign in to view claims' },
      { id: 'documents-needed', label: 'Checklist items left', value: claimsAvailable ? claims.reduce((count, claim) => count + (claim.checklist || []).filter(item => !item.completed).length, 0) : '—', subtext: claimsAvailable ? 'Incomplete saved checklist items' : 'Preparation details unavailable' },
    ]} />}
    <HeroSection
      eyebrow="Your insurance, in focus"
      title={{ firstLine: 'Understand your policy.', secondLine: 'Plan your next step.' }}
      description="Review your documents and find the next step that is supported by your own policy."
      primaryAction={<button type="button" onClick={() => scenarioDialog.current?.showModal()} aria-haspopup="dialog" aria-controls="start-scenario-dialog" className="hero-section-primary">Start with your situation <ArrowRight className="h-4 w-4" /></button>}
      variant="document"
      className="overview-hero"
    >
      <HeroIllustration variant="document" />
    </HeroSection>
    {error && <div role={requiresSignIn ? 'status' : 'alert'} className={`mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4 text-sm ${requiresSignIn ? 'border-teal-200/70 bg-white/85 text-teal-900' : 'border-rose-200 bg-rose-50 text-rose-800'}`}><span>{requiresSignIn ? 'Sign in to view your saved claims and portfolio.' : error}</span>{requiresSignIn ? <button type="button" onClick={() => openAuthModal('login')} className="font-semibold underline underline-offset-4">Sign in</button> : <button type="button" onClick={() => void load()} className="inline-flex items-center gap-2 font-semibold"><RefreshCw className="h-4 w-4" />Retry</button>}</div>}
    <StaggerGroup className="cw-overview-content">
    <StaggerItem><section aria-labelledby="overview-attention-title"><div className="cw-section-heading"><h2 id="overview-attention-title">Needs attention</h2><Link href="/claims">View claims →</Link></div>{loading && !loaded ? <div role="status" className="space-y-3"><Skeleton className="h-16" /><Skeleton className="h-16" /></div> : <AttentionList items={attention} />}{!claimsAvailable && loaded && <p className="mt-3 text-xs text-slate-600">Claim preparation items are unavailable until you sign in.</p>}</section></StaggerItem>
    </StaggerGroup>
    <dialog ref={scenarioDialog} id="start-scenario-dialog" aria-labelledby="scenario-start-title" className="scenario-dialog" onClick={event => { if (event.target === event.currentTarget) { const bounds = event.currentTarget.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) event.currentTarget.close(); } }}>
      <button type="button" aria-label="Close scenario" onClick={() => scenarioDialog.current?.close()} className="scenario-dialog-close"><X className="h-5 w-5" /></button>
      <ScenarioLauncher policies={policies} loading={loading && !loaded} />
    </dialog>
  </div>;
}
