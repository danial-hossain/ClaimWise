'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  ClipboardList,
  ArrowLeft,
  Shield,
  AlertTriangle,
  FileSearch,
  Lock,
  Upload,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Send,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  FileText,
  ExternalLink,
  Scale,
  Download,
  Copy,
  Edit3,
  CheckSquare,
  Square,
  ShieldCheck,
} from 'lucide-react';

import {
  fetchUploadedPolicies,
  uploadMedicalBill,
  createClaimFromBill,
  adjudicateClaim,
  submitClaimToSandbox,
  generateAppealDraft,
  updateAppealDraft,
  exportAppealPackage,
  downloadClaimEobPdf,
  downloadAppealPdf,
  centsToDollarsClient,
  dollarsToCentsClient,
} from '@/lib/api';
import {
  PolicyExtractionResult,
  BillExtractionResult,
  BillLineItem,
  ClaimRecord,
  ExplanationOfBenefits,
  SandboxPayerOutcome,
  AdjudicatedLineItem,
  ClaimAppealDraft,
  AppealExportPackage,
} from '@/types/api';

export default function ClaimsPage() {
  // Navigation & Policies
  const [policies, setPolicies] = useState<PolicyExtractionResult[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string>('');

  // Workflow Stages
  // Step 1: Upload Bill -> Step 2: Review Line Items -> Step 3: Adjudicate & EOB -> Step 4: Sandbox
  const [billFile, setBillFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [billExtraction, setBillExtraction] = useState<BillExtractionResult | null>(null);
  const [editableLineItems, setEditableLineItems] = useState<BillLineItem[]>([]);

  // Claim State
  const [currentClaim, setCurrentClaim] = useState<ClaimRecord | null>(null);
  const [isCreatingClaim, setIsCreatingClaim] = useState<boolean>(false);
  const [isAdjudicating, setIsAdjudicating] = useState<boolean>(false);
  const [eob, setEob] = useState<ExplanationOfBenefits | null>(null);
  const [expandedLineId, setExpandedLineId] = useState<string | null>(null);

  // Sandbox Submission State
  const [userConfirmedSandbox, setUserConfirmedSandbox] = useState<boolean>(false);
  const [selectedScenario, setSelectedScenario] = useState<string>('auto');
  const [isSubmittingSandbox, setIsSubmittingSandbox] = useState<boolean>(false);
  const [sandboxOutcome, setSandboxOutcome] = useState<SandboxPayerOutcome | null>(null);

  // Appeal Draft State (Milestone 5)
  const [appealDraft, setAppealDraft] = useState<ClaimAppealDraft | null>(null);
  const [isGeneratingAppeal, setIsGeneratingAppeal] = useState<boolean>(false);
  const [isSavingAppeal, setIsSavingAppeal] = useState<boolean>(false);
  const [isExportingAppeal, setIsExportingAppeal] = useState<boolean>(false);
  const [isDownloadingEobPdf, setIsDownloadingEobPdf] = useState<boolean>(false);
  const [isDownloadingAppealPdf, setIsDownloadingAppealPdf] = useState<boolean>(false);
  const [exportedPackage, setExportedPackage] = useState<AppealExportPackage | null>(null);
  const [editableRebuttal, setEditableRebuttal] = useState<string>('');
  const [editableIssue, setEditableIssue] = useState<string>('');
  const [editableRequestedAction, setEditableRequestedAction] = useState<string>('');
  const [userAdditionalNotes, setUserAdditionalNotes] = useState<string>('');

  // General Notification / Error
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadPolicies() {
      const res = await fetchUploadedPolicies();
      if (res.data && res.data.length > 0) {
        setPolicies(res.data);
        const first = res.data.find((p) => p.policy_id) || res.data[0];
        if (first.policy_id) setSelectedPolicyId(first.policy_id);
      }
    }
    loadPolicies();
  }, []);

  // 1. Handle Bill File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setBillFile(file);
    setIsUploading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const res = await uploadMedicalBill(file);
    setIsUploading(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setBillExtraction(res.data);
      setEditableLineItems(res.data.line_items);
      setSuccessMessage(res.data.message);
      // Reset subsequent steps
      setCurrentClaim(null);
      setEob(null);
      setSandboxOutcome(null);
    }
  };

  // 2. Handle Line Item Edit
  const handleUpdateItem = (
    index: number,
    field: keyof BillLineItem,
    value: string | number | boolean | null
  ) => {
    setEditableLineItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };


  // 3. Confirm & Create Claim Record
  const handleConfirmCreateClaim = async () => {
    if (!billExtraction || !selectedPolicyId) {
      setErrorMessage('Please select a policy document and upload a bill.');
      return;
    }

    setIsCreatingClaim(true);
    setErrorMessage(null);

    const res = await createClaimFromBill(selectedPolicyId, billExtraction.bill_id, editableLineItems);
    setIsCreatingClaim(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setCurrentClaim(res.data);
      setSuccessMessage('Claim record created successfully! Ready for evidence-based adjudication.');
    }
  };

  // 4. Run Evidence Adjudication
  const handleRunAdjudication = async () => {
    if (!currentClaim) return;

    setIsAdjudicating(true);
    setErrorMessage(null);

    const res = await adjudicateClaim(currentClaim.id, 20.0, 50000, 300000);
    setIsAdjudicating(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setEob(res.data);
      setSuccessMessage('Adjudication complete. Itemized Explanation of Benefits (EOB) generated.');
    }
  };

  // 5. Submit to Mock Sandbox
  const handleSubmitSandbox = async () => {
    if (!currentClaim || !userConfirmedSandbox) {
      setErrorMessage('You must confirm the local simulation acknowledgment before submitting.');
      return;
    }

    setIsSubmittingSandbox(true);
    setErrorMessage(null);

    const res = await submitClaimToSandbox(currentClaim.id, selectedScenario);
    setIsSubmittingSandbox(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setSandboxOutcome(res.data);
      setSuccessMessage('Simulated claim outcome received from local mock payer gateway.');
    }
  };

  // Appeal Workflow Handlers (Milestone 5)
  const handleGenerateAppeal = async () => {
    if (!currentClaim) return;
    setIsGeneratingAppeal(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const res = await generateAppealDraft(currentClaim.id, {
      user_additional_facts: userAdditionalNotes.trim() ? userAdditionalNotes : undefined,
    });

    setIsGeneratingAppeal(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setAppealDraft(res.data);
      setEditableIssue(res.data.statement_of_issue);
      setEditableRebuttal(res.data.rebuttal_narrative);
      setEditableRequestedAction(res.data.requested_action);
      setSuccessMessage('Evidence-grounded denial appeal draft generated! Review and customize below.');
    }
  };

  const handleSaveAppealEdits = async () => {
    if (!currentClaim || !appealDraft) return;
    setIsSavingAppeal(true);
    setErrorMessage(null);

    const res = await updateAppealDraft(currentClaim.id, {
      statement_of_issue: editableIssue,
      rebuttal_narrative: editableRebuttal,
      requested_action: editableRequestedAction,
    });

    setIsSavingAppeal(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setAppealDraft(res.data);
      setSuccessMessage('Appeal draft edits saved successfully.');
    }
  };

  const handleExportAppeal = async () => {
    if (!currentClaim) return;
    setIsExportingAppeal(true);
    setErrorMessage(null);

    const res = await exportAppealPackage(currentClaim.id);

    setIsExportingAppeal(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setExportedPackage(res.data);
      if (appealDraft) {
        setAppealDraft({ ...appealDraft, status: 'exported' });
      }
      setSuccessMessage('Appeal package finalized and exported with full verification citations!');
    }
  };

  const handleDownloadEobPdf = async () => {
    if (!currentClaim) return;
    setIsDownloadingEobPdf(true);
    setErrorMessage(null);
    const res = await downloadClaimEobPdf(currentClaim.id);
    setIsDownloadingEobPdf(false);
    if (res.error) {
      setErrorMessage(res.error);
    } else {
      setSuccessMessage('EOB PDF generated and downloaded successfully!');
    }
  };

  const handleDownloadAppealPdf = async () => {
    if (!currentClaim) return;
    setIsDownloadingAppealPdf(true);
    setErrorMessage(null);
    const res = await downloadAppealPdf(currentClaim.id);
    setIsDownloadingAppealPdf(false);
    if (res.error) {
      setErrorMessage(res.error);
    } else {
      setSuccessMessage('Reviewed Appeal Letter PDF generated and downloaded successfully!');
    }
  };

  const getStatusBadge = (status: AdjudicatedLineItem['decision_status']) => {
    switch (status) {
      case 'potentially_covered':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200 dark:bg-emerald-950/60 dark:border-emerald-800 dark:text-emerald-300">
            <CheckCircle2 className="h-3 w-3" /> Potentially Covered
          </span>
        );
      case 'potentially_excluded':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700 border border-red-200 dark:bg-red-950/60 dark:border-red-800 dark:text-red-300">
            <XCircle className="h-3 w-3" /> Potentially Excluded
          </span>
        );
      case 'requires_review':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 border border-amber-200 dark:bg-amber-950/60 dark:border-amber-800 dark:text-amber-300">
            <AlertTriangle className="h-3 w-3" /> Requires Review
          </span>
        );
      case 'insufficient_evidence':
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700 border border-slate-200 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300">
            <HelpCircle className="h-3 w-3" /> Insufficient Evidence
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
            >
              <ArrowLeft className="h-3 w-3" /> Dashboard
            </Link>
            <span className="text-slate-300">/</span>
            <span className="text-xs font-semibold text-emerald-600">My Claims</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">
            Claim Adjudication & Mock Sandbox
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            ClaimWise Tagline: <span className="font-semibold italic text-slate-700 dark:text-slate-300">&ldquo;Evidence first. If no proof, no answer.&rdquo;</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            <Lock className="h-3.5 w-3.5 text-emerald-500" />
            Local Mock Sandbox Environment
          </span>
        </div>
      </div>

      {/* Safety Notice Banner */}
      <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300 flex items-start gap-3">
        <Shield className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="text-xs space-y-1">
          <p className="font-semibold text-amber-900 dark:text-amber-200">
            Educational Simulation Guarantee: No Live Insurance Submissions
          </p>
          <p className="text-amber-800/80 dark:text-amber-400 leading-relaxed">
            ClaimWise will NEVER transmit claim data, EDI 837P files, or appeals to real health plans.
            All adjudication results are illustrative, and sandbox transmissions execute exclusively against
            a local simulated mock payer.
          </p>
        </div>
      </div>

      {/* Feedback Messages */}
      {errorMessage && (
        <div className="rounded-xl bg-red-50 p-3.5 border border-red-200 text-xs text-red-700 flex items-center gap-2 dark:bg-red-950/40 dark:border-red-900/50 dark:text-red-300">
          <XCircle className="h-4 w-4 shrink-0 text-red-500" />
          <span>{errorMessage}</span>
        </div>
      )}
      {successMessage && (
        <div className="rounded-xl bg-emerald-50 p-3.5 border border-emerald-200 text-xs text-emerald-700 flex items-center gap-2 dark:bg-emerald-950/40 dark:border-emerald-900/50 dark:text-emerald-300">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Policy Selector */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <label htmlFor="policy-select" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
              Active Policy Schedule
            </label>
            <p className="text-[11px] text-slate-500">
              Select which master policy schedule will be evaluated during bill adjudication.
            </p>
          </div>
        </div>

        <div>
          {policies.length > 0 ? (
            <select
              id="policy-select"
              value={selectedPolicyId}
              onChange={(e) => setSelectedPolicyId(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {policies.map((p) => (
                <option key={p.policy_id || p.document_hash} value={p.policy_id || ''}>
                  {p.document_name} ({p.total_clauses} clauses)
                </option>
              ))}
            </select>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-600 dark:text-amber-400">No policy uploaded yet</span>
              <Link
                href="/policies"
                className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-emerald-700 transition"
              >
                Upload Policy First <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Step 1: Upload Medical Bill PDF */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-indigo-600" />
            <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
              Step 1: Upload Medical Bill or Provider Invoice (PDF)
            </h2>
          </div>
          <span className="text-xs font-mono text-slate-400">Format: Digital PDF</span>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-4">
          <label className="flex-1 w-full flex flex-col items-center justify-center p-6 border-2 border-dashed border-slate-300 rounded-xl cursor-pointer hover:bg-slate-50 transition dark:border-slate-700 dark:hover:bg-slate-800/50">
            <Upload className="h-8 w-8 text-slate-400 mb-2" />
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
              {billFile ? billFile.name : 'Select or drop medical bill PDF'}
            </span>
            <span className="text-[11px] text-slate-400 mt-1">
              Supports hospital statements, physician invoices, and super-bills (up to 25MB).
            </span>
            <input
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleFileUpload}
              disabled={isUploading}
              className="hidden"
            />
          </label>
        </div>

        {isUploading && (
          <div className="flex items-center gap-2 text-xs text-indigo-600 font-medium">
            <RefreshCw className="h-4 w-4 animate-spin" />
            Extracting line items, procedure codes, and charges from bill...
          </div>
        )}
      </section>

      {/* Step 2: Review Extracted Line Items */}
      {billExtraction && billExtraction.line_items.length > 0 && (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-5 w-5 text-emerald-600" />
              <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
                Step 2: Review Extracted Line Items ({billExtraction.line_items.length} Items)
              </h2>
            </div>
            <span className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-300">
              Total Billed: {centsToDollarsClient(billExtraction.total_billed_cents)}
            </span>
          </div>

          <p className="text-xs text-slate-500">
            Verify extracted procedure descriptions, CPT codes, and billed amounts before creating the claim.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 dark:border-slate-700 dark:bg-slate-800/40">
                  <th className="py-2.5 px-3 font-semibold">ID</th>
                  <th className="py-2.5 px-3 font-semibold">Date</th>
                  <th className="py-2.5 px-3 font-semibold">CPT Code</th>
                  <th className="py-2.5 px-3 font-semibold">Description</th>
                  <th className="py-2.5 px-3 font-semibold">Page</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Billed Charge</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                {editableLineItems.map((item, idx) => (
                  <tr key={item.line_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 font-bold text-slate-800 dark:text-slate-200">{item.line_id}</td>
                    <td className="py-2.5 px-3">
                      <input
                        type="text"
                        value={item.service_date || ''}
                        onChange={(e) => handleUpdateItem(idx, 'service_date', e.target.value)}
                        className="rounded border border-slate-200 px-2 py-1 text-xs w-28 dark:bg-slate-800 dark:border-slate-700"
                      />
                    </td>
                    <td className="py-2.5 px-3">
                      <input
                        type="text"
                        value={item.cpt_code || ''}
                        onChange={(e) => handleUpdateItem(idx, 'cpt_code', e.target.value)}
                        placeholder="e.g. 99284"
                        className="rounded border border-slate-200 px-2 py-1 text-xs w-20 dark:bg-slate-800 dark:border-slate-700"
                      />
                    </td>
                    <td className="py-2.5 px-3 font-sans">
                      <input
                        type="text"
                        value={item.description}
                        onChange={(e) => handleUpdateItem(idx, 'description', e.target.value)}
                        className="rounded border border-slate-200 px-2 py-1 text-xs w-full dark:bg-slate-800 dark:border-slate-700"
                      />
                      {item.is_ambiguous && (
                        <span className="text-[10px] text-amber-600 block mt-0.5">
                          &bull; {item.ambiguity_notes}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">P.{item.source_page_number}</td>
                    <td className="py-2.5 px-3 text-right">
                      <input
                        type="text"
                        value={(item.billed_charge_cents / 100).toFixed(2)}
                        onChange={(e) => handleUpdateItem(idx, 'billed_charge_cents', dollarsToCentsClient(e.target.value))}
                        className="rounded border border-slate-200 px-2 py-1 text-xs w-24 text-right font-mono dark:bg-slate-800 dark:border-slate-700"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800">
            <span className="text-[11px] text-slate-400">
              SHA-256 Hash: <code className="text-[10px]">{billExtraction.document_hash.slice(0, 16)}...</code>
            </span>

            <button
              type="button"
              onClick={handleConfirmCreateClaim}
              disabled={isCreatingClaim || !!currentClaim}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {isCreatingClaim ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Creating Claim...
                </>
              ) : currentClaim ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5" /> Claim Created ({currentClaim.id})
                </>
              ) : (
                <>
                  <FileText className="h-3.5 w-3.5" /> Confirm & Create Claim
                </>
              )}
            </button>
          </div>
        </section>
      )}

      {/* Step 3: Run Adjudication & View EOB */}
      {currentClaim && (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <FileSearch className="h-5 w-5 text-indigo-600" />
              <div>
                <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
                  Step 3: Evidence-Based Adjudication & Itemized EOB
                </h2>
                <p className="text-[11px] text-slate-500">
                  Evaluates line items against contract clauses using deterministic integer-cents arithmetic.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {eob && (
                <button
                  type="button"
                  onClick={handleDownloadEobPdf}
                  disabled={isDownloadingEobPdf}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 transition"
                >
                  {isDownloadingEobPdf ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Exporting...
                    </>
                  ) : (
                    <>
                      <Download className="h-3.5 w-3.5 text-indigo-600" /> Export EOB (PDF)
                    </>
                  )}
                </button>
              )}

              <button
                type="button"
                onClick={handleRunAdjudication}
                disabled={isAdjudicating}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 transition"
              >
                {isAdjudicating ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Adjudicating...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-3.5 w-3.5" /> {eob ? 'Re-run Adjudication' : 'Run Adjudication'}
                  </>
                )}
              </button>
            </div>
          </div>

          {eob && (
            <div className="space-y-6">
              {/* Educational Disclaimer Banner */}
              <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-200 text-xs text-slate-600 dark:bg-slate-800/60 dark:border-slate-700 dark:text-slate-300">
                <strong>EDUCATIONAL EOB DISCLAIMER:</strong> {eob.simulation_disclaimer}
              </div>

              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-800/40">
                  <span className="text-[11px] font-medium text-slate-500 uppercase">Total Billed</span>
                  <div className="text-xl font-bold font-mono text-slate-900 dark:text-white mt-1">
                    {centsToDollarsClient(eob.total_billed_cents)}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 p-4 bg-emerald-50/50 dark:border-emerald-900/40 dark:bg-emerald-950/20">
                  <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 uppercase">
                    Illustrative Insurer Share
                  </span>
                  <div className="text-xl font-bold font-mono text-emerald-800 dark:text-emerald-300 mt-1">
                    {centsToDollarsClient(eob.total_illustrative_insurer_cents)}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 p-4 bg-indigo-50/50 dark:border-indigo-900/40 dark:bg-indigo-950/20">
                  <span className="text-[11px] font-medium text-indigo-700 dark:text-indigo-400 uppercase">
                    Illustrative Member Share
                  </span>
                  <div className="text-xl font-bold font-mono text-indigo-800 dark:text-indigo-300 mt-1">
                    {centsToDollarsClient(eob.total_illustrative_member_cents)}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-800/40">
                  <span className="text-[11px] font-medium text-slate-500 uppercase">Deductible Applied</span>
                  <div className="text-xl font-bold font-mono text-slate-800 dark:text-slate-200 mt-1">
                    {centsToDollarsClient(eob.total_deductible_applied_cents)}
                  </div>
                </div>
              </div>

              {/* Itemized EOB Table */}
              <div className="space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Itemized Cost Breakdown & Evidence
                </h3>

                <div className="space-y-3">
                  {eob.items.map((item) => {
                    const isExpanded = expandedLineId === item.line_id;
                    return (
                      <div
                        key={item.line_id}
                        className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 shadow-sm space-y-3"
                      >
                        <div
                          className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 cursor-pointer"
                          onClick={() => setExpandedLineId(isExpanded ? null : item.line_id)}
                        >
                          <div className="flex items-center gap-3">
                            <span className="font-mono font-bold text-xs text-slate-900 dark:text-white">
                              {item.line_id}
                            </span>
                            {getStatusBadge(item.decision_status)}
                            <span className="text-xs font-medium text-slate-800 dark:text-slate-200">
                              {item.description}
                            </span>
                            {item.cpt_code && (
                              <span className="text-[11px] font-mono text-slate-400">({item.cpt_code})</span>
                            )}
                          </div>

                          <div className="flex items-center gap-4 text-xs font-mono">
                            <span className="text-slate-500">
                              Billed: {centsToDollarsClient(item.billed_charge_cents)}
                            </span>
                            <span className="text-indigo-600 font-semibold">
                              Member: {centsToDollarsClient(item.illustrative_member_cents)}
                            </span>
                            <span className="text-emerald-600 font-semibold">
                              Insurer: {centsToDollarsClient(item.illustrative_insurer_cents)}
                            </span>
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 text-slate-400" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-slate-400" />
                            )}
                          </div>
                        </div>

                        {/* Expandable Details & Citations */}
                        {isExpanded && (
                          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 space-y-3 text-xs">
                            <p className="text-slate-600 dark:text-slate-300 leading-relaxed font-sans">
                              <strong>Decision Rationale:</strong> {item.decision_rationale}
                            </p>

                            {/* Cost Breakdown Pills */}
                            <div className="flex flex-wrap gap-3 font-mono text-[11px] bg-slate-50 p-2.5 rounded-lg border border-slate-100 dark:bg-slate-800/60 dark:border-slate-700">
                              <span>Copay: {centsToDollarsClient(item.copay_cents)}</span>
                              <span>&bull;</span>
                              <span>Deductible: {centsToDollarsClient(item.deductible_applied_cents)}</span>
                              <span>&bull;</span>
                              <span>Coinsurance: {centsToDollarsClient(item.member_coinsurance_cents)}</span>
                              {item.uncovered_amount_cents > 0 && (
                                <>
                                  <span>&bull;</span>
                                  <span className="text-red-600">
                                    Uncovered: {centsToDollarsClient(item.uncovered_amount_cents)}
                                  </span>
                                </>
                              )}
                            </div>

                            {/* Verified Policy Citations */}
                            {item.evidence_citations.length > 0 && (
                              <div className="space-y-1.5">
                                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                                  Verified Policy Proof:
                                </span>
                                {item.evidence_citations.map((cit, idx) => (
                                  <div
                                    key={idx}
                                    className="p-2.5 rounded-lg bg-emerald-50/70 border border-emerald-200 text-xs dark:bg-emerald-950/40 dark:border-emerald-900/50 space-y-1"
                                  >
                                    <div className="flex items-center justify-between font-mono text-[11px] text-emerald-800 dark:text-emerald-300 font-bold">
                                      <span>Clause {cit.clause_id}</span>
                                      <span>Page {cit.page_number}</span>
                                    </div>
                                    <p className="italic text-slate-700 dark:text-slate-300 font-serif">
                                      &ldquo;{cit.exact_quote}&rdquo;
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Assumptions & Missing Facts */}
                            {item.assumptions_and_missing_facts.length > 0 && (
                              <div className="space-y-1">
                                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                                  Assumptions & Missing Information:
                                </span>
                                <ul className="list-disc pl-5 text-[11px] text-slate-500 space-y-0.5">
                                  {item.assumptions_and_missing_facts.map((assump, aIdx) => (
                                    <li key={aIdx}>{assump}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Step 4: Mock Insurer Sandbox Simulation */}
      {eob && (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-emerald-600" />
              <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
                Step 4: Mock Insurer Sandbox Gateway Submission
              </h2>
            </div>
            <span className="text-xs font-mono text-slate-400">Isolated Test Harness</span>
          </div>

          <p className="text-xs text-slate-500">
            Simulate electronic submission (EDI 837P batch flow) to a local mock health payer to observe
            standard remittance advice, claim approval codes, or administrative rejection reasons.
          </p>

          <div className="space-y-3 bg-slate-50 p-4 rounded-xl border border-slate-200 dark:bg-slate-800/40 dark:border-slate-700">
            {/* Scenario Selector */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <label htmlFor="scenario-select" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Simulated Payer Scenario:
              </label>
              <select
                id="scenario-select"
                value={selectedScenario}
                onChange={(e) => setSelectedScenario(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <option value="auto">Auto-detect from Adjudication Evidence</option>
                <option value="approve">Simulate Full Payer Approval (In-Network)</option>
                <option value="partial">Simulate Partial Approval (Cost Sharing Applied)</option>
                <option value="deny_exclusion">Simulate Denial (Exclusion Code 104)</option>
                <option value="request_info">Simulate Pending (Request Chart Notes)</option>
                <option value="gateway_error">Simulate Payer Gateway Timeout (EDI 504)</option>
              </select>
            </div>

            {/* Mandatory User Confirmation Checkbox */}
            <div className="flex items-start gap-2.5 pt-2 border-t border-slate-200 dark:border-slate-700">
              <input
                type="checkbox"
                id="confirm-simulation"
                checked={userConfirmedSandbox}
                onChange={(e) => setUserConfirmedSandbox(e.target.checked)}
                className="mt-0.5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 h-4 w-4"
              />
              <label htmlFor="confirm-simulation" className="text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
                <strong>Explicit Simulation Acknowledgment:</strong> I understand that this is a safe, local sandbox test.
                No patient data or claim forms will be transmitted to any actual insurance carrier.
              </label>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={handleSubmitSandbox}
              disabled={isSubmittingSandbox || !userConfirmedSandbox}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {isSubmittingSandbox ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Transmitting to Mock Sandbox...
                </>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5" /> Submit to Mock Insurer Sandbox
                </>
              )}
            </button>
          </div>

          {/* Sandbox Response Card */}
          {sandboxOutcome && (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50/60 p-5 dark:border-emerald-800 dark:bg-emerald-950/30 space-y-3 mt-4">
              <div className="flex items-center justify-between pb-2 border-b border-emerald-200 dark:border-emerald-800/60">
                <div className="flex items-center gap-2 font-mono text-xs font-bold text-emerald-800 dark:text-emerald-300">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <span>Outcome: {sandboxOutcome.outcome_status}</span>
                </div>
                <span className="font-mono text-[11px] text-emerald-700 dark:text-emerald-400">
                  Ref: {sandboxOutcome.simulated_claim_reference}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono text-slate-700 dark:text-slate-300">
                <div>
                  <span className="text-slate-500 font-sans">Simulated Payer:</span> {sandboxOutcome.simulated_payer_name}
                </div>
                <div>
                  <span className="text-slate-500 font-sans">EDI Batch ID:</span> {sandboxOutcome.simulated_edi_batch_id}
                </div>
                <div>
                  <span className="text-slate-500 font-sans">Simulated Insurer Paid:</span>{' '}
                  <strong className="text-emerald-700 dark:text-emerald-300 font-bold">
                    {centsToDollarsClient(sandboxOutcome.simulated_paid_amount_cents)}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-500 font-sans">Patient Responsibility:</span>{' '}
                  <strong className="text-indigo-700 dark:text-indigo-300 font-bold">
                    {centsToDollarsClient(sandboxOutcome.simulated_patient_responsibility_cents)}
                  </strong>
                </div>
              </div>

              <div className="text-xs text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-900 p-3 rounded-lg border border-emerald-100 dark:border-slate-800">
                <p className="font-semibold text-slate-800 dark:text-slate-200 mb-1">
                  Remittance Code: {sandboxOutcome.simulated_remittance_code}
                </p>
                <p>{sandboxOutcome.explanation_notes}</p>
              </div>

              <p className="text-[10px] text-emerald-800/80 dark:text-emerald-400 font-mono">
                Simulation Timestamp: {new Date(sandboxOutcome.timestamp).toLocaleString()} &bull; {sandboxOutcome.disclaimer}
              </p>
            </div>
          )}
        </section>
      )}

      {/* Step 5: Evidence-Based Denial Appeal Generator (Milestone 5) */}
      {currentClaim && (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <Scale className="h-5 w-5 text-indigo-600" />
              <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
                Step 5: Evidence-Based Denial Appeal Generator
              </h2>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
              <ShieldCheck className="h-3.5 w-3.5" /> Verifiable Grounding
            </span>
          </div>

          <p className="text-xs text-slate-500">
            Generate an evidence-backed formal administrative appeal draft contesting claim denial codes.
            Every policy assertion references validated clauses. Missing documentation is cataloged transparently.
          </p>

          {!appealDraft ? (
            <div className="space-y-3 bg-slate-50 p-4 rounded-xl border border-slate-200 dark:bg-slate-800/40 dark:border-slate-700">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Additional Provider Notes or Member Context (Untrusted Data Input):
                </label>
                <textarea
                  rows={3}
                  value={userAdditionalNotes}
                  onChange={(e) => setUserAdditionalNotes(e.target.value)}
                  placeholder="Optional: Enter clinical details, treating physician notes, or emergency context..."
                  className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-xs text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>

              <div className="flex justify-end pt-1">
                <button
                  type="button"
                  onClick={handleGenerateAppeal}
                  disabled={isGeneratingAppeal}
                  className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {isGeneratingAppeal ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Cross-Examining Denial & Policy Clauses...
                    </>
                  ) : (
                    <>
                      <Scale className="h-3.5 w-3.5" /> Generate Evidence-Based Appeal Draft
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Draft Status Banner */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-mono text-slate-500">Draft ID:</span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200">{appealDraft.draft_id}</span>
                  <span className="text-slate-300">|</span>
                  <span className="font-mono text-slate-500">Denial Code:</span>
                  <span className="font-mono font-semibold text-rose-700 dark:text-rose-400">{appealDraft.denial_reason_code}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                    appealDraft.status === 'exported'
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                      : appealDraft.status === 'user_edited'
                      ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                      : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300'
                  }`}>
                    Status: {appealDraft.status}
                  </span>
                </div>
              </div>

              {/* 1. Statement of Issue */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-800 dark:text-slate-200">
                  1. Concise Statement of the Issue (Editable):
                </label>
                <textarea
                  rows={2}
                  value={editableIssue}
                  onChange={(e) => setEditableIssue(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>

              {/* 2. Factual Background */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-800 dark:text-slate-200">
                  2. Relevant Facts Established in Record:
                </label>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs font-mono text-slate-700 whitespace-pre-wrap dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-300">
                  {appealDraft.factual_background}
                </div>
              </div>

              {/* 3. Verified Policy Clauses */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold text-slate-800 dark:text-slate-200">
                    3. Exact Supporting Policy Clauses (Deterministic Verification):
                  </label>
                  <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400">
                    {appealDraft.policy_clauses_cited.length} Validated Clauses
                  </span>
                </div>

                {appealDraft.policy_clauses_cited.length === 0 ? (
                  <p className="text-xs text-slate-400 italic bg-slate-50 p-3 rounded-lg dark:bg-slate-800/30">
                    No specific policy clause established direct coverage for this denial reason.
                  </p>
                ) : (
                  <div className="grid grid-cols-1 gap-2">
                    {appealDraft.policy_clauses_cited.map((cit, idx) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-3 dark:border-emerald-900/60 dark:bg-emerald-950/20 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between font-mono text-[11px] text-emerald-800 dark:text-emerald-300 font-semibold">
                          <span>Clause: {cit.clause_id} (Page {cit.page_number})</span>
                          <span>Policy: {cit.policy_id}</span>
                        </div>
                        <p className="italic text-slate-800 dark:text-slate-200 font-sans">
                          &ldquo;{cit.exact_quote}&rdquo;
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 4. Rebuttal Narrative */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-800 dark:text-slate-200">
                  4. Reasoned Response to Stated Denial Basis (Editable):
                </label>
                <textarea
                  rows={4}
                  value={editableRebuttal}
                  onChange={(e) => setEditableRebuttal(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>

              {/* 5. Missing Evidence Checklist */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-800 dark:text-slate-200">
                  5. Evidence & Missing-Document Checklist:
                </label>
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 dark:border-slate-700 dark:bg-slate-800/30 divide-y divide-slate-200 dark:divide-slate-700 text-xs">
                  {appealDraft.missing_documents_checklist.map((item, idx) => (
                    <div key={idx} className="py-2 first:pt-0 last:pb-0 flex items-start gap-2.5">
                      {item.is_available ? (
                        <CheckSquare className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                      ) : (
                        <Square className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                      )}
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-800 dark:text-slate-200">
                            {item.item_name}
                          </span>
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                            item.is_available
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                              : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                          }`}>
                            {item.is_available ? 'Available' : 'Recommended to Attach'}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">{item.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 6. Requested Action */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-800 dark:text-slate-200">
                  6. Clear Requested Relief (Editable):
                </label>
                <textarea
                  rows={2}
                  value={editableRequestedAction}
                  onChange={(e) => setEditableRequestedAction(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>

              {/* Human Review Disclaimer */}
              <div className="rounded-xl border border-amber-300 bg-amber-50/70 p-3.5 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300 flex items-start gap-2.5">
                <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <p className="leading-relaxed">
                  <strong>Mandatory Human Review Disclaimer:</strong> {appealDraft.disclaimer}
                </p>
              </div>

              {/* Actions Bar */}
              <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleSaveAppealEdits}
                  disabled={isSavingAppeal}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 transition"
                >
                  {isSavingAppeal ? (
                    <>
                      <RefreshCw className="h-3 w-3 animate-spin" /> Saving Changes...
                    </>
                  ) : (
                    <>
                      <Edit3 className="h-3.5 w-3.5" /> Save My Edits
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={handleDownloadAppealPdf}
                  disabled={isDownloadingAppealPdf || !appealDraft || (appealDraft.status !== 'user_edited' && appealDraft.status !== 'exported')}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-300 bg-indigo-50 px-4 py-2 text-xs font-semibold text-indigo-700 shadow-sm hover:bg-indigo-100 disabled:opacity-50 dark:border-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-300 transition"
                  title={
                    appealDraft.status === 'generated'
                      ? 'Save edits before downloading PDF'
                      : 'Download reviewed appeal letter as PDF'
                  }
                >
                  {isDownloadingAppealPdf ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Generating PDF...
                    </>
                  ) : (
                    <>
                      <Download className="h-3.5 w-3.5" /> Download Appeal PDF
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={handleExportAppeal}
                  disabled={isExportingAppeal}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {isExportingAppeal ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Finalizing Appeal Package...
                    </>
                  ) : (
                    <>
                      <Download className="h-3.5 w-3.5" /> Export Reviewed Appeal Package
                    </>
                  )}
                </button>
              </div>

              {/* Exported Package View */}
              {exportedPackage && (
                <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 dark:border-indigo-900/60 dark:bg-indigo-950/30 space-y-3">
                  <div className="flex items-center justify-between border-b border-indigo-100 pb-2 dark:border-indigo-800">
                    <span className="font-semibold text-xs text-indigo-900 dark:text-indigo-200 flex items-center gap-1.5">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      Appeal Package Finalized & Exported (ID: {exportedPackage.export_id})
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleDownloadAppealPdf}
                        disabled={isDownloadingAppealPdf}
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
                      >
                        <Download className="h-3 w-3" /> Download PDF
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(exportedPackage.formatted_markdown_letter);
                          setSuccessMessage('Full appeal letter copied to clipboard!');
                        }}
                        className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm border border-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700"
                      >
                        <Copy className="h-3 w-3" /> Copy Letter Text
                      </button>
                    </div>
                  </div>

                  <pre className="p-3 bg-white dark:bg-slate-900 rounded-lg border border-indigo-100 dark:border-slate-800 text-[11px] font-mono text-slate-800 dark:text-slate-200 overflow-x-auto whitespace-pre-wrap max-h-72">
                    {exportedPackage.formatted_markdown_letter}
                  </pre>
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
