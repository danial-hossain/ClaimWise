'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, X } from 'lucide-react';
import { useScenario } from '@/context/ScenarioContext';
import { autoAdvanceDelay } from '@/lib/wizard-behavior';
import { wizardUrl, type WizardStep } from '@/lib/wizard';

export function FirstRunHint() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try { setVisible(localStorage.getItem('claimwise_wizard_hint_seen') !== '1'); } catch { setVisible(true); }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  if (!visible) return null;
  return <aside className="wizard-first-hint"><p>After your policy is ready, review your analysis here and continue to guidance when you choose.</p><button type="button" aria-label="Dismiss automatic step hint" onClick={() => { setVisible(false); try { localStorage.setItem('claimwise_wizard_hint_seen', '1'); } catch { /* Optional hint preference. */ } }}><X size={16} /></button></aside>;
}

export default function AutoAdvanceNotice({ step, enabled }: { step: WizardStep; enabled: boolean }) {
  const { scenario, remember } = useScenario();
  const router = useRouter();
  const delay = enabled ? autoAdvanceDelay(step, scenario) : null;
  const { policyId, analysisId, claimId } = scenario;
  useEffect(() => {
    if (delay === null) return;
    const timer = window.setTimeout(() => {
      remember(step === 'policy' ? { policyAdvancedId: policyId } : { analysisAdvancedId: analysisId, analysisAdvancePending: undefined });
      router.push(wizardUrl(step === 'policy' ? 'analysis' : 'guidance', { policyId, analysisId, claimId }), { scroll: false });
    }, delay);
    return () => window.clearTimeout(timer);
  }, [delay, step, policyId, analysisId, claimId, remember, router]);
  if (delay === null) return null;
  return <p role="status" className="wizard-success"><Check className="wizard-draw-check" size={18} />{step === 'policy' ? 'Policy ready. Moving to Analysis…' : 'Analysis complete. Moving to Guidance…'}</p>;
}
