import { Suspense } from 'react';
import WizardFlow from '@/components/features/wizard/WizardFlow';
export default function NewClaimPage() {
  return <Suspense fallback={<p role="status" className="p-6 text-sm text-slate-600">Loading your claim preparation…</p>}><WizardFlow /></Suspense>;
}
