"use client";
import { Suspense, useEffect, useState, type ReactNode } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, ArrowRight, LoaderCircle } from 'lucide-react';
import { GlassPanel } from '@/components/ui/Glass';
import { useScenario } from '@/context/ScenarioContext';
import { WIZARD_STEPS, completedSteps, wizardStep, wizardUrl, type WizardStep } from '@/lib/wizard';
import StepTransition from './StepTransition';
import { WizardActionContext, type WizardAction } from './WizardAction';
import AutoAdvanceNotice, { FirstRunHint } from './AutoAdvanceNotice';

const loading = () => <p role="status" className="py-8 text-sm text-slate-600">Loading this step…</p>;
// Reuse the existing route screens and their API/evidence pipelines without duplicating them.
const Policy = dynamic(() => import('@/app/policies/page'), { loading });
const Analysis = dynamic(() => import('@/app/coverage/page'), { loading });
const Guidance = dynamic(() => import('@/app/workspace/page'), { loading });
const Draft = dynamic(() => import('@/app/claims/page'), { loading });
const screens = { policy: Policy, analysis: Analysis, guidance: Guidance, draft: Draft };

function StepPanel({ step, children }: { step: WizardStep; children: ReactNode }) {
  const { scenario, remember, wizardHref } = useScenario();
  const router = useRouter();
  const index = WIZARD_STEPS.findIndex(item => item.id === step);
  const definition = WIZARD_STEPS[index];
  const [action, setAction] = useState<WizardAction | null>(null);
  const next = WIZARD_STEPS[index + 1];
  const completed = completedSteps(scenario);
  const goNext = () => {
    if (!next) return;
    remember({ visited: [...new Set([...(scenario.visited || []), step, next.id])], ...(step === 'guidance' ? { guidanceReviewed: true } : {}), ...(step === 'policy' ? { policyAdvancedId: scenario.policyId } : {}) });
    router.push(wizardHref(next.id), { scroll: false });
  };
  const defaultAction: WizardAction = { label: next ? `Continue to ${next.label.toLowerCase()}` : 'Open My claims', disabled: step === 'policy' ? !completed.policy : step === 'analysis' || step === 'guidance' ? !completed.analysis : !completed.draft, onClick: next ? goNext : () => router.push('/claims') };
  const primary = action || defaultAction;
  return <WizardActionContext.Provider value={setAction}>
    <GlassPanel className="wizard-panel" aria-labelledby={`wizard-title-${step}`}>
      <header className="wizard-panel-heading"><p className="cw-label">Step {index + 1} of 4 · {definition.label}</p><h1 id={`wizard-title-${step}`} tabIndex={-1} data-wizard-heading>{definition.title}</h1><p>{definition.description}</p></header>
      <div className="wizard-step-body" data-wizard-step={step}><AutoAdvanceNotice step={step} enabled={Boolean(action?.autoAdvanceReady)} /><Suspense fallback={loading()}>{children}</Suspense></div>
      <footer className="wizard-footer"><Link href={index ? wizardHref(WIZARD_STEPS[index - 1].id) : '/dashboard'} scroll={false} className="wizard-back"><ArrowLeft className="h-4 w-4" />Back</Link><span className="wizard-footer-note">Preparation only. Nothing is sent to an insurer.</span><button data-wizard-primary-action type={primary.form ? 'submit' : 'button'} form={primary.form} disabled={primary.disabled || primary.busy} aria-busy={primary.busy || undefined} onClick={primary.form ? undefined : primary.onClick} className="cw-primary-button inline-flex items-center justify-center gap-2 px-5 py-3 text-sm font-semibold">{primary.busy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}{primary.label}{!primary.busy && <ArrowRight className="h-4 w-4" />}</button></footer>
    </GlassPanel>
  </WizardActionContext.Provider>;
}

export default function WizardFlow() {
  const params = useSearchParams();
  const step = wizardStep(params.get('step'));
  const index = WIZARD_STEPS.findIndex(item => item.id === step);
  const { scenario, remember, restored } = useScenario();
  const router = useRouter();
  const visited = scenario.visited;
  const atFreshStart = step === 'policy' && !params.has('policy_id') && !params.has('analysis_id') && !params.has('claim_id');
  useEffect(() => {
    if (!restored) return;
    if (scenario.resetting) {
      if (atFreshStart) remember({ resetting: false, visited: ['policy'], lastStep: 'policy' });
      else router.replace(wizardUrl('policy'), { scroll: false });
    } else if (!visited?.includes(step) || scenario.lastStep !== step) remember({ visited: [...new Set([...(visited || []), step])], lastStep: step });
  }, [step, restored, visited, remember, scenario.resetting, scenario.lastStep, atFreshStart, router]);
  const Screen = screens[step];
  return <div className="wizard-shell"><FirstRunHint />{restored && !scenario.resetting ? <StepTransition index={index} identity={String(scenario.revision || 0)}><StepPanel step={step}><Screen /></StepPanel></StepTransition> : loading()}</div>;
}
