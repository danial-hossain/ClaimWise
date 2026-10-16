'use client';
import { Check, Circle, AlertCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import { Skeleton } from '@/components/ui/Motion';
export type AnalysisPhase = 'idle' | 'requesting' | 'complete' | 'error';
export default function AnalysisProgress({ phase, policyReady, children }: { phase: AnalysisPhase; policyReady: boolean; children?: ReactNode }) {
  if (phase === 'idle' && !children) return null;
  const steps = [
    { label: 'Readable policy selected', done: policyReady },
    { label: phase === 'requesting' ? 'Analyzing your scenario against the policy' : phase === 'complete' ? 'Analysis response received' : 'Analysis request failed', done: phase === 'complete' },
    { label: 'Saved analysis available', done: phase === 'complete' },
  ];
  return <section className="wizard-analysis-progress" aria-label="Analysis request progress" aria-busy={phase === 'requesting'}>
    {phase !== 'idle' && <><ol>{steps.map(({ label, done }, index) => <li key={index} data-complete={done}>{done ? <Check size={17} className="wizard-draw-check" /> : phase === 'error' && index === 1 ? <AlertCircle size={17} /> : <Circle size={17} />}<span>{label}</span></li>)}</ol>
    <p role="status">{phase === 'requesting' ? 'The backend is processing this request. Detailed processing stages are not reported.' : phase === 'error' ? 'Analysis could not finish. Your scenario is kept here; retry when you are ready.' : 'Analysis complete. Your saved findings are ready to review.'}</p></>}
    {(phase === 'requesting' || children) && <div className="wizard-analysis-output">
      <div className="wizard-analysis-skeleton" aria-hidden="true" style={{ opacity: phase === 'requesting' ? 1 : 0 }}><Skeleton className="wizard-skeleton-line short" /><Skeleton className="wizard-skeleton-line" /><Skeleton className="wizard-skeleton-line" /><Skeleton className="wizard-skeleton-quote" /></div>
      {phase !== 'requesting' && <div className="wizard-analysis-result wizard-result-reveal">{children}</div>}
    </div>}
  </section>;
}
