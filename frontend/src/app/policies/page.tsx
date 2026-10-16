'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useWizardAction } from '@/components/features/wizard/WizardAction';
import AutoAdvance, { type Handoff } from '@/components/ui/AutoAdvance';
import { useScenario } from '@/context/ScenarioContext';
import {
  FileText,
  UploadCloud,
  Shield,
  AlertCircle,
  RefreshCw,
  X,
  Layers,
  Copy,
  Check,
  Sparkles,
} from 'lucide-react';
import {
  uploadPolicyFile,
  fetchUploadedPolicies,
  fetchOriginalPolicyPdf,
  rewritePolicyHeadings,
} from '@/lib/api';
import {
  PolicyExtractionResult,
  ExtractedClause,
} from '@/types/api';
import PolicyCard from '@/components/ui/PolicyCard';
import { GlassPanel } from '@/components/ui/Glass';
import HeroSection from '@/components/ui/HeroSection';
import HeroIllustration from '@/components/ui/HeroIllustration';
import { Skeleton, StaggerGroup, StaggerItem } from '@/components/ui/Motion';
import PolicyUploadProgress from '@/components/ui/PolicyUploadProgress';
import {
  isPolicyClause,
  parseClauseContent,
  highlightMatch,
} from '@/lib/clauseClassifier';
import { cachePolicyPdf, getCachedPolicyPdf } from '@/lib/policyPdfCache';

// ==============================================================================
// MODAL CLAUSE CARD
// ==============================================================================

function ModalClauseCardItem({
  clause,
  searchQuery,
  onCopy,
  isCopied,
  showHeading = true,
}: {
  clause: ExtractedClause;
  searchQuery: string;
  onCopy: (id: string, text: string) => void;
  isCopied: boolean;
  showHeading?: boolean;
}) {
  const sections = useMemo(
    () => parseClauseContent(clause.text, clause.clause_heading),
    [clause.text, clause.clause_heading]
  );
  const pageClauseMatch = clause.clause_id.match(/^P\d+-C(\d+)$/);

  return (
    <article className="group space-y-3 rounded-2xl border border-white/80 bg-white/75 p-5 shadow-[0_12px_32px_-24px_rgba(15,47,75,0.35)] backdrop-blur-xl transition-all hover:border-teal-200/80 cw-glass">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs font-bold text-teal-800 bg-teal-50 border border-teal-200/80 px-2.5 py-0.5 rounded-lg shadow-2xs">
            Clause {clause.clause_id} · Page {clause.page_number}{pageClauseMatch ? ` · Line ${pageClauseMatch[1]}` : ''}
          </span>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => onCopy(clause.clause_id, clause.text)}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors cursor-pointer"
            title="Copy verbatim clause text"
          >
            {isCopied ? (
              <>
                <Check className="h-3 w-3 text-emerald-600" />
                <span className="text-emerald-700 font-semibold">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3 text-slate-400" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Heading */}
      {showHeading && clause.clause_heading ? (
        <h4 className="text-sm sm:text-base font-bold text-[#173b58] tracking-tight leading-snug">
          {highlightMatch(clause.clause_heading, searchQuery)}
        </h4>
      ) : showHeading && clause.section_number ? (
        <h4 className="text-sm font-bold text-slate-800">
          Section {clause.section_number}
        </h4>
      ) : null}

      {/* Formatted Content */}
      <div className="text-xs sm:text-sm text-slate-700 leading-relaxed space-y-2.5">
        {sections.map((section, idx) => {
          if (section.type === 'bullet') {
            return (
              <div key={idx} className="flex items-start gap-2.5 pl-1.5 py-0.5">
                <span className="mt-2 h-1.5 w-1.5 rounded-full bg-teal-600 shrink-0" />
                <span className="flex-1 leading-relaxed">
                  {highlightMatch(section.text, searchQuery)}
                </span>
              </div>
            );
          }
          return (
            <p key={idx} className="leading-relaxed">
              {highlightMatch(section.text, searchQuery)}
            </p>
          );
        })}
      </div>
    </article>
  );
}

// ==============================================================================
// MAIN POLICIES PAGE COMPONENT
// ==============================================================================

export default function PoliciesPage() {
  const [handoff, setHandoff] = useState<Handoff | null>(null);
  const { remember, scenario, isWizard, wizardHref } = useScenario();
  const router = useRouter();
  // Upload & Extraction state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<PolicyExtractionResult | null>(null);
  const [newPolicyHash, setNewPolicyHash] = useState<string>();
  const [loadingPolicies, setLoadingPolicies] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activePolicy, setActivePolicy] = useState<PolicyExtractionResult | null>(null);
  const [isPolicyViewerOpen, setIsPolicyViewerOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingOriginalPdf, setIsLoadingOriginalPdf] = useState(false);
  const [originalPdfError, setOriginalPdfError] = useState<string | null>(null);
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const [sessionPolicies, setSessionPolicies] = useState<PolicyExtractionResult[]>([]);
  const readyPolicy = sessionPolicies.find(policy => policy.policy_id === scenario.policyId);
  const readyToAdvance = Boolean(readyPolicy?.status === 'success' && readyPolicy.has_extractable_text && readyPolicy.clauses.length && !isUploading);
  useWizardAction({ label: 'Continue to analysis', disabled: !readyToAdvance, autoAdvanceReady: readyToAdvance, onClick: () => { remember({ policyAdvancedId: scenario.policyId }); router.push(wizardHref('analysis'), { scroll: false }); } });
  useEffect(() => {
    if (!isWizard || !scenario.policyId) return;
    const selected = sessionPolicies.find(policy => policy.policy_id === scenario.policyId);
    remember({ policyReady: Boolean(selected?.has_extractable_text && selected.clauses.length && selected.status === 'success') });
  }, [sessionPolicies, scenario.policyId, isWizard, remember]);

  // Reader Modal state
  const [clauseSearch, setClauseSearch] = useState('');
  const [clausePage, setClausePage] = useState('all');
  const [selectedHeading, setSelectedHeading] = useState('');
  const [headingLabels, setHeadingLabels] = useState<Record<string, string>>({});
  const [isRewritingHeadings, setIsRewritingHeadings] = useState(false);
  const [headingsAiUsed, setHeadingsAiUsed] = useState(false);
  const [viewerMode, setViewerMode] = useState<'clauses' | 'pdf'>('clauses');
  const [copiedClauseId, setCopiedClauseId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pdfPreviewInputRef = useRef<HTMLInputElement>(null);
  const previewUrlsRef = useRef<Record<string, string>>({});
  useEffect(() => {
    if (!isPolicyViewerOpen) return;
    const dialog = document.getElementById('policy-reader-dialog');
    if (!dialog) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const controls = () => [...dialog.querySelectorAll<HTMLElement>('button:not(:disabled), input, select, a[href], [tabindex="0"]')];
    (dialog.querySelector<HTMLElement>('input[type="search"]') || controls()[0])?.focus({ preventScroll: true });
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setIsPolicyViewerOpen(false); }
      if (event.key !== 'Tab') return;
      const items = controls();
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', keyboard);
    return () => { document.removeEventListener('keydown', keyboard); document.body.style.overflow = previousOverflow; previousFocus?.focus({ preventScroll: true }); };
  }, [isPolicyViewerOpen]);

  useEffect(() => () => {
    Object.values(previewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
  }, []);

  // Load existing policies from session on mount
  useEffect(() => {
    async function loadPolicies() {
      setLoadingPolicies(true);
      const res = await fetchUploadedPolicies();
      setLoadError(res.error);
      if (res.data && res.data.length > 0) {
        setSessionPolicies(res.data);
        setActivePolicy(null);
      } else {
        setSessionPolicies([]);
        setActivePolicy(null);
      }
      setLoadingPolicies(false);
    }
    loadPolicies();
    window.addEventListener('claimwise_profile_updated', loadPolicies);
    window.addEventListener('storage', loadPolicies);
    return () => {
      window.removeEventListener('claimwise_profile_updated', loadPolicies);
      window.removeEventListener('storage', loadPolicies);
    };
  }, []);

  // Validate file
  const validateAndSetFile = (file: File) => {
    setUploadResult(null);
    setUploadError(null);
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setUploadError('Invalid file type: Only PDF insurance contracts (.pdf) are supported.');
      setSelectedFile(null);
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setUploadError('File is too large: Policy documents must be under 25MB.');
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setHandoff(null);
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  // Execute upload action
  const handleUpload = async () => {
    if (!selectedFile) return;

    setHandoff(null);
    setIsUploading(true);
    setUploadError(null);
    setUploadResult(null);

    const res = await uploadPolicyFile(selectedFile);
    setIsUploading(false);

    if (res.error) {
      setUploadError(res.error);
    } else if (res.data) {
      setUploadResult(res.data);
      setNewPolicyHash(res.data.document_hash);
      try {
        await cachePolicyPdf(res.data.document_hash, selectedFile);
      } catch {
        // The backend copy remains available if browser storage is unavailable.
      }
      remember({ policyId: res.data.policy_id || undefined, policyReady: Boolean(res.data.status === 'success' && res.data.has_extractable_text && res.data.clauses.length) });
      setActivePolicy(null);
      setSessionPolicies((prev) => [res.data!, ...prev.filter((p) => p.document_hash !== res.data!.document_hash)]);
      const previousUrl = previewUrlsRef.current[res.data.document_hash];
      if (previousUrl) URL.revokeObjectURL(previousUrl);
      const previewUrl = URL.createObjectURL(selectedFile);
      previewUrlsRef.current = { ...previewUrlsRef.current, [res.data.document_hash]: previewUrl };
      setPreviewUrls(previewUrlsRef.current);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';

      if (res.data.is_scanned && !res.data.has_extractable_text) {
        setUploadError('Document is a scanned image with no extractable digital text streams. Under our evidence-first standard, we cannot guess unreadable clauses.');
      } else if (res.data.status === 'success' && res.data.has_extractable_text && res.data.clauses.length && res.data.policy_id) {
        setHandoff({ href: `/coverage?policy_id=${encodeURIComponent(res.data.policy_id)}`, title: 'Your policy is ready.', description: 'Next, describe the incident you want us to check.', seconds: 4 });
      }
    }
  };

  const handleCopyClause = (clauseId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedClauseId(clauseId);
    setTimeout(() => setCopiedClauseId(null), 2000);
  };

  const handleOpenOriginalPdf = async () => {
    if (!activePolicy) return;
    setViewerMode('pdf');
    setOriginalPdfError(null);
    if (previewUrls[activePolicy.document_hash]) return;

    setIsLoadingOriginalPdf(true);
    try {
      const cachedPdf = await getCachedPolicyPdf(activePolicy.document_hash);
      if (cachedPdf) {
        const cachedUrl = URL.createObjectURL(new Blob([cachedPdf], { type: 'application/pdf' }));
        previewUrlsRef.current = { ...previewUrlsRef.current, [activePolicy.document_hash]: cachedUrl };
        setPreviewUrls(previewUrlsRef.current);
        setIsLoadingOriginalPdf(false);
        return;
      }
    } catch {
      // Continue with the server copy if IndexedDB is unavailable.
    }

    if (!activePolicy.policy_id) {
      setOriginalPdfError('The original PDF is not available for this policy.');
      setIsLoadingOriginalPdf(false);
      return;
    }

    const result = await fetchOriginalPolicyPdf(activePolicy.policy_id);
    if (result.data) {
      const pdfBlob = new Blob([result.data], { type: 'application/pdf' });
      void cachePolicyPdf(activePolicy.document_hash, pdfBlob).catch(() => undefined);
      const url = URL.createObjectURL(pdfBlob);
      previewUrlsRef.current = { ...previewUrlsRef.current, [activePolicy.document_hash]: url };
      setPreviewUrls(previewUrlsRef.current);
    } else {
      setOriginalPdfError(result.error || 'Unable to load the original PDF.');
    }
    setIsLoadingOriginalPdf(false);
  };

  const handleLocalPdfPreview = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !activePolicy) return;

    setIsLoadingOriginalPdf(true);
    setOriginalPdfError(null);
    try {
      const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
      const fileHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
      if (fileHash.toLowerCase() !== activePolicy.document_hash.toLowerCase()) {
        setOriginalPdfError('This file does not match the policy document. Choose the exact PDF that was uploaded.');
        return;
      }

      const previousUrl = previewUrlsRef.current[activePolicy.document_hash];
      if (previousUrl) URL.revokeObjectURL(previousUrl);
      const url = URL.createObjectURL(file);
      previewUrlsRef.current = { ...previewUrlsRef.current, [activePolicy.document_hash]: url };
      setPreviewUrls(previewUrlsRef.current);
      setViewerMode('pdf');
    } catch {
      setOriginalPdfError('The PDF could not be verified in this browser.');
    } finally {
      setIsLoadingOriginalPdf(false);
    }
  };

  // Show all policy clauses in document order so the reader flows heading by heading.
  const modalClauses = useMemo(() => {
    if (!activePolicy?.clauses) return [];
    return activePolicy.clauses.filter(isPolicyClause);
  }, [activePolicy]);

  const headingGroups = useMemo(() => {
    const groups: { heading: string; clauses: ExtractedClause[] }[] = [];
    let currentHeading = 'Other provisions';
    modalClauses.forEach((clause) => {
      const detectedHeading = clause.clause_heading?.trim() ||
        (clause.section_number ? `Section ${clause.section_number}` : '');
      if (detectedHeading) currentHeading = detectedHeading;

      const currentGroup = groups[groups.length - 1];
      if (currentGroup?.heading === currentHeading) {
        currentGroup.clauses.push(clause);
      } else {
        groups.push({ heading: currentHeading, clauses: [clause] });
      }
    });
    return groups.map((group, index) => ({ ...group, id: `heading-${index}` }));
  }, [modalClauses]);

  // Filter the reader only. Stable source groups keep AI heading requests and IDs unchanged.
  const visibleHeadingGroups = headingGroups.map(group => ({ ...group, clauses: group.clauses.filter(clause => {
    if (clausePage !== 'all' && String(clause.page_number) !== clausePage) return false;
    const query = clauseSearch.trim().toLowerCase();
    return !query || [clause.clause_id, clause.clause_heading, clause.section_number, clause.text].some(value => value?.toLowerCase().includes(query));
  }) })).filter(group => group.clauses.length);
  const activeHeadingGroup = visibleHeadingGroups.find((group) => group.id === selectedHeading) ?? visibleHeadingGroups[0];

  useEffect(() => {
    if (!isPolicyViewerOpen || !activePolicy || headingGroups.length === 0) return;

    let isCurrent = true;
    const headingTimer = window.setTimeout(() => {
    setHeadingLabels({});
    setHeadingsAiUsed(false);
    setIsRewritingHeadings(true);
    rewritePolicyHeadings(headingGroups.slice(0, 100).map((group) => ({
      id: group.id,
      heading: group.heading,
      context: group.clauses.slice(0, 3).map((clause) => clause.text.slice(0, 500)).join('\n'),
    }))).then((result) => {
      if (!isCurrent || !result.data) return;
      setHeadingLabels(result.data.headings);
      setHeadingsAiUsed(result.data.ai_used);
    }).finally(() => {
      if (isCurrent) setIsRewritingHeadings(false);
    });
    }, 0);
    return () => { isCurrent = false; window.clearTimeout(headingTimer); };
  }, [isPolicyViewerOpen, activePolicy, headingGroups]);

  return (
    <main className={`app-page policies-page mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-7 sm:py-10 lg:px-10 ${sessionPolicies.length === 0 ? 'policies-page-empty' : ''}`}>
      {handoff && <AutoAdvance key={handoff.href} handoff={handoff} onPause={() => setHandoff(null)} />}
      <HeroSection
        eyebrow="Your coverage, in focus"
        title={{ firstLine: 'Understand what your', secondLine: 'policy covers.' }}
        description="Add your insurance documents to review benefits, limits, and exclusions with evidence from the policy text."
        secondaryAction={<Link href="/compare" className="policy-compare-link hero-section-secondary"><Layers className="h-3.5 w-3.5" />Compare policies</Link>}
        variant="upload"
        className="policy-hero"
      >
        <HeroIllustration variant="upload" />
        <div className="policy-hero-upload">
          <div className="mb-4 flex items-center gap-3">
            <div className="policy-upload-icon flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"><UploadCloud className="h-5 w-5" /></div>
            <div>
              <div className="policy-upload-kicker">Add to your library</div>
              <h2 className="mt-1 text-sm font-semibold text-slate-900">Upload a policy document</h2>
            </div>
          </div>

          <GlassPanel
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`policy-upload-panel relative overflow-hidden rounded-2xl border p-5 transition-all sm:p-6 ${isDragging ? 'is-dragging' : ''}`}
          >
            <p className="text-xs leading-relaxed text-slate-600">
              Drag and drop your PDF contract or schedule of benefits here, or browse files (up to 25MB).
            </p>
            <input ref={fileInputRef} type="file" accept=".pdf,application/pdf" onChange={handleFileChange} disabled={isUploading} className="hidden" id="policy-file-upload" />
            <div className="mt-4 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
              <label htmlFor="policy-file-upload" className="policy-select-file inline-flex max-w-full cursor-pointer items-center gap-2 rounded-xl border px-4 py-2.5 text-xs font-semibold transition-colors">
                <FileText className="h-4 w-4 shrink-0 text-teal-700" />
                <span className="truncate">{selectedFile ? selectedFile.name : 'Select PDF File'}</span>
              </label>
              {selectedFile && (
                <button type="button" onClick={handleUpload} disabled={isUploading} className="policy-submit-upload inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-xs font-semibold text-white transition-colors disabled:opacity-50">
                  {isUploading ? <><RefreshCw className="h-3.5 w-3.5" /> Uploading and extracting…</> : <><UploadCloud className="h-4 w-4" /> Upload &amp; extract</>}
                </button>
              )}
            </div>
            <PolicyUploadProgress pending={isUploading} result={uploadResult} error={uploadError} />
            <div className="mt-4 flex items-start gap-2 text-[11px] leading-relaxed text-slate-500">
              <Shield className="mt-0.5 h-3 w-3 shrink-0 text-teal-700" />
              <span>PDF validation, tamper-evident file hashing, and page-indexed citations.</span>
            </div>
          </GlassPanel>

          {uploadError && (
            <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50/90 p-3.5 text-xs text-rose-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
              <div><p className="font-semibold">Notice</p><p className="mt-0.5">{uploadError}</p></div>
            </div>
          )}
        </div>
      </HeroSection>
      {loadError && <p role="alert" className="cw-inline-error">Your policy library could not be loaded. {loadError}</p>}
      {loadingPolicies && !sessionPolicies.length && <div role="status" aria-label="Loading policy library" className="grid gap-4 md:grid-cols-3">{[0, 1, 2].map(i => <Skeleton key={i} className="h-52" />)}</div>}
      {!loadingPolicies && !loadError && !sessionPolicies.length && <GlassPanel className="cw-library-empty"><FileText size={28} /><h2>Your policy library starts here</h2><p>Upload your first PDF above to get answers grounded in your own insurance documents.</p><a className="text-sm font-semibold text-teal-800 underline" href="#policy-file-upload" onClick={() => fileInputRef.current?.click()}>Choose a policy PDF</a></GlassPanel>}
      {/* 2. Grid of Policy Cards (Each card is expandable and contains only genuine clauses) */}
      {isWizard && sessionPolicies.length > 0 && <section className="rounded-2xl border border-teal-100 bg-white/85 p-5">
        <label htmlFor="wizard-policy-select" className="block text-sm font-semibold text-slate-900">Or choose a saved policy</label>
        <select id="wizard-policy-select" value={scenario.policyId || ''} onChange={event => {
          const policy = sessionPolicies.find(item => item.policy_id === event.target.value);
          remember({ policyId: event.target.value || undefined, policyReady: Boolean(policy?.status === 'success' && policy.has_extractable_text && policy.clauses.length) });
          setActivePolicy(policy || null);
        }} className="mt-3 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm"><option value="">Choose a policy</option>{sessionPolicies.filter(policy => policy.policy_id).map(policy => <option key={policy.policy_id} value={policy.policy_id || ''}>{policy.document_name}</option>)}</select>
        {scenario.policyId && <button type="button" className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-teal-800" onClick={() => {
          const policy = sessionPolicies.find(item => item.policy_id === scenario.policyId);
          if (policy) { setActivePolicy(policy); setCurrentPage(1); setSelectedHeading(''); setViewerMode('clauses'); setIsPolicyViewerOpen(true); }
        }}><FileText className="h-4 w-4" />Review this policy and its clauses</button>}
        <p className="mt-3 text-xs leading-6 text-slate-600">Your selected policy stays linked through analysis, guidance, and claim preparation.</p>
      </section>}
      {!isWizard && sessionPolicies.length > 0 && (
        <GlassPanel as="section" className="policy-library-section space-y-4 p-5 sm:p-7">
          <div className="policy-section-heading flex items-end justify-between gap-4">
            <div>
              <div className="policy-page-kicker">Your documents</div>
              <h2 className="mt-1 text-lg font-semibold text-slate-900">
                Policy library <span className="policy-count">{sessionPolicies.length}</span>
              </h2>
            </div>
            <span className="text-xs text-slate-500">
              Open a policy to read its clauses and original document.
            </span>
          </div>

          <StaggerGroup className="policy-library-grid">
            {sessionPolicies.map((p) => {
              const isSelected = activePolicy?.document_hash === p.document_hash || (isWizard && scenario.policyId === p.policy_id);
              return (
                <StaggerItem key={p.document_hash}><PolicyCard
                  key={p.document_hash}
                  policy={p}
                  animateCount={newPolicyHash === p.document_hash}
                  isSelected={isSelected}
                  onSelect={() => {
                    remember({ policyId: p.policy_id || undefined, policyReady: Boolean(p.status === 'success' && p.has_extractable_text && p.clauses.length) });
                    setHandoff(null);
                    setActivePolicy(p);
                    setCurrentPage(1);
                    setSelectedHeading('');
                    setClauseSearch('');
                    setClausePage('all');
                    setViewerMode('clauses');
                    setIsPolicyViewerOpen(true);
                  }}
                /></StaggerItem>
              );
            })}
          </StaggerGroup>
        </GlassPanel>
      )}

      {/* 4. FULL READER MODAL (CONTINUOUS CLAUSE LIST & PDF PREVIEW) */}
      {isPolicyViewerOpen && activePolicy && typeof document !== 'undefined' && createPortal(
        <div
          className="cw-policy-reader-overlay fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/25 p-3 backdrop-blur-md sm:p-6"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setIsPolicyViewerOpen(false);
          }}
        >
          <section
            id="policy-reader-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="policy-viewer-title"
            className="flex max-h-[94svh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-white/70 bg-white/75 shadow-[0_28px_90px_-28px_rgba(15,47,75,0.42)] backdrop-blur-2xl sm:rounded-3xl cw-glass"
          >
            {/* Header */}
            <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/70 bg-white/45 px-4 py-3.5 backdrop-blur-xl sm:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-800">
                  <FileText className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[.12em] text-teal-800">
                    Policy reader · {modalClauses.length} clauses
                  </p>
                  <h2 id="policy-viewer-title" className="mt-0.5 truncate text-sm font-semibold text-slate-900 sm:text-base">
                    {activePolicy.document_name}
                  </h2>
                </div>
              </div>

              <button type="button" disabled={!activePolicy.policy_id || activePolicy.status !== 'success' || !activePolicy.has_extractable_text || !activePolicy.clauses.length} onClick={() => {
                setIsPolicyViewerOpen(false);
                setHandoff({ href: `/coverage?policy_id=${encodeURIComponent(activePolicy.policy_id!)}`, title: 'Policy selected.', description: 'Next, tell us about your incident.', seconds: 3 });
              }} className="shrink-0 rounded-lg bg-teal-800 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">Use this policy →</button>
              {/* View Mode Tabs & Close */}
              <div className="flex items-center gap-2 self-end sm:self-auto">
                <div className="grid grid-cols-2 rounded-lg border border-white/70 bg-white/55 p-0.5 text-xs font-semibold shadow-sm">
                  <button
                    type="button"
                    onClick={() => {
                      setOriginalPdfError(null);
                      setViewerMode('clauses');
                    }}
                    className={`rounded-md px-3 py-1.5 transition-colors cursor-pointer ${
                      viewerMode === 'clauses'
                        ? 'bg-white/90 text-slate-900 shadow-sm font-semibold'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    Policy Clauses
                  </button>
                  <button
                    type="button"
                    disabled={isLoadingOriginalPdf}
                    onClick={handleOpenOriginalPdf}
                    className={`rounded-md px-3 py-1.5 transition-colors cursor-pointer disabled:cursor-wait disabled:opacity-60 ${
                      viewerMode === 'pdf'
                        ? 'bg-white/90 text-slate-900 shadow-sm font-semibold'
                        : 'text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    {isLoadingOriginalPdf ? 'Loading PDF…' : 'Original PDF'}
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => setIsPolicyViewerOpen(false)}
                  aria-label="Close policy viewer"
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-slate-500 transition hover:bg-white/70 hover:text-slate-900 cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </header>

            {/* Modal Body */}
            <div className="cw-policy-reader-body min-h-0 flex-1 overflow-hidden bg-gradient-to-br from-[#dceaf1]/70 via-[#f2f6f9]/75 to-[#dceeea]/70 p-3 sm:p-5">
              {viewerMode === 'pdf' ? (
                previewUrls[activePolicy.document_hash] ? (
                  <object
                    key={`${activePolicy.document_hash}-${currentPage}`}
                    type="application/pdf"
                    aria-label={`Preview of ${activePolicy.document_name}`}
                    data={`${previewUrls[activePolicy.document_hash]}#page=${currentPage}`}
                    className="h-[62vh] min-h-[300px] w-full rounded-xl border border-slate-200 bg-white shadow-sm sm:h-[68vh]"
                  >
                    <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                      <FileText className="h-8 w-8 text-slate-300" />
                      <p className="mt-3 text-sm font-semibold text-slate-800">PDF preview is unavailable in this browser.</p>
                      <a
                        href={previewUrls[activePolicy.document_hash]}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-3 text-xs font-semibold text-teal-700 underline underline-offset-2"
                      >
                        Open the original PDF in a new tab
                      </a>
                    </div>
                  </object>
                ) : (
                  <div className="mx-auto flex h-[62vh] min-h-[300px] max-w-5xl flex-col items-center justify-center rounded-xl border border-white/70 bg-white/35 px-6 text-center shadow-inner backdrop-blur-md sm:h-[68vh]">
                    {isLoadingOriginalPdf ? (
                      <div className="flex flex-col items-center rounded-2xl border border-white/80 bg-white/75 px-8 py-7 shadow-lg backdrop-blur-xl cw-glass"><RefreshCw className="h-6 w-6 animate-spin text-teal-700" /><p className="mt-3 text-sm font-semibold text-slate-800">Loading original PDF…</p></div>
                    ) : (
                      <div className="flex max-w-lg flex-col items-center rounded-2xl border border-white/80 bg-white/75 px-8 py-7 shadow-[0_18px_50px_-24px_rgba(15,47,75,0.35)] backdrop-blur-xl cw-glass">
                        <FileText className="h-8 w-8 text-slate-300" />
                        <p className="mt-3 text-sm font-semibold text-slate-800">Could not open the original PDF</p>
                        <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-500">{originalPdfError}</p>
                        <div className="mt-4 flex flex-wrap justify-center gap-2">
                          <button type="button" onClick={handleOpenOriginalPdf} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50">Try again</button>
                          <button type="button" onClick={() => pdfPreviewInputRef.current?.click()} className="rounded-lg bg-teal-700 px-3 py-2 text-xs font-semibold text-white hover:bg-teal-800">Choose the original PDF</button>
                        </div>
                      </div>
                    )}
                    <input ref={pdfPreviewInputRef} type="file" accept=".pdf,application/pdf" onChange={handleLocalPdfPreview} className="hidden" />
                  </div>
                )
              ) : (
                <><div className="cw-reader-filters"><label>Search clauses<input type="search" value={clauseSearch} onChange={event => setClauseSearch(event.target.value)} placeholder="Clause ID, heading, or words in the policy" /></label><label>Page<select value={clausePage} onChange={event => setClausePage(event.target.value)}><option value="all">All pages</option>{[...new Set(modalClauses.map(clause => clause.page_number))].sort((a, b) => a - b).map(page => <option key={page} value={page}>Page {page}</option>)}</select></label><p role="status">{visibleHeadingGroups.reduce((count, group) => count + group.clauses.length, 0)} matching clauses</p></div>
                <div className="cw-reader-content mx-auto flex h-[62vh] min-h-[300px] max-w-5xl flex-col overflow-hidden rounded-xl border border-white/75 bg-white/35 shadow-[0_16px_40px_-30px_rgba(15,47,75,0.38)] backdrop-blur-lg sm:h-[68vh] md:flex-row">
                  {visibleHeadingGroups.length > 0 ? (
                    <>
                      <nav aria-label="Policy headings" className="flex shrink-0 gap-2 overflow-x-auto border-b border-white/70 bg-white/45 p-3 backdrop-blur-xl md:w-64 md:flex-col md:overflow-y-auto md:overflow-x-hidden md:border-b-0 md:border-r md:p-4">
                        <p className="hidden px-2 pb-1 text-[10px] font-bold uppercase tracking-[.14em] text-slate-400 md:block">
                          {isRewritingHeadings ? 'Refining with AI…' : headingsAiUsed ? 'AI policy headings' : 'Policy headings'}
                        </p>
                        {visibleHeadingGroups.map((group) => (
                          <button
                            key={group.id}
                            type="button"
                            aria-pressed={(activeHeadingGroup?.id ?? '') === group.id}
                            onClick={() => setSelectedHeading(group.id)}
                            className={`flex min-w-[190px] items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-left text-xs transition-colors md:min-w-0 ${
                              (activeHeadingGroup?.id ?? '') === group.id
                                ? 'border-teal-200/90 bg-teal-50/90 text-teal-950 shadow-sm'
                                : 'border-transparent bg-white/20 text-slate-600 hover:border-white/80 hover:bg-white/65'
                            }`}
                          >
                            <span className="line-clamp-2 font-semibold leading-snug">{headingLabels[group.id] || group.heading}</span>
                            <span className="shrink-0 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
                              {group.clauses.length}
                            </span>
                          </button>
                        ))}
                      </nav>

                      <section className="min-h-0 flex-1 overflow-y-auto bg-white/18 p-4 sm:p-6" aria-live="polite">
                        {activeHeadingGroup && (
                          <div className="mb-4 border-b border-slate-200 pb-4">
                            <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[.14em] text-teal-700">
                              {headingsAiUsed && <Sparkles className="h-3 w-3" />}
                              {isRewritingHeadings ? 'Refining heading' : headingsAiUsed ? 'AI refined section' : 'Selected section'}
                            </p>
                            <h3 className="mt-1 text-lg font-semibold leading-snug text-[#173b58]">
                              {headingLabels[activeHeadingGroup.id] || activeHeadingGroup.heading}
                            </h3>
                            <p className="mt-1 text-xs text-slate-500">
                              {activeHeadingGroup.clauses.length} {activeHeadingGroup.clauses.length === 1 ? 'clause' : 'clauses'} in this section
                            </p>
                          </div>
                        )}
                        <div className="space-y-3.5">
                          {activeHeadingGroup?.clauses.map((clause, index) => (
                            <ModalClauseCardItem
                              key={`${clause.clause_id}-${index}`}
                              clause={clause}
                              searchQuery={clauseSearch}
                              onCopy={handleCopyClause}
                              isCopied={copiedClauseId === clause.clause_id}
                              showHeading={false}
                            />
                          ))}
                        </div>
                      </section>
                    </>
                  ) : (
                    <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
                      <FileText className="h-8 w-8 text-slate-300" />
                      <p className="mt-3 text-sm font-semibold text-slate-700">
                        {modalClauses.length ? 'No clauses match these filters' : 'No policy clauses found'}
                      </p>
                      <p className="mt-1 max-w-sm text-xs leading-relaxed text-slate-500">
                        Try a different search term or upload a policy with extractable text.
                      </p>
                    </div>
                  )}
                </div></>
              )}
            </div>

            {/* Modal Footer */}
            <footer className="flex items-center justify-between gap-3 border-t border-white/70 bg-white/45 px-4 py-3 backdrop-blur-xl sm:px-6">
              <p className="text-xs text-slate-500">
                {viewerMode === 'pdf'
                  ? 'Previewing the original uploaded PDF'
                  : `${modalClauses.length} ${modalClauses.length === 1 ? 'clause' : 'clauses'} · shown by policy heading`}
              </p>
            </footer>
          </section>
        </div>, document.body
      )}

      {/* Footer Disclaimer */}
      <footer className="policy-page-footer border-t border-slate-200 pt-5 text-center text-xs text-slate-400">
        ClaimWise explains policy text and does not replace your insurer or give financial advice.
      </footer>
    </main>
  );
}
