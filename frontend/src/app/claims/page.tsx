'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useScenario } from '@/context/ScenarioContext';
import { useWizardAction } from '@/components/features/wizard/WizardAction';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { sandboxEligibility } from '@/lib/wizard-behavior';
import AnalysisContext from '@/components/ui/AnalysisContext';
import { GlassPanel } from '@/components/ui/Glass';
import GlassModal from '@/components/ui/GlassModal';
import PageHero from '@/components/ui/PageHero';
import { Skeleton } from '@/components/ui/Motion';
import { workflowRequest, analysisLink, type AnalysisConversation } from '@/lib/claimWorkflow';
import {
  AlertCircle,
  ArrowDownToLine,
  Check,
  CheckCircle2,
  CircleAlert,
  Copy,
  Clock3,
  FileCheck2,
  FilePlus2,
  FileText,
  LoaderCircle,
  Plus,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
  X,
} from 'lucide-react';
import {
  createClaimIntake,
  downloadClaimDocument,
  evaluateIncidentGuidance,
  fetchClaimGuidance,
  fetchClaims,
  fetchUploadedPolicies,
  updateClaimIntake,
  uploadClaimDocument,
  submitClaimToSandbox,
} from '@/lib/api';
import type {
  ClaimChecklistItem,
  ClaimDocumentMeta,
  ClaimRecord,
  ClaimTimelineEvent,
  PolicyExtractionResult,
  IncidentGuidanceResult,
} from '@/types/api';

type ClaimForm = {
  policy_id: string;
  claim_type: string;
  incident_date: string;
  incident_location: string;
  incident_description: string;
  estimated_loss: string;
  claim_reference: string;
};

const emptyForm = (): ClaimForm => ({
  policy_id: '',
  claim_type: '',
  incident_date: '',
  incident_location: '',
  incident_description: '',
  estimated_loss: '',
  claim_reference: '',
});

const createChecklistItemId = () => {
  const randomId = globalThis.crypto?.randomUUID?.();
  return `member-${randomId || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
};

const statusLabels: Record<string, string> = {
  draft: 'Draft',
  evidence_gathering: 'Preparing Documents',
  preparing_documents: 'Preparing Documents',
  ready_to_submit: 'Ready for review (internal)',
  submitted: 'Submitted',
  under_review: 'Under Review',
  approved: 'Approved',
  rejected: 'Rejected',
  insurer_rejected: 'Rejected (simulation)',
  in_dispute: 'In Dispute (internal)',
  analyzed: 'Preparing Documents',
  sandbox_submitted: 'Submitted (simulation)',
  closed: 'Closed',
};

const terminalStatuses = new Set(['approved', 'rejected', 'insurer_rejected', 'closed']);
function statusLabel(claim: ClaimRecord): string {
  const raw = String(claim.status || 'draft').toLowerCase();
  const label = statusLabels[raw] || 'Draft';
  const insurerConfirmed = (claim.timeline || []).some((event) => event.source === 'insurer');
  if (claim.sandbox_submission && ['submitted', 'rejected', 'insurer_rejected', 'sandbox_submitted'].includes(raw)) {
    return `${label.replace(' (simulation)', '')} (simulation)`;
  }
  if (['submitted', 'under_review', 'approved', 'rejected'].includes(raw) && !insurerConfirmed) return 'Status needs confirmation';
  return label;
}

function statusClasses(claim: ClaimRecord): string {
  const status = String(claim.status || 'draft').toLowerCase();
  if (statusLabel(claim) === 'Status needs confirmation') return 'border-amber-200 bg-amber-50 text-amber-800';
  if (['approved', 'closed'].includes(status)) return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  if (status === 'ready_to_submit') return 'border-teal-200 bg-teal-50 text-teal-800';
  if (['rejected', 'insurer_rejected'].includes(status)) return 'border-rose-200 bg-rose-50 text-rose-800';
  return 'border-amber-200 bg-amber-50 text-amber-800';
}

function displayDate(value?: string | null): string {
  if (!value) return 'Not recorded';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(parsed);
}

function toDollars(value: string): number | null {
  if (!value.trim()) return null;
  const amount = Number(value.replace(/[$,\s]/g, ''));
  return Number.isFinite(amount) && amount >= 0 ? Math.round(amount * 100) : null;
}

function ClaimsGuidanceModal({ guidance, onClose }: { guidance: IncidentGuidanceResult; onClose: () => void }) {
  const filing = guidance.timely_filing;
  return (
    <GlassModal open onClose={onClose} title="What to review for this claim" description={`Policy-based guidance from ${guidance.policy_name}.`}>
        <div className="space-y-4">
          <section className={`rounded-xl border p-4 ${guidance.claimability_status === 'potentially_claimable' ? 'border-emerald-200 bg-emerald-50/60' : guidance.claimability_status === 'not_supported' ? 'border-rose-200 bg-rose-50/60' : 'border-amber-200 bg-amber-50/60'}`}><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Policy assessment</p><h3 className="mt-1 text-lg font-semibold text-slate-900">{guidance.claimability_status === 'potentially_claimable' ? 'Potentially claimable' : guidance.claimability_status === 'not_supported' ? 'Not supported by the cited policy wording' : 'Cannot determine from this policy'}</h3><p className="mt-2 text-sm leading-6 text-slate-700">{guidance.claimability_reason}</p></section>
          <section className="grid gap-3 sm:grid-cols-2"><div className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Claim amount</p><p className="mt-1 text-lg font-semibold text-slate-900">{guidance.claim_amount_cents != null ? new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD' }).format(guidance.claim_amount_cents / 100) : 'Not provided'}</p><p className="mt-1 text-[11px] leading-5 text-slate-500">{guidance.claim_amount_cents != null ? 'This is your entered estimate, not a confirmed covered or payable amount.' : 'Enter an estimated loss to show the amount you intend to claim.'}</p></div><div className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Filing due date</p><p className="mt-1 text-lg font-semibold text-slate-900">{filing.filing_deadline_date ? displayDate(filing.filing_deadline_date) : 'Cannot calculate'}</p><p className="mt-1 text-[11px] leading-5 text-slate-500">{filing.timely_filing_limit_days ? `${filing.timely_filing_limit_days} days from the ${filing.deadline_anchor || 'date stated in the policy'}.` : 'No explicit filing period was found in the extracted clauses.'}</p></div></section>
          <section><h3 className="text-sm font-semibold text-slate-900">Policy citations</h3>{guidance.claimability_citations.length || filing.citation ? <ul className="mt-2 space-y-2">{[...guidance.claimability_citations, ...(filing.citation && !guidance.claimability_citations.some((item) => item.clause_id === filing.citation?.clause_id) ? [filing.citation] : [])].map((citation) => <li key={`citation-${citation.clause_id}`} className="rounded-lg border border-slate-200 bg-white p-3"><p className="text-xs font-semibold text-teal-900">{citation.clause_heading || `Clause ${citation.clause_id}`} · page {citation.page_number}</p><p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-slate-700">“{citation.exact_quote}”</p></li>)}</ul> : <p className="mt-2 text-xs text-slate-600">No relevant clause citation could be verified from the extracted PDF.</p>}</section>
          <p className="rounded-lg bg-slate-50 p-3 text-[11px] leading-5 text-slate-500">This is a policy-text assessment, not an insurer decision. The payout can differ from your estimate due to limits, deductibles, conditions, and review of evidence.</p>
        </div>
    </GlassModal>
  );
}

function getTimeline(claim: ClaimRecord): ClaimTimelineEvent[] {
  const events = [...(claim.timeline || [])];
  if (!events.some((event) => event.event_type === 'draft_created')) {
    events.push({
      id: `created-${claim.id}`,
      event_type: 'draft_created',
      summary: 'Claim record created.',
      source: 'internal',
      created_at: claim.created_at,
    });
  }
  if (claim.eob && !events.some((event) => event.event_type === 'policy_analysis')) {
    events.push({
      id: `analysis-${claim.id}`,
      event_type: 'policy_analysis',
      summary: 'Internal policy analysis completed.',
      source: 'internal',
      created_at: claim.updated_at,
    });
  }
  if (claim.sandbox_submission && !events.some((event) => event.event_type === 'sandbox_simulation')) {
    events.push({
      id: `simulation-${claim.id}`,
      event_type: 'sandbox_simulation',
      summary: 'Local payer sandbox simulation completed. This was not sent to an insurer.',
      source: 'simulation',
      created_at: claim.updated_at,
    });
  }
  return events.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
}

function ClaimDetailsPanel({ inline, open, onClose, children }: { inline: boolean; open: boolean; onClose: () => void; children: React.ReactNode }) {
  return inline ? <div className="min-w-0">{children}</div> : <GlassModal open={open} onClose={onClose} title="Claim information" description="Review incident details, documents, policy evidence, and preparation progress." className="claim-information-modal">{children}</GlassModal>;
}

export default function ClaimsPage() {
  const router = useRouter();
  const [reviewMode, setReviewMode] = useState(false);
  const { remember, scenario, isWizard, wizardHref } = useScenario();
  const [initialWizard] = useState(() => isWizard ? scenario : null);
  const [linkedAnalysis, setLinkedAnalysis] = useState<AnalysisConversation['analysis'] | null>(null);
  const [descriptionDraft, setDescriptionDraft] = useState('');
  const [generatingDescription, setGeneratingDescription] = useState(false);
  const [policies, setPolicies] = useState<PolicyExtractionResult[]>([]);
  const [claims, setClaims] = useState<ClaimRecord[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState('');
  const [claimDetailsOpen, setClaimDetailsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [descriptionModalOpen, setDescriptionModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [checklistModalOpen, setChecklistModalOpen] = useState(false);
  const [reopenCreateAfterGuidance, setReopenCreateAfterGuidance] = useState(false);
  const [form, setForm] = useState<ClaimForm>(emptyForm());
  const [newChecklist, setNewChecklist] = useState<ClaimChecklistItem[]>([]);
  const [checklistGuidance, setChecklistGuidance] = useState('');
  const [isGeneratingChecklist, setIsGeneratingChecklist] = useState(false);
  const [providedDocuments, setProvidedDocuments] = useState('');
  const [deadlineReferenceDate, setDeadlineReferenceDate] = useState('');
  const [newClaimGuidance, setNewClaimGuidance] = useState<IncidentGuidanceResult | null>(null);
  const [guidanceModal, setGuidanceModal] = useState<IncidentGuidanceResult | null>(null);
  const [manualChecklistTitle, setManualChecklistTitle] = useState('');
  const [editForm, setEditForm] = useState<ClaimForm>(emptyForm());
  const [isSavingEdits, setIsSavingEdits] = useState(false);
  const [isUploadingDocument, setIsUploadingDocument] = useState(false);
  const [claimGuidance, setClaimGuidance] = useState<Record<string, IncidentGuidanceResult>>({});
  const [guidanceLoadingFor, setGuidanceLoadingFor] = useState<string | null>(null);
  const [claimGuidanceError, setClaimGuidanceError] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmSandbox, setConfirmSandbox] = useState(false);
  const [submittingSandbox, setSubmittingSandbox] = useState(false);
  const [sandboxSuccess, setSandboxSuccess] = useState<string | null>(null);

  const selectClaim = useCallback((claim: ClaimRecord) => {
    setClaimGuidanceError('');
    remember({ policyId: claim.policy_id, claimId: claim.id, claimReady: true, analysisId: claim.analysis_id || undefined, title: claim.incident_description || claim.claim_type || 'Claim preparation' });
    const cachedEdits = initialWizard?.claimEditDraft?.claimId === claim.id ? initialWizard.claimEditDraft : undefined;
    setDescriptionDraft(cachedEdits?.description ?? claim.claim_description_draft ?? '');
    setSelectedClaimId(claim.id);
    setEditModalOpen(false);
    setEditForm({
      policy_id: claim.policy_id,
      claim_type: claim.claim_type || 'Medical claim',
      incident_date: String(claim.incident_date || '').slice(0, 10),
      incident_location: claim.incident_location || '',
      incident_description: claim.incident_description || '',
      estimated_loss: claim.estimated_loss_cents != null
        ? (claim.estimated_loss_cents / 100).toFixed(2)
        : claim.total_billed_cents > 0 ? (claim.total_billed_cents / 100).toFixed(2) : '',
      claim_reference: claim.claim_reference || '',
      ...cachedEdits?.fields,
    });
    setNotice(null);
  }, [remember, initialWizard]);

  const loadWorkspace = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const [policyResult, claimResult] = await Promise.all([fetchUploadedPolicies(), fetchClaims()]);
    if (policyResult.error && !policyResult.data) setError(policyResult.error);
    else setPolicies(policyResult.data || []);
    if (claimResult.error && !claimResult.data) setError((previous) => previous ? `${previous} ${claimResult.error}` : claimResult.error);
    else setClaims([...(claimResult.data || [])].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()));
    const params = new URLSearchParams(window.location.search);
    setReviewMode(params.get('stage') === 'review');
    const analysisId = params.get('analysis_id') || initialWizard?.analysisId;
    const claimId = params.get('claim_id') || initialWizard?.claimId;
    const existing = claimResult.data?.find(c => claimId ? c.id === claimId : analysisId && c.analysis_id === analysisId);
    if (existing) {
      selectClaim(existing);
      if (claimId) setClaimDetailsOpen(true);
      setShowCreateForm(false);
    } else if (analysisId) {
      try {
        const record = await workflowRequest<AnalysisConversation>(`coverage/analyses/${encodeURIComponent(analysisId)}`);
        setLinkedAnalysis(record.analysis);
        setForm({ ...emptyForm(), claim_type: record.analysis.category || 'Insurance claim', incident_description: [record.analysis.situation, record.analysis.description].filter(Boolean).join('\n\n'), ...initialWizard?.claimDraft?.fields, policy_id: record.analysis.policy_id });
        setShowCreateForm(true);
      } catch (error) { setError(error instanceof Error ? error.message : 'Could not load analysis.'); }
    } else if (initialWizard) {
      setForm({ ...emptyForm(), policy_id: initialWizard.policyId || '', incident_description: initialWizard.incidentDraft || initialWizard.title || '', ...initialWizard.claimDraft?.fields });
      setShowCreateForm(true);
    }
    if (initialWizard?.claimDraft && !existing) {
      setNewChecklist(initialWizard.claimDraft.checklist || []);
      setProvidedDocuments(initialWizard.claimDraft.providedDocuments || '');
      setDeadlineReferenceDate(initialWizard.claimDraft.deadlineReferenceDate || '');
      setNewClaimGuidance(initialWizard.claimDraft.guidance || null);
    }
    setIsLoading(false);
  }, [selectClaim, initialWizard]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadWorkspace(), 0);
    window.addEventListener('claimwise_profile_updated', loadWorkspace);
    window.addEventListener('storage', loadWorkspace);
    return () => {
      window.clearTimeout(initialLoad);
      window.removeEventListener('claimwise_profile_updated', loadWorkspace);
      window.removeEventListener('storage', loadWorkspace);
    };
  }, [loadWorkspace]);

  const selectedClaim = claims.find((claim) => claim.id === selectedClaimId) || null;
  useEffect(() => {
    if (!isWizard || isLoading) return;
    if (showCreateForm) remember({ claimDraft: { fields: form, checklist: newChecklist, providedDocuments, deadlineReferenceDate, guidance: newClaimGuidance } });
    else if (selectedClaim) remember({ claimEditDraft: { claimId: selectedClaim.id, fields: editForm, description: descriptionDraft } });
  }, [isWizard, isLoading, showCreateForm, form, newChecklist, providedDocuments, deadlineReferenceDate, newClaimGuidance, selectedClaim, editForm, descriptionDraft, remember]);
  useWizardAction({
    label: sandboxSuccess ? 'Open My claims' : isWizard ? 'Review and submit' : showCreateForm ? 'Save claim draft' : selectedClaim ? 'Open saved claim' : 'Start claim draft',
    disabled: isLoading || isGeneratingChecklist || (showCreateForm && !policies.length),
    busy: isSaving || submittingSandbox,
    form: showCreateForm ? 'wizard-claim-form' : undefined,
    onClick: () => sandboxSuccess && selectedClaim ? router.push(`/claims?claim_id=${encodeURIComponent(selectedClaim.id)}`) : isWizard ? setConfirmSandbox(true) : selectedClaim ? router.push(`/claims?claim_id=${encodeURIComponent(selectedClaim.id)}&stage=review`) : setShowCreateForm(true),
  });
  const policyNames = useMemo(
    () => new Map(policies.map((policy) => [policy.policy_id, policy.document_name])),
    [policies]
  );
  const openClaimCount = claims.filter((claim) => !terminalStatuses.has(String(claim.status).toLowerCase())).length;

  const invalidateNewClaimGuidance = () => {
    setNewClaimGuidance(null);
    setChecklistGuidance('');
  };



  const handleGenerateChecklist = async () => {
    if (!form.policy_id) {
      setError('Choose a saved policy before requesting claim guidance.');
      return;
    }
    setIsGeneratingChecklist(true);
    setError(null);
    setChecklistGuidance('');
    if (!form.incident_date || form.incident_description.trim().length < 5) {
      setIsGeneratingChecklist(false);
      setError('Add the incident date and describe what happened before requesting guidance.');
      return;
    }
    const result = await evaluateIncidentGuidance({
      policy_id: form.policy_id,
      incident_date: form.incident_date,
      deadline_reference_date: deadlineReferenceDate || undefined,
      estimated_loss_cents: toDollars(form.estimated_loss) ?? undefined,
      incident_category: 'other',
      network_status: 'unsure',
      prior_auth_status: 'unsure',
      provided_document_titles: providedDocuments.split(',').map((title) => title.trim()).filter(Boolean),
      user_notes: [
        form.claim_type.trim() ? `Claim type: ${form.claim_type.trim()}.` : '',
        `Incident: ${form.incident_description.trim()}.`,
        form.incident_location.trim() ? `Location: ${form.incident_location.trim()}.` : '',
        form.estimated_loss.trim() ? `Estimated loss: ${form.estimated_loss.trim()}.` : '',
      ].filter(Boolean).join(' '),
    });
    setIsGeneratingChecklist(false);
    if (result.error || !result.data) {
      setError(result.error || 'Could not generate policy-based document guidance.');
      return;
    }

    setNewClaimGuidance(result.data);
    setGuidanceModal(result.data);
    setChecklistGuidance(result.data.readiness_summary);
    const items = result.data.document_checklist.map((item) => ({
      id: item.item_id,
      title: item.title,
      description: `${item.description}${item.why_needed ? ` ${item.why_needed}` : ''}`,
      mandatory: item.is_mandatory,
      completed: item.status === 'provided',
      source_clause_id: item.policy_citation?.clause_id,
    } satisfies ClaimChecklistItem));
    setNewChecklist(items);
    if (!items.length) {
      setNotice('The policy response did not cite an explicit document requirement. Review the answer and add only documents that apply to your situation.');
    }
  };

  const handleCreateClaim = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSaving) return;
    setError(null);
    if (!form.policy_id || !form.incident_date || form.incident_description.trim().length < 5) {
      setError('Select a policy and enter the incident date and description before saving the draft.');
      return;
    }
    const amount = toDollars(form.estimated_loss);
    if (form.estimated_loss.trim() && amount == null) {
      setError('Enter an estimated loss as a non-negative amount.');
      return;
    }

    setIsSaving(true);
    const result = await createClaimIntake({
      analysis_id: linkedAnalysis?.id,
      policy_id: form.policy_id,
      claim_type: form.claim_type.trim() || 'Insurance claim',
      incident_description: form.incident_description.trim(),
      incident_date: form.incident_date,
      incident_location: form.incident_location.trim() || undefined,
      estimated_loss_cents: amount,
      claim_reference: form.claim_reference.trim() || undefined,
      checklist: newChecklist,
    });
    if (result.error || !result.data) {
      setIsSaving(false);
      setError(result.error || 'Could not save the claim draft.');
      return;
    }

    let created = result.data;
    if (newChecklist.length) {
      const update = await updateClaimIntake(created.id, { checklist: newChecklist });
      if (update.data) created = update.data;
    }
    setIsSaving(false);
    setClaims((current) => [created, ...current.filter((claim) => claim.id !== created.id)]);
    remember({ policyId: created.policy_id, claimId: created.id, claimReady: true, analysisId: created.analysis_id || undefined, title: created.incident_description || 'Claim preparation', claimDraft: undefined });
    setSelectedClaimId(created.id);
    setClaimDetailsOpen(true);
    setEditForm({ ...form });
    setShowCreateForm(false);
    setForm(emptyForm());
    setLinkedAnalysis(null);
    setNewChecklist([]);
    setChecklistGuidance('');
    setNewClaimGuidance(null);
    setNotice('Claim draft saved. No information has been sent to an insurer.');
    setReviewMode(true);
    const stillOnDraft = !isWizard || (window.location.pathname === '/claims/new' && new URLSearchParams(window.location.search).get('step') === 'draft');
    if (isWizard && stillOnDraft) setConfirmSandbox(true);
    if (stillOnDraft) router.push(isWizard ? `${wizardHref('draft', { claimId: created.id, policyId: created.policy_id, analysisId: created.analysis_id || undefined })}&stage=review` : `/claims?claim_id=${encodeURIComponent(created.id)}&stage=review`, { scroll: false });
  };

  const saveClaim = async (updatedFields: Parameters<typeof updateClaimIntake>[1], successText: string): Promise<boolean> => {
    if (!selectedClaim) return false;
    setError(null);
    const result = await updateClaimIntake(selectedClaim.id, updatedFields);
    if (result.error || !result.data) {
      setError(result.error || 'Could not update the claim.');
      return false;
    }
    setClaims((current) => current.map((claim) => claim.id === result.data!.id ? result.data! : claim));
    setNotice(successText);
    return true;
  };

  const handleSandboxConfirm = async () => {
    if (!selectedClaim || !sandboxEligibility(String(selectedClaim.status)) || submittingSandbox) return;
    setSubmittingSandbox(true);
    setError(null);
    try {
      if (hasPendingReviewChanges) throw new Error('Save your edited details and statement before reviewing sandbox submission. Nothing was submitted.');
      const result = await submitClaimToSandbox(selectedClaim.id);
      if (!result.data || result.error) throw new Error(result.error || 'Sandbox submission could not finish.');
      setSandboxSuccess(`Claim ${selectedClaim.id} · ${result.data.outcome_status} (simulation)`);
      setConfirmSandbox(false);
      const refreshed = await fetchClaims();
      if (refreshed.data) setClaims(refreshed.data);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not submit to the sandbox.'); setConfirmSandbox(false); }
    finally { setSubmittingSandbox(false); }
  };

  const handleSaveEdits = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedClaim) return;
    if (editForm.claim_type.trim().length < 2 || !editForm.incident_date || editForm.incident_description.trim().length < 5) {
      setError('Enter a claim type, incident date, and incident description before saving.');
      return;
    }
    const estimated = toDollars(editForm.estimated_loss);
    if (editForm.estimated_loss.trim() && estimated == null) {
      setError('Enter an estimated loss as a non-negative amount.');
      return;
    }
    setIsSavingEdits(true);
    const saved = await saveClaim({
      claim_type: editForm.claim_type.trim(),
      incident_date: editForm.incident_date,
      incident_location: editForm.incident_location.trim() || undefined,
      incident_description: editForm.incident_description.trim(),
      estimated_loss_cents: estimated,
      claim_reference: editForm.claim_reference.trim() || null,
    }, 'Claim draft updated.');
    setIsSavingEdits(false);
    if (saved) setEditModalOpen(false);
  };

  const handleGetClaimGuidance = async () => {
    if (!selectedClaim) return;
    setError(null);
    setClaimGuidanceError('');
    setGuidanceLoadingFor(selectedClaim.id);
    const result = await fetchClaimGuidance(selectedClaim.id);
    setGuidanceLoadingFor(null);
    if (result.error || !result.data) {
      setClaimGuidanceError(result.error || 'Could not generate claims guidance.');
      return;
    }
    setClaimGuidance((current) => ({ ...current, [selectedClaim.id]: result.data! }));
    setGuidanceModal(result.data);
    const existing = selectedClaim.checklist || [];
    const items = result.data.document_checklist.filter(item => !existing.some(c => c.id === item.item_id)).map(item => ({
      id: item.item_id, title: item.title, description: item.description,
      mandatory: item.is_mandatory, completed: item.status === 'provided', source_clause_id: item.policy_citation?.clause_id,
    }));
    await saveClaim({ checklist: [...existing, ...items] }, 'Policy checklist updated.');
  };

  const handleChecklistToggle = async (item: ClaimChecklistItem) => {
    if (!selectedClaim) return;
    const checklist = (selectedClaim.checklist || []).map((entry) =>
      entry.id === item.id ? { ...entry, completed: !entry.completed } : entry
    );
    await saveClaim({ checklist }, 'Checklist progress saved.');
  };

  const handleAddNewChecklistItem = () => {
    const title = manualChecklistTitle.trim();
    if (!title) {
      setError('Enter a document or information item before adding it.');
      return;
    }
    setError(null);
    setNewChecklist((items) => [...items, {
      id: createChecklistItemId(),
      title,
      description: 'Added by the member.',
      mandatory: false,
      completed: false,
    }]);
    setManualChecklistTitle('');
  };

  const handleAddChecklistItem = async (event: React.FormEvent<HTMLFormElement>): Promise<boolean> => {
    event.preventDefault();
    if (!selectedClaim) return false;
    const title = manualChecklistTitle.trim();
    if (!title) {
      setError('Enter a document or information item before adding it.');
      return false;
    }
    const checklist = [...(selectedClaim.checklist || []), {
      id: createChecklistItemId(),
      title,
      description: 'Added by the member.',
      mandatory: false,
      completed: false,
    }];
    setManualChecklistTitle('');
    return saveClaim({ checklist }, 'Checklist item added.');
  };

  const handleAttachFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !selectedClaim) return;
    setIsUploadingDocument(true);
    setError(null);
    const result = await uploadClaimDocument(selectedClaim.id, file);
    setIsUploadingDocument(false);
    if (result.error || !result.data) {
      setError(result.error || 'Could not upload the document.');
      return;
    }
    setClaims((current) => current.map((claim) => claim.id === result.data!.id ? result.data! : claim));
    setNotice('Evidence uploaded and attached to this claim.');
    setUploadModalOpen(false);
  };

  const handleDownloadDocument = async (fileMeta: ClaimDocumentMeta) => {
    if (!selectedClaim) return;
    const result = await downloadClaimDocument(selectedClaim.id, fileMeta.id);
    if (result.error || !result.data) {
      setError(result.error || 'Could not download this document.');
      return;
    }
    const url = URL.createObjectURL(result.data);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileMeta.file_name;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const selectedRequirements = selectedClaim?.checklist || [];
  const requiresSignIn = Boolean(error && /401|unauthorized|authentication required|bearer token/i.test(error));
  const checklistComplete = selectedRequirements.every((item) => item.completed);
  const missingDetailPrompts = selectedClaim ? [
    !selectedClaim.incident_description?.trim() && 'What happened?',
    !selectedClaim.incident_location && 'Where did it happen?',
    selectedClaim.estimated_loss_cents == null && !selectedClaim.total_billed_cents && 'What is the estimated loss?',
  ].filter(Boolean) as string[] : [];
  const incidentDateIsFuture = Boolean(selectedClaim?.incident_date && new Date(`${selectedClaim.incident_date}T00:00:00`) > new Date(new Date().toDateString()));
  const readyForReview = Boolean(
    selectedClaim?.claim_type && selectedClaim.incident_date && selectedClaim.incident_description?.trim() &&
    checklistComplete && !missingDetailPrompts.length && !incidentDateIsFuture && policyNames.has(selectedClaim.policy_id)
  );
  const hasPendingReviewChanges = Boolean(selectedClaim && (
    descriptionDraft !== (selectedClaim.claim_description_draft || '') ||
    editForm.incident_description !== (selectedClaim.incident_description || '') ||
    editForm.incident_date !== String(selectedClaim.incident_date || '').slice(0, 10) ||
    editForm.incident_location !== (selectedClaim.incident_location || '') ||
    editForm.claim_type !== (selectedClaim.claim_type || 'Medical claim') ||
    editForm.claim_reference !== (selectedClaim.claim_reference || '') ||
    toDollars(editForm.estimated_loss) !== (selectedClaim.estimated_loss_cents ?? (selectedClaim.total_billed_cents > 0 ? selectedClaim.total_billed_cents : null))
  ));
  const canSubmitSandbox = Boolean(selectedClaim && sandboxEligibility(String(selectedClaim.status)) && !hasPendingReviewChanges);
  const sandboxDescription = !selectedClaim
    ? 'Save a claim draft before sandbox submission can be reviewed. No information will be sent to an insurer. The current backend accepts only previously analyzed claims in its local simulation.'
    : !sandboxEligibility(String(selectedClaim.status))
      ? `Claim ${selectedClaim.id} is saved with status “${statusLabel(selectedClaim)}”. The sandbox requires an analyzed claim. This draft has not met that backend requirement, so submission is unavailable. No information is sent to an insurer.`
      : hasPendingReviewChanges
        ? 'Save the edited incident details and draft statement first. The backend will recheck preparation status after saving; sandbox eligibility may change. Nothing has been submitted.'
        : `Confirm simulated submission of claim ${selectedClaim.id}? This uses the local sandbox only. It does not send a claim to your insurer, and its response is not a real coverage or approval decision.`;

  return (
    <main data-wizard-creating={isWizard && showCreateForm || undefined} className="app-page claims-page mx-auto max-w-7xl space-y-7 px-4 py-7 sm:px-7 sm:py-9 lg:px-10">
      <ConfirmDialog isOpen={confirmSandbox} title="Sandbox submission" description={sandboxDescription} confirmLabel="Confirm sandbox submission" cancelLabel="Back to draft" variant="sandbox" canConfirm={canSubmitSandbox} isProcessing={submittingSandbox} onCancel={() => setConfirmSandbox(false)} onConfirm={() => void handleSandboxConfirm()} />
      {sandboxSuccess && <section role="status" className="wizard-success wizard-toast"><CheckCircle2 size={19} /><div><p>{sandboxSuccess}</p><Link className="underline" href={`/claims?claim_id=${encodeURIComponent(selectedClaimId)}`}>View in My claims</Link><p className="text-xs">Sandbox response only. Nothing was sent to an insurer.</p></div></section>}
      {isWizard && <button type="button" className="text-xs text-teal-800 underline underline-offset-4" onClick={() => setConfirmSandbox(true)}>About sandbox submission</button>}
      {reviewMode && selectedClaim && <section className="rounded-2xl border border-teal-200 bg-teal-50 p-5"><p className="text-[10px] font-semibold uppercase tracking-widest text-teal-800">Draft saved · Final preparation step</p><h2 className="mt-2 text-lg font-semibold text-slate-900">Everything in one place, ready for your review.</h2><p className="mt-2 text-sm leading-6 text-slate-600">Check the incident details, document checklist, evidence and description below. You can keep editing this saved draft. No claim has been submitted.</p><Link href="/dashboard" className="mt-4 inline-block text-xs font-semibold text-teal-800">Return to overview →</Link></section>}
      {showCreateForm && linkedAnalysis && <AnalysisContext analysis={linkedAnalysis} />}
      <PageHero
        currentPage="My Claims"
        illustrated={{ eyebrow: 'My Claims', firstLine: 'Your claim, organized.', secondLine: 'Your next step, clear.', variant: 'claims' }}
        title="My Claims"
        description="Track every claim, see AI-prepared drafts, and follow next steps grounded in your policy clauses."
        stats={[
          { label: 'Total', value: isLoading || requiresSignIn ? '—' : claims.length },
          { label: 'In progress', value: isLoading || requiresSignIn ? '—' : openClaimCount },
          { label: 'Approved', value: isLoading || requiresSignIn ? '—' : claims.filter((claim) => String(claim.status).toLowerCase() === 'approved').length },
        ]}
        rightSlot={
          <div className="flex flex-wrap gap-2">
            {!isWizard && scenario.lastStep && <Link data-wizard-resume href={wizardHref(scenario.lastStep)} className="inline-flex min-h-10 items-center gap-2 rounded-full border border-teal-200 bg-white/80 px-3 text-xs font-semibold text-teal-900">Continue preparation</Link>}
            <button type="button" onClick={() => void loadWorkspace()} className="inline-flex min-h-10 items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 text-xs font-semibold text-slate-700 hover:bg-white">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </button>
            <button type="button" onClick={() => { setShowCreateForm(true); setError(null); }} className="inline-flex min-h-10 items-center gap-2 rounded-full bg-[#12294A] px-4 text-xs font-semibold text-white hover:bg-[#1c3a64]">
              <Plus className="h-4 w-4" /> New claim
            </button>
          </div>
        }
      />

      {error && <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{requiresSignIn ? 'Sign in to view your saved claims and prepare a draft.' : error}</div>}
      {notice && <div role="status" className="flex items-start justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"><span className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />{notice}</span><button onClick={() => setNotice(null)} aria-label="Dismiss notice"><X className="h-4 w-4" /></button></div>}

      <GlassModal
        open={showCreateForm}
        onClose={() => setShowCreateForm(false)}
        title="New claim"
        description="Enter the incident details and review policy-based guidance before saving your draft."
        footer={<>
          <button type="button" className="glass-modal-action glass-modal-action-secondary" onClick={() => setShowCreateForm(false)}>Cancel</button>
          <button type="submit" form="wizard-claim-form" disabled={isSaving || !policies.length} aria-busy={isSaving || undefined} className="glass-modal-action glass-modal-action-primary">
            {isSaving && <LoaderCircle className="h-4 w-4 animate-spin" />}{isSaving ? 'Saving claim…' : 'Save claim'}
          </button>
        </>}
      >
      {showCreateForm && (
        <section className="rounded-2xl border border-white bg-white/85 p-5 shadow-md backdrop-blur-md sm:p-6 cw-glass">
          {error && <p role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{error}</p>}
          <div className="mb-5 flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-800"><FilePlus2 className="h-5 w-5" /></span>
            <div><h2 className="font-semibold text-slate-900">AI assisted claim guidance</h2><p className="mt-1 text-xs leading-5 text-slate-600">Tell us what happened and choose the closest care details. ClaimWise checks your answers against the selected policy and explains the result.</p></div>
          </div>

          {policies.length === 0 ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              Upload a policy before creating a policy-linked claim. <Link href="/policies" className="font-semibold underline">Go to My Policies</Link>
            </div>
          ) : (
            <form id="wizard-claim-form" onSubmit={handleCreateClaim} className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1.5 text-xs font-semibold text-slate-700">Related policy
                  <select required value={form.policy_id} onChange={(event) => { invalidateNewClaimGuidance(); setForm({ ...form, policy_id: event.target.value }); }} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm font-normal outline-none focus:border-teal-600">
                    <option value="">Choose a saved policy</option>
                    {policies.filter((policy) => policy.policy_id).map((policy) => <option key={policy.policy_id} value={policy.policy_id || ''}>{policy.document_name}</option>)}
                  </select>
                </label>
                <label className="space-y-1.5 text-xs font-semibold text-slate-700">Claim type <span className="font-normal text-slate-500">(optional before policy guidance)</span>
                  <input maxLength={100} value={form.claim_type} onChange={(event) => { invalidateNewClaimGuidance(); setForm({ ...form, claim_type: event.target.value }); }} placeholder="Leave blank and ClaimWise will look for relevant policy clauses" className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-teal-600" />
                </label>
                <label className="space-y-1.5 text-xs font-semibold text-slate-700">Incident date
                  <input required type="date" value={form.incident_date} onChange={(event) => { invalidateNewClaimGuidance(); setForm({ ...form, incident_date: event.target.value }); }} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-teal-600" />
                </label>
                <label className="space-y-1.5 text-xs font-semibold text-slate-700">Trip return date <span className="font-normal text-slate-500">(if applicable)</span>
                  <input type="date" value={deadlineReferenceDate} onChange={(event) => { invalidateNewClaimGuidance(); setDeadlineReferenceDate(event.target.value); }} className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-teal-600" />
                  <span className="block font-normal text-slate-500">Used only if the policy says the filing period starts when you return.</span>
                </label>
                <label className="space-y-1.5 text-xs font-semibold text-slate-700">Claim reference (optional)
                  <input maxLength={100} value={form.claim_reference} onChange={(event) => setForm({ ...form, claim_reference: event.target.value })} placeholder="Your existing reference, if assigned" className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-teal-600" />
                </label>
                <label className="space-y-1.5 text-xs font-semibold text-slate-700">Where did it happen?
                  <input value={form.incident_location} onChange={(event) => { invalidateNewClaimGuidance(); setForm({ ...form, incident_location: event.target.value }); }} placeholder="City, facility, or other location" className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-teal-600" />
                </label>
                <label className="space-y-1.5 text-xs font-semibold text-slate-700 sm:col-span-2">What happened?
                  <textarea required minLength={5} maxLength={5000} rows={4} value={form.incident_description} onChange={(event) => { invalidateNewClaimGuidance(); setForm({ ...form, incident_description: event.target.value }); }} placeholder="Describe the incident in your own words. Include only details you know." className="w-full resize-y rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-teal-600" />
                </label>
                <label className="space-y-1.5 text-xs font-semibold text-slate-700">Estimated loss (optional)
                  <input inputMode="decimal" value={form.estimated_loss} onChange={(event) => setForm({ ...form, estimated_loss: event.target.value })} placeholder="Amount, if known" className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-teal-600" />
                </label>
              </div>

              {(!form.incident_location || !form.estimated_loss.trim()) && <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-900"><p className="font-semibold">Follow-up details that may help</p><ul className="mt-1 list-inside list-disc">{!form.incident_location && <li>Where did the incident take place?</li>}{!form.estimated_loss.trim() && <li>Do you know the approximate loss amount?</li>}</ul><p className="mt-1 text-amber-800">You can save the draft without these answers and add them later.</p></div>}

              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div><h3 className="text-sm font-semibold text-slate-900">What might this policy let you claim?</h3><p className="mt-1 text-xs text-slate-600">Choose the policy and describe what happened. ClaimWise will find related clauses in that PDF and show the possible claim basis to review.</p></div>
                  <button type="button" onClick={() => void handleGenerateChecklist()} disabled={isGeneratingChecklist || !form.policy_id} className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-teal-200 bg-white px-3 text-xs font-semibold text-teal-900 hover:bg-teal-50 disabled:opacity-50">
                    {isGeneratingChecklist ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                    {isGeneratingChecklist ? 'Reviewing your policy…' : newClaimGuidance ? 'Refresh claim guidance' : 'Get claim guidance'}
                  </button>
                </div>
                <label className="mt-4 block text-xs font-medium text-slate-700">Documents or evidence you already have <span className="font-normal text-slate-500">(optional; separate items with commas)</span><input value={providedDocuments} onChange={(event) => { invalidateNewClaimGuidance(); setProvidedDocuments(event.target.value); }} placeholder="e.g. repair estimate, police report, receipts" className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs" /></label>
                {newClaimGuidance && <button type="button" onClick={() => { setShowCreateForm(false); setReopenCreateAfterGuidance(true); setGuidanceModal(newClaimGuidance); }} className="mt-4 flex w-full items-center justify-between rounded-lg border border-teal-200 bg-white p-3 text-left text-xs hover:bg-teal-50"><span><strong className="block text-teal-900">Policy guidance is ready</strong><span className="mt-0.5 block text-slate-600">View the readable summary, possible related clauses, deadline, and documents.</span></span><span className="font-semibold text-teal-800">Open guidance</span></button>}
                {newClaimGuidance && <div className="hidden mt-4 space-y-3 rounded-xl border border-teal-200 bg-white p-4">
                    <div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-900">Preparation score {newClaimGuidance.readiness_score_pct}%</span><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{newClaimGuidance.risk_level.replace('_', ' ')}</span><span className="text-xs text-slate-600">Based on: {newClaimGuidance.policy_name}</span></div>
                  <div className="rounded-lg border border-teal-100 bg-teal-50/50 p-3"><p className="text-xs font-semibold text-teal-950">Possible claim basis from this policy</p><p className="mt-1 text-xs leading-5 text-slate-700">{newClaimGuidance.potential_claim_clauses.length ? 'These exact policy sections relate to the incident you described. They may help identify what to ask the insurer to assess; they do not confirm that your loss is covered.' : 'I could not find a policy clause that clearly relates to this incident. Check the policy PDF or ask the insurer which benefit applies.'}</p>{newClaimGuidance.potential_claim_clauses.length > 0 && <ul className="mt-2 space-y-2">{newClaimGuidance.potential_claim_clauses.map((citation) => <li key={`claim-basis-${citation.clause_id}`} className="rounded-md border border-teal-100 bg-white p-2.5 text-xs"><p className="font-semibold text-teal-900">{citation.clause_heading || `Clause ${citation.clause_id}`} · page {citation.page_number}</p><p className="mt-1 whitespace-pre-wrap leading-5 text-slate-600">{citation.exact_quote}</p></li>)}</ul>}</div>
                  <p className="text-xs leading-5 text-slate-700">{newClaimGuidance.readiness_summary}</p>
                  {newClaimGuidance.timely_filing.warning_message ? <p className="rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900">{newClaimGuidance.timely_filing.warning_message}</p> : <p className="text-xs text-slate-500">No explicit claim filing deadline was identified in this PDF.</p>}
                  {newClaimGuidance.obstacles.length > 0 && <div><p className="text-xs font-semibold text-slate-800">Things to check</p><ul className="mt-1 space-y-2">{newClaimGuidance.obstacles.map((obstacle) => <li key={obstacle.id} className="rounded-lg border border-amber-100 bg-amber-50/50 p-3 text-xs"><p className="font-semibold text-slate-800">{obstacle.title}</p><p className="mt-1 leading-5 text-slate-600">{obstacle.description} {obstacle.mitigation_strategy}</p>{obstacle.citation && <p className="mt-1 text-[10px] text-teal-800">Policy clause: {obstacle.citation.clause_id}</p>}</li>)}</ul></div>}
                  {newClaimGuidance.action_plan_steps.length > 0 && <div><p className="text-xs font-semibold text-slate-800">What to do next</p><ol className="mt-1 list-inside list-decimal space-y-1 text-xs leading-5 text-slate-700">{newClaimGuidance.action_plan_steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol></div>}
                  {newClaimGuidance.verified_citations.length > 0 && <div><p className="text-xs font-semibold text-slate-800">Clauses from this PDF</p><ul className="mt-1 space-y-2">{newClaimGuidance.verified_citations.map((citation) => <li key={citation.clause_id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs"><p className="font-semibold text-teal-900">{citation.clause_heading || `Clause ${citation.clause_id}`} · page {citation.page_number}</p><p className="mt-1 whitespace-pre-wrap leading-5 text-slate-600">{citation.exact_quote}</p></li>)}</ul></div>}
                  <p className="border-t border-slate-100 pt-2 text-[10px] leading-4 text-slate-500">{newClaimGuidance.disclaimer} Guidance helps you prepare and does not promise coverage or approval.</p>
                </div>}
                {checklistGuidance && <div className="mt-4 rounded-lg border border-teal-100 bg-white p-3 text-xs leading-5 text-slate-700"><p className="mb-1 font-semibold text-teal-900">Document checklist for this claim</p><p className="whitespace-pre-wrap">{checklistGuidance}</p></div>}
                {newChecklist.length > 0 && <ul className="mt-3 space-y-2">{newChecklist.map((item) => <li key={item.id} className="flex items-start gap-2 text-xs text-slate-700"><FileCheck2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" /><span><strong>{item.title}</strong>{item.mandatory ? ' · stated as required' : ' · policy reference to review'}<span className="block text-slate-500">{item.description} {item.source_clause_id && `(${item.source_clause_id})`}</span></span></li>)}</ul>}
                <div className="mt-3 flex flex-wrap gap-2">
                  <input value={manualChecklistTitle} onChange={(event) => setManualChecklistTitle(event.target.value)} placeholder="Add a document or information item" aria-label="Document or information item" className="min-h-9 min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-xs outline-none focus:border-teal-600" />
                  <button type="button" onClick={handleAddNewChecklistItem} className="rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-100">Add item</button>
                </div>
              </div>

            </form>
          )}
        </section>
      )}
      </GlassModal>

      <section className={`claims-workspace-grid grid items-start gap-5 ${isWizard ? 'lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]' : ''}`}>
        <GlassPanel as="div" className="cw-claims-list rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5 cw-glass">
          <div className="mb-4 flex items-center justify-between gap-3"><div><h2 className="font-semibold text-slate-900">All claims</h2><p className="mt-1 text-xs text-slate-500">Claims saved to your account.</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">{requiresSignIn ? '—' : claims.length}</span></div>
          {isLoading ? <div role="status" aria-label="Loading claims" className="space-y-3">{[1, 2, 3].map((item) => <Skeleton key={item} className="h-24" />)}</div> : claims.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 px-5 py-8 text-center">
              <FileText className="mx-auto h-8 w-8 text-slate-400" />
              <p className="mt-3 text-sm font-semibold text-slate-800">{requiresSignIn ? 'Sign in to view your claims' : 'No saved claims yet'}</p>
              <p className="mt-1 text-xs text-slate-500">{requiresSignIn ? 'Your saved claim records are private to your account.' : 'Create a claim draft to start tracking details and supporting evidence.'}</p>
              <button type="button" onClick={() => setShowCreateForm(true)} className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-teal-800 px-3 py-2 text-xs font-semibold text-white"><Plus className="h-3.5 w-3.5" /> Create a claim</button>
            </div>
          ) : <div className="space-y-2.5">{claims.map((claim) => (
            <button key={claim.id} type="button" onClick={() => { selectClaim(claim); setClaimDetailsOpen(true); }} aria-haspopup="dialog" aria-pressed={selectedClaimId === claim.id} className={`cw-glass w-full rounded-xl border p-3.5 text-left transition hover:border-teal-300 hover:bg-teal-50/30 ${selectedClaimId === claim.id ? 'border-teal-400 bg-teal-50/40 ring-1 ring-teal-100' : 'border-slate-200 bg-white'}`}>
              <div className="flex flex-wrap items-start justify-between gap-3"><span className="min-w-0 truncate text-sm font-semibold text-slate-900">{claim.claim_type || (claim.bill_document_name ? 'Medical claim' : 'Claim')}</span><span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-semibold ${statusClasses(claim)}`}><FileCheck2 size={13} aria-hidden="true" />{statusLabel(claim)}</span></div>
              <p className="mt-1 truncate text-xs text-slate-600">{policyNames.get(claim.policy_id) || 'Policy details unavailable'}</p>
              <div className="mt-3 grid grid-cols-2 gap-x-2 gap-y-1 text-[10px] text-slate-500">
                <span>Incident: {displayDate(String(claim.incident_date))}</span><span>Updated: {displayDate(claim.updated_at)}</span>
                <span className="col-span-2 truncate">Reference: {claim.claim_reference || 'Not assigned'}</span>
              </div>
            </button>
          ))}</div>}
        </GlassPanel>

        <ClaimDetailsPanel inline={isWizard} open={claimDetailsOpen && Boolean(selectedClaim)} onClose={() => setClaimDetailsOpen(false)}>
          {!selectedClaim ? (
            <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/60 p-8 text-center cw-glass">
              <FileCheck2 className="h-9 w-9 text-slate-400" /><p className="mt-3 text-sm font-semibold text-slate-800">Select a claim to review</p><p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">Review and edit its incident details, checklist, uploaded evidence, and progress timeline.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {selectedClaim.coverage_analysis && <AnalysisContext analysis={selectedClaim.coverage_analysis} />}
              <Link className="text-xs font-semibold text-teal-800" href={selectedClaim.analysis_id ? `${analysisLink('workspace', selectedClaim.analysis_id)}&claim_id=${encodeURIComponent(selectedClaim.id)}` : `/workspace?policy_id=${encodeURIComponent(selectedClaim.policy_id)}&claim_id=${encodeURIComponent(selectedClaim.id)}`}>Ask ClaimWise about this claim</Link>
              <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3 cw-glass">
                <h3 className="font-semibold">Claim description draft</h3>
                <p className="text-xs text-slate-600">Review every fact and edit this AI-assisted draft before using it. No claim is submitted here.</p>
                <button type="button" onClick={() => setDescriptionModalOpen(true)} className="glass-modal-action glass-modal-action-secondary">Open draft editor</button>
              </section>
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm cw-glass">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><p className="text-[10px] font-semibold uppercase tracking-wider text-teal-800">Claim draft</p><h2 className="mt-1 text-lg font-semibold text-slate-900">{selectedClaim.claim_type || 'Claim'}</h2><p className="mt-1 text-xs text-slate-500">{selectedClaim.claim_reference || selectedClaim.id}</p></div>
                  <div className="flex items-center gap-2"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClasses(selectedClaim)}`}>{statusLabel(selectedClaim)}</span><button type="button" onClick={() => setEditModalOpen(true)} className="glass-modal-action glass-modal-action-secondary">Edit claim</button></div>
                </div>
                <p className="mt-4 text-xs text-slate-600">Policy: {policyNames.get(selectedClaim.policy_id) || 'Unavailable'}</p>
                <dl className="grid gap-4 border-t border-slate-100 pt-4 text-sm sm:grid-cols-2">
                  <div><dt className="text-xs text-slate-500">Incident date</dt><dd className="mt-1 text-slate-800">{displayDate(String(selectedClaim.incident_date))}</dd></div>
                  <div><dt className="text-xs text-slate-500">Location</dt><dd className="mt-1 text-slate-800">{selectedClaim.incident_location || 'Not provided'}</dd></div>
                  <div className="sm:col-span-2"><dt className="text-xs text-slate-500">What happened</dt><dd className="mt-1 whitespace-pre-wrap leading-6 text-slate-800">{selectedClaim.incident_description || 'Not provided'}</dd></div>
                </dl>
              </section>

              <section className="rounded-2xl border border-teal-200 bg-teal-50/50 p-5 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div><h3 className="font-semibold text-slate-900">Claims guidance</h3><p className="mt-1 text-xs leading-5 text-slate-600">Check this claim against its saved policy for filing deadlines, possible obstacles, and supporting documents.</p></div>
                  <button type="button" onClick={() => void handleGetClaimGuidance()} disabled={guidanceLoadingFor === selectedClaim.id} className="inline-flex min-h-9 items-center gap-2 rounded-lg bg-teal-800 px-3 text-xs font-semibold text-white hover:bg-teal-900 disabled:opacity-60">
                    {guidanceLoadingFor === selectedClaim.id && <LoaderCircle className="h-4 w-4 animate-spin" />}{guidanceLoadingFor === selectedClaim.id ? 'Checking policy…' : claimGuidance[selectedClaim.id] ? 'Refresh guidance' : 'Get claim guidance'}
                  </button>
                </div>
                {claimGuidanceError && <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{claimGuidanceError}</p>}
                {claimGuidance[selectedClaim.id] && <button type="button" onClick={() => setGuidanceModal(claimGuidance[selectedClaim.id])} className="mt-4 flex w-full items-center justify-between rounded-lg border border-teal-200 bg-white p-3 text-left text-xs hover:bg-teal-50"><span><strong className="block text-teal-900">Policy guidance is ready</strong><span className="mt-0.5 block text-slate-600">View the readable summary, possible related clauses, deadline, and documents.</span></span><span className="font-semibold text-teal-800">Open guidance</span></button>}
                {claimGuidance[selectedClaim.id] && (() => {
                  const guidance = claimGuidance[selectedClaim.id];
                  return <div className="hidden mt-4 space-y-3">
                    <div className="flex flex-wrap items-center gap-2"><span className="rounded-full border border-teal-200 bg-white px-2.5 py-1 text-xs font-semibold text-teal-900">Preparation score {guidance.readiness_score_pct}%</span><span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700">{guidance.risk_level.replace('_', ' ')}</span>{guidance.timely_filing.filing_deadline_date ? <span className="text-xs text-slate-600">Policy filing deadline: {displayDate(guidance.timely_filing.filing_deadline_date)} · {guidance.timely_filing.days_remaining} days remaining</span> : <span className="text-xs text-slate-600">No explicit filing deadline found in the policy PDF</span>}</div>
                    <div className="rounded-lg border border-teal-100 bg-teal-50/50 p-3"><p className="text-xs font-semibold text-teal-950">Possible claim basis from this policy</p><p className="mt-1 text-xs leading-5 text-slate-700">{guidance.potential_claim_clauses.length ? 'These exact policy sections relate to the incident details on this claim. They may help identify what to ask the insurer to assess; they do not confirm coverage.' : 'I could not find a policy clause that clearly relates to this incident. Check the policy PDF or ask the insurer which benefit applies.'}</p>{guidance.potential_claim_clauses.length > 0 && <ul className="mt-2 space-y-2">{guidance.potential_claim_clauses.map((citation) => <li key={`claim-basis-${citation.clause_id}`} className="rounded-md border border-teal-100 bg-white p-2.5 text-xs"><p className="font-semibold text-teal-900">{citation.clause_heading || `Clause ${citation.clause_id}`} · page {citation.page_number}</p><p className="mt-1 whitespace-pre-wrap leading-5 text-slate-600">{citation.exact_quote}</p></li>)}</ul>}</div>
                    <p className="text-xs leading-5 text-slate-700">{guidance.readiness_summary}</p>
                    {guidance.obstacles.length > 0 && <div><p className="text-xs font-semibold text-slate-800">Items to review</p><ul className="mt-1 space-y-2">{guidance.obstacles.map((obstacle) => <li key={obstacle.id} className="rounded-lg border border-amber-200 bg-white p-3 text-xs"><p className="font-semibold text-slate-800">{obstacle.title}</p><p className="mt-1 leading-5 text-slate-600">{obstacle.description} {obstacle.mitigation_strategy}</p>{obstacle.citation && <p className="mt-1 text-[10px] text-teal-800">Policy: {obstacle.citation.clause_id}</p>}</li>)}</ul></div>}
                    {guidance.document_checklist.length > 0 && <div><p className="text-xs font-semibold text-slate-800">Suggested documents</p><ul className="mt-1 space-y-1">{guidance.document_checklist.map((item) => <li key={item.item_id} className="flex items-start gap-2 rounded-lg border border-slate-200 bg-white p-2.5 text-xs text-slate-700"><FileCheck2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-700" /><span><span className="font-semibold">{item.title}</span><span className="block mt-0.5 text-slate-500">{item.description}{item.policy_citation && ` · Policy clause ${item.policy_citation.clause_id}`}</span></span></li>)}</ul></div>}
                    {guidance.action_plan_steps.length > 0 && <div><p className="text-xs font-semibold text-slate-800">Next steps</p><ol className="mt-1 list-inside list-decimal space-y-1 text-xs leading-5 text-slate-700">{guidance.action_plan_steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol></div>}
                    {guidance.verified_citations.length > 0 && <div><p className="text-xs font-semibold text-slate-800">Clauses from this PDF</p><ul className="mt-1 space-y-2">{guidance.verified_citations.map((citation) => <li key={citation.clause_id} className="rounded-lg border border-slate-200 bg-white p-3 text-xs"><p className="font-semibold text-teal-900">{citation.clause_heading || `Clause ${citation.clause_id}`} · page {citation.page_number}</p><p className="mt-1 whitespace-pre-wrap leading-5 text-slate-600">{citation.exact_quote}</p></li>)}</ul></div>}
                    <p className="border-t border-teal-100 pt-2 text-[10px] leading-4 text-slate-500">{guidance.disclaimer} This is preparation guidance and does not guarantee coverage or approval.</p>
                  </div>;
                })()}
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm cw-glass">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-slate-900">Documents & readiness</h3><p className="mt-1 text-xs text-slate-500">Mark checklist items complete when you have the information or evidence.</p></div><button type="button" onClick={() => setUploadModalOpen(true)} disabled={isUploadingDocument} className={`inline-flex min-h-9 items-center gap-2 rounded-lg border px-3 text-xs font-semibold ${isUploadingDocument ? 'border-slate-200 bg-slate-100 text-slate-500' : 'border-teal-200 bg-white text-teal-900 hover:bg-teal-50'}`}><UploadCloud className="h-4 w-4" />{isUploadingDocument ? 'Uploading…' : 'Upload evidence'}</button></div>
                {selectedRequirements.length ? <div className="mt-4 space-y-2">{selectedRequirements.map((item) => <label key={item.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50"><input type="checkbox" checked={item.completed} onChange={() => void handleChecklistToggle(item)} className="mt-0.5 h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-teal-600" /><span className="min-w-0 flex-1"><span className={`text-xs font-semibold ${item.completed ? 'text-emerald-800' : 'text-slate-800'}`}>{item.title}{item.mandatory && <span className="ml-1 text-[10px] font-medium text-rose-700">Required by cited clause</span>}</span>{item.description && <span className="mt-1 block text-[11px] leading-5 text-slate-500">{item.description}</span>}{item.source_clause_id && <span className="mt-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">{item.source_clause_id}</span>}</span></label>)}</div> : <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">No policy checklist has been generated. Create a policy-based checklist from the new claim form, or add an item below.</p>}
                <button type="button" onClick={() => setChecklistModalOpen(true)} className="mt-3 glass-modal-action glass-modal-action-secondary">Add checklist item</button>
                {selectedClaim.documents?.length ? <div className="mt-4 border-t border-slate-100 pt-3"><p className="mb-2 text-xs font-semibold text-slate-700">Uploaded evidence</p><ul className="space-y-2">{selectedClaim.documents.map((document) => <li key={document.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2"><span className="min-w-0 truncate text-xs text-slate-700">{document.file_name}<span className="ml-2 text-[10px] text-slate-400">{Math.max(1, Math.round(document.file_size_bytes / 1024))} KB</span></span><button type="button" onClick={() => void handleDownloadDocument(document)} aria-label={`Download ${document.file_name}`} className="shrink-0 rounded-md p-1.5 text-slate-500 hover:bg-white hover:text-teal-800"><ArrowDownToLine className="h-4 w-4" /></button><button type="button" className="text-xs text-rose-700" onClick={async () => {
                  try { const updated = await workflowRequest<ClaimRecord>(`claims/${encodeURIComponent(selectedClaim.id)}/documents/${encodeURIComponent(document.id)}`, 'DELETE'); setClaims(current => current.map(c => c.id === updated.id ? updated : c)); setNotice('Evidence removed. Review checklist completion.'); }
                  catch (error) { setError(error instanceof Error ? error.message : 'Could not remove document.'); }
                }}>Remove</button></li>)}</ul></div> : null}
                <div className={`mt-4 flex items-start gap-2 rounded-lg border p-3 text-xs ${readyForReview ? 'border-teal-200 bg-teal-50 text-teal-900' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
                  {readyForReview ? <Check className="mt-0.5 h-4 w-4 shrink-0" /> : <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />}
                  <div><p className="font-semibold">{readyForReview ? 'Preparation looks complete' : 'Still preparing this claim'}</p><p className="mt-1 leading-5">{incidentDateIsFuture ? 'The incident date is in the future; confirm or correct it.' : !policyNames.has(selectedClaim.policy_id) ? 'The related policy is no longer available in this account.' : missingDetailPrompts.length ? `Add these details: ${missingDetailPrompts.join(' ')}` : selectedRequirements.some((item) => !item.completed) ? 'Complete the document and information checklist before considering submission.' : readyForReview ? 'This checks for preparation gaps only. It does not predict or promise an insurer decision.' : 'Review the incident details and document checklist for anything still missing.'}</p></div>
                </div>
                <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600">No insurer submission integration is configured. This workspace saves and prepares your claim only. It will not transmit a claim or show an insurer status unless a supported integration supplies one.</p>
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm cw-glass">
                <div className="mb-4 flex items-center gap-2"><Clock3 className="h-4 w-4 text-teal-700" /><div><h3 className="font-semibold text-slate-900">Claim progress</h3><p className="mt-1 text-xs text-slate-500">Internal preparation events are separated from insurer-confirmed events.</p></div></div>
                <ol className="space-y-4">{getTimeline(selectedClaim).map((event) => <li key={event.id} className="relative flex gap-3"><span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${event.source === 'insurer' ? 'bg-emerald-100 text-emerald-800' : event.source === 'simulation' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'}`}>{event.source === 'insurer' ? <ShieldCheck className="h-4 w-4" /> : event.source === 'simulation' ? <CircleAlert className="h-4 w-4" /> : <Clock3 className="h-4 w-4" />}</span><span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-800">{event.summary}<span className={`rounded-full px-1.5 py-0.5 text-[9px] uppercase tracking-wide ${event.source === 'insurer' ? 'bg-emerald-50 text-emerald-800' : event.source === 'simulation' ? 'bg-amber-50 text-amber-800' : 'bg-slate-100 text-slate-500'}`}>{event.source === 'insurer' ? 'Insurer confirmed' : event.source === 'simulation' ? 'Simulation' : 'Internal'}</span></span><span className="mt-1 block text-[10px] text-slate-500">{displayDate(event.created_at)}</span></span></li>)}</ol>
              </section>
            </div>
          )}
        </ClaimDetailsPanel>
      </section>
      <GlassModal
        open={Boolean(editModalOpen && selectedClaim)}
        onClose={() => setEditModalOpen(false)}
        title="Edit claim"
        description="Update the incident details saved with this claim."
        footer={<>
          <button type="button" className="glass-modal-action glass-modal-action-secondary" onClick={() => setEditModalOpen(false)}>Cancel</button>
          <button type="submit" form="edit-claim-form" disabled={isSavingEdits} aria-busy={isSavingEdits || undefined} className="glass-modal-action glass-modal-action-primary">
            {isSavingEdits && <LoaderCircle className="h-4 w-4 animate-spin" />}{isSavingEdits ? 'Saving…' : 'Save claim'}
          </button>
        </>}
      >
        {selectedClaim && <>
          {error && <p role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{error}</p>}
          <form id="edit-claim-form" onSubmit={handleSaveEdits} className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs font-medium text-slate-700">Claim type<input value={editForm.claim_type} onChange={(event) => setEditForm({ ...editForm, claim_type: event.target.value })} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-700">Incident date<input type="date" value={editForm.incident_date} onChange={(event) => setEditForm({ ...editForm, incident_date: event.target.value })} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-700">Location<input value={editForm.incident_location} onChange={(event) => setEditForm({ ...editForm, incident_location: event.target.value })} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-700">Estimated loss<input inputMode="decimal" value={editForm.estimated_loss} onChange={(event) => setEditForm({ ...editForm, estimated_loss: event.target.value })} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-700 sm:col-span-2">Claim reference<input value={editForm.claim_reference} onChange={(event) => setEditForm({ ...editForm, claim_reference: event.target.value })} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /></label>
          <label className="text-xs font-medium text-slate-700 sm:col-span-2">Incident description<textarea rows={3} value={editForm.incident_description} onChange={(event) => setEditForm({ ...editForm, incident_description: event.target.value })} className="mt-1 block w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm" /></label>
          <p className="text-[11px] text-slate-500 sm:col-span-2">Policy: {policyNames.get(selectedClaim.policy_id) || 'Unavailable'}</p>
          </form>
        </>}
      </GlassModal>
      <GlassModal
        open={Boolean(descriptionModalOpen && selectedClaim)}
        onClose={() => setDescriptionModalOpen(false)}
        title="Claim description draft"
        description="Review every fact and edit this AI-assisted draft before using it. No claim is submitted here."
        footer={<>
          <button type="button" className="glass-modal-action glass-modal-action-secondary" onClick={() => setDescriptionModalOpen(false)}>Cancel</button>
          <button type="button" className="glass-modal-action glass-modal-action-secondary" onClick={async () => {
            try { await navigator.clipboard.writeText(descriptionDraft); setNotice('Draft copied to clipboard.'); }
            catch { setError('Could not copy the draft. Check clipboard permissions and try again.'); }
          }}><Copy className="h-4 w-4" />Copy</button>
          <button type="button" className="glass-modal-action glass-modal-action-primary" onClick={async () => {
            if (await saveClaim({ claim_description_draft: descriptionDraft }, 'Description draft saved for review.')) setDescriptionModalOpen(false);
          }}>Save draft</button>
        </>}
      >
        {selectedClaim && <>
          {error && <p role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{error}</p>}
          <button type="button" disabled={generatingDescription} aria-busy={generatingDescription || undefined} className="glass-modal-action glass-modal-action-primary" onClick={async () => {
            setGeneratingDescription(true); setError(null);
            try {
              const result = await workflowRequest<{ description: string; citations: import('@/types/api').VerifiedCitation[] }>(`claims/${encodeURIComponent(selectedClaim.id)}/description-draft`, 'POST');
              setDescriptionDraft(result.description + (result.citations.length ? '\n\nVerified policy references:\n' + result.citations.map(c => `${c.clause_heading || c.clause_id} (page ${c.page_number}): ${c.exact_quote}`).join('\n\n') : ''));
            } catch (error) { setError(error instanceof Error ? error.message : 'Could not generate draft.'); }
            finally { setGeneratingDescription(false); }
          }}>{generatingDescription && <LoaderCircle className="h-4 w-4 animate-spin" />}{generatingDescription ? 'Generating…' : descriptionDraft ? 'Regenerate draft' : 'Generate draft'}</button>
          <label className="mt-4 block text-xs font-semibold text-slate-700" htmlFor="claim-description-draft">Editable draft<textarea id="claim-description-draft" maxLength={10000} rows={9} value={descriptionDraft} onChange={(event) => setDescriptionDraft(event.target.value)} className="mt-2 block w-full resize-y rounded-lg border border-slate-300 bg-white/80 p-3 text-sm font-normal leading-6" /></label>
        </>}
      </GlassModal>
      <GlassModal
        open={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        title="Upload claim evidence"
        description="Choose a document to attach it to this claim. Existing upload validation and handling remain unchanged."
        footer={<button type="button" className="glass-modal-action glass-modal-action-secondary" onClick={() => setUploadModalOpen(false)}>Cancel</button>}
      >
        {error && <p role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{error}</p>}
        <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-teal-400 bg-white/70 p-5 text-center text-sm font-semibold text-teal-900 hover:bg-teal-50/70">
          <UploadCloud className="h-6 w-6" />{isUploadingDocument ? 'Uploading…' : 'Select a document'}
          <input type="file" className="sr-only" disabled={isUploadingDocument} onChange={(event) => void handleAttachFile(event)} />
        </label>
      </GlassModal>
      <GlassModal
        open={Boolean(checklistModalOpen && selectedClaim)}
        onClose={() => setChecklistModalOpen(false)}
        title="Add checklist item"
        description="Add a document or information item to this claim’s preparation checklist."
        footer={<>
          <button type="button" className="glass-modal-action glass-modal-action-secondary" onClick={() => setChecklistModalOpen(false)}>Cancel</button>
          <button type="submit" form="add-checklist-item-form" className="glass-modal-action glass-modal-action-primary">Add item</button>
        </>}
      >
        <form id="add-checklist-item-form" onSubmit={async (event) => {
          if (await handleAddChecklistItem(event)) setChecklistModalOpen(false);
        }}>
          <label className="block text-xs font-semibold text-slate-700" htmlFor="manual-checklist-title">Document or information item
            <input id="manual-checklist-title" required value={manualChecklistTitle} onChange={(event) => setManualChecklistTitle(event.target.value)} placeholder="Describe what to gather" className="mt-2 block w-full rounded-lg border border-slate-300 bg-white/80 px-3 py-2 text-sm font-normal" />
          </label>
          {error && <p role="alert" className="mt-3 text-xs text-rose-800">{error}</p>}
        </form>
      </GlassModal>
      {guidanceModal && <ClaimsGuidanceModal guidance={guidanceModal} onClose={() => {
        setGuidanceModal(null);
        if (reopenCreateAfterGuidance) {
          setReopenCreateAfterGuidance(false);
          setShowCreateForm(true);
        }
      }} />}
    </main>
  );
}
