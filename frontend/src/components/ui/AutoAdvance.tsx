"use client";
import { useRouter } from 'next/navigation';
import { ArrowRight, CircleCheck, X } from 'lucide-react';
import { useScenario } from '@/context/ScenarioContext';
import { WIZARD_STEPS, wizardUrl } from '@/lib/wizard';

export type Handoff = { href: string; title: string; description: string; seconds?: number };
export default function AutoAdvance({ handoff, onPause }: { handoff: Handoff; onPause: () => void }) {
  const router = useRouter();
  const { isWizard, scenario } = useScenario();
  // Part 2 is manual. The wizard's footer owns its one primary action.
  if (isWizard) return null;
  const [pathname, query] = handoff.href.split('?');
  const step = WIZARD_STEPS.find(item => item.page === pathname);
  const params = new URLSearchParams(query);
  const destination = step ? wizardUrl(step.id, { policyId: params.get('policy_id') || scenario.policyId, analysisId: params.get('analysis_id') || scenario.analysisId, claimId: params.get('claim_id') || scenario.claimId }) : handoff.href;
  return <aside className="workflow-handoff" aria-label="Next step">
    <CircleCheck className="h-6 w-6 shrink-0 text-emerald-600" />
    <div className="min-w-0 flex-1"><p role="status" className="text-sm font-semibold text-slate-900">{handoff.title}</p><p className="mt-1 text-xs leading-5 text-slate-600">{handoff.description} Continue when you are ready.</p></div>
    <div className="flex flex-wrap items-center gap-2"><button type="button" onClick={onPause} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600"><X className="h-3.5 w-3.5" />Dismiss</button><button type="button" onClick={() => router.push(destination)} className="cw-primary-button inline-flex items-center gap-2 px-3 py-2 text-xs font-semibold">Continue<ArrowRight className="h-3.5 w-3.5" /></button></div>
  </aside>;
}
