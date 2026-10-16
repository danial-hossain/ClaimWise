"use client";

import { createContext, Suspense, useCallback, useContext, useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from './AuthContext';
import { wizardUrl, type WizardStep, type WizardProgress } from '@/lib/wizard';
import type { ClaimChecklistItem, IncidentGuidanceResult, QAResponse } from '@/types/api';

export type ScenarioMessage = { id: string; sender: 'user' | 'assistant'; text: string; qaResponse?: QAResponse; messageType?: 'platform_guide'; timestamp: string };

export type Scenario = WizardProgress & {
  revision?: number;
  resetting?: boolean;
  lastStep?: WizardStep;
  title?: string;
  incidentDraft?: string;
  questionDraft?: string;
  policyAdvancedId?: string;
  analysisAdvancePending?: string;
  analysisAdvancedId?: string;
  guidanceMessages?: ScenarioMessage[];
  claimEditDraft?: { claimId: string; fields: Record<string, string>; description: string };
  claimDraft?: { fields: Record<string, string>; checklist?: ClaimChecklistItem[]; providedDocuments?: string; deadlineReferenceDate?: string; guidance?: IncidentGuidanceResult | null };
};
type Journey = {
  scenario: Scenario; restored: boolean; isWizard: boolean;
  remember: (next: Scenario) => void; reset: () => void; startWizard: () => void;
  href: (page: string) => string;
  wizardHref: (step: WizardStep, next?: Partial<Scenario>) => string;
};
const Context = createContext<Journey | null>(null);
function storage(owner: string) { return owner === 'guest' ? sessionStorage : localStorage; }
function read(owner: string): Scenario {
  try {
    const value = JSON.parse(storage(owner).getItem(`claimwise_journey:${owner}`) || '{}');
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  } catch { return {}; }
}

function RouteContext() {
  const params = useSearchParams();
  const { remember, scenario } = useScenario();
  const policyId = params.get('policy_id');
  const analysisId = params.get('analysis_id');
  const claimId = params.get('claim_id');
  const incident = params.get('scenario');
  useEffect(() => {
    if (scenario.resetting) return;
    if (analysisId) remember({ analysisId, ...(policyId ? { policyId } : {}), ...(claimId ? { claimId } : {}) });
    else if (claimId) remember({ claimId, ...(policyId ? { policyId } : {}) });
    else if (incident !== null) remember({ ...(policyId ? { policyId } : {}), incidentDraft: incident, title: incident, analysisId: undefined, claimId: undefined });
    else if (policyId) remember({ policyId });
  }, [policyId, analysisId, claimId, incident, remember, scenario.resetting]);
  return null;
}

export function ScenarioProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const owner = user?.id || 'guest';
  const [stored, setStored] = useState<{ owner: string; value: Scenario; ready: boolean }>({ owner: '', value: {}, ready: false });
  const scenario = stored.owner === owner ? stored.value : {};
  const restored = stored.owner === owner && stored.ready;
  const remember = useCallback((next: Scenario) => {
    setStored(previous => {
      let current = previous.owner === owner && previous.ready ? previous.value : read(owner);
      if ('policyId' in next && current.policyId && next.policyId !== current.policyId) {
        current = { revision: current.revision, incidentDraft: current.incidentDraft, title: current.incidentDraft, visited: ['policy'] };
      }
      if (next.analysisId && current.analysisId !== next.analysisId) {
        current = { revision: current.revision, policyId: current.policyId, policyReady: current.policyReady, policyAdvancedId: current.policyAdvancedId, incidentDraft: current.incidentDraft, title: current.title, visited: ['policy', 'analysis'] };
      }
      if (next.claimId && current.claimId && next.claimId !== current.claimId && !next.analysisId) current = { revision: current.revision };
      const value = { ...current, ...next };
      if (previous.ready && previous.owner === owner && JSON.stringify(value) === JSON.stringify(previous.value)) return previous;
      try { storage(owner).setItem(`claimwise_journey:${owner}`, JSON.stringify(value)); } catch { /* Server records remain authoritative. */ }
      return { owner, value, ready: true };
    });
  }, [owner]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setStored(previous => previous.owner === owner && previous.ready ? previous : { owner, value: read(owner), ready: true });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [owner]);
  const isWizard = path === '/claims/new';
  const clearScenario = (openWizard: boolean) => {
    const fresh: Scenario = { revision: (scenario.revision || 0) + 1, resetting: openWizard };
    try {
      storage(owner).setItem(`claimwise_journey:${owner}`, JSON.stringify(fresh));
      localStorage.removeItem(`claimwise_coverage_state_v1:${owner}`);
    } catch { /* A new in-memory scenario is still available. */ }
    setStored({ owner, value: fresh, ready: true });
    router.push(openWizard ? wizardUrl('policy') : '/dashboard');
  };
  const reset = () => clearScenario(isWizard);
  const startWizard = () => clearScenario(true);
  const href = (page: string) => {
    const params = new URLSearchParams();
    if (scenario.policyId) params.set('policy_id', scenario.policyId);
    if (scenario.analysisId && ['/coverage', '/workspace', '/claims'].includes(page)) params.set('analysis_id', scenario.analysisId);
    if (scenario.claimId && ['/workspace', '/claims'].includes(page)) params.set('claim_id', scenario.claimId);
    return page + (params.size ? `?${params}` : '');
  };
  const wizardHref = (step: WizardStep, next: Partial<Scenario> = {}) => wizardUrl(step, { ...scenario, ...next });
  return <Context.Provider value={{ scenario, restored, isWizard, remember, reset, startWizard, href, wizardHref }}><Suspense fallback={null}><RouteContext /></Suspense>{children}</Context.Provider>;
}
export function useScenario() {
  const context = useContext(Context);
  if (!context) throw new Error('ScenarioProvider is required');
  return context;
}

function PageIdentity({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const params = useSearchParams();
  const identity = pathname === '/claims/new' ? pathname : `${pathname}?${params}`;
  return <div className={pathname === '/claims/new' ? undefined : 'cw-page-enter'} key={`${user?.id || 'guest'}:${identity}`}>{children}</div>;
}
export function ScenarioPageContent({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<p role="status" className="p-6 text-sm text-slate-500">Loading your insurance workspace…</p>}><PageIdentity>{children}</PageIdentity></Suspense>;
}
