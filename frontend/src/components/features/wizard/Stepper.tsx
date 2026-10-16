"use client";
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { Check } from 'lucide-react';
import { GlassBar } from '@/components/ui/Glass';
import { useScenario } from '@/context/ScenarioContext';
import { WIZARD_STEPS, canVisitStep, completedSteps, wizardStep } from '@/lib/wizard';

export default function Stepper() {
  const path = usePathname();
  const params = useSearchParams();
  const { scenario, reset, wizardHref } = useScenario();
  if (path !== '/claims/new') return null;
  const step = wizardStep(params.get('step'));
  const index = WIZARD_STEPS.findIndex(item => item.id === step);
  const completed = completedSteps(scenario);
  return <GlassBar className="wizard-stepper" aria-label="Claim preparation progress">
    <div className="wizard-stepper-inner">
      <div className="wizard-scenario"><p title={scenario.title || scenario.incidentDraft}>{scenario.title || scenario.incidentDraft || 'Your insurance scenario'}</p><button type="button" onClick={reset}>New scenario</button></div>
      <div className="wizard-mobile-progress"><span aria-current="step">Step {index + 1} of 4 <strong>{WIZARD_STEPS[index].label}</strong></span><div className="wizard-mobile-track" role="progressbar" aria-label="Current preparation step" aria-valuemin={1} aria-valuemax={4} aria-valuenow={index + 1}><span style={{ transform: `scaleX(${(index + 1) / 4})` }} /></div></div>
      <ol className="wizard-steps">{WIZARD_STEPS.map((item, i) => <li key={item.id}>
        {i > 0 && <div className="wizard-step-connector" aria-hidden="true"><span style={{ transform: `scaleX(${i <= index ? 1 : 0})` }} /></div>}
        {canVisitStep(item.id, scenario) || i === index ? <Link scroll={false} href={wizardHref(item.id)} aria-current={i === index ? 'step' : undefined} className={`wizard-step ${i === index ? 'is-current' : ''} ${completed[item.id] ? 'is-complete' : ''}`}><span className="wizard-step-number">{completed[item.id] && i !== index ? <Check className="h-4 w-4 wizard-draw-check" aria-hidden="true" /> : i + 1}</span><span>{item.label}</span>{completed[item.id] && <span className="sr-only">, completed</span>}</Link> : <button type="button" disabled className="wizard-step is-future" aria-label={`${item.label}, not yet reached`}><span className="wizard-step-number">{i + 1}</span><span>{item.label}</span></button>}
      </li>)}</ol>
      <span className="sr-only" aria-live="polite" aria-atomic="true">Step {index + 1} of 4: {WIZARD_STEPS[index].label}</span>
    </div>
  </GlassBar>;
}
