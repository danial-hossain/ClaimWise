'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  GitCompare,
  ArrowLeft,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Calculator,
  RefreshCw,
  FileText,
  DollarSign,
  Layers,
  Sparkles,
  Download,
} from 'lucide-react';

import {
  fetchUploadedPolicies,
  createPolicyComparison,
  simulateComparisonCost,
  downloadComparisonPdf,
  centsToDollarsClient,
  dollarsToCentsClient,
} from '@/lib/api';
import {
  PolicyExtractionResult,
  ComparisonRecord,
  AttributeStatus,
  ComparisonCostSimulation,
} from '@/types/api';

export default function ComparePage() {
  const [availablePolicies, setAvailablePolicies] = useState<PolicyExtractionResult[]>([]);
  const [selectedPolicyIds, setSelectedPolicyIds] = useState<string[]>([]);
  const [isLoadingPolicies, setIsLoadingPolicies] = useState<boolean>(true);
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [comparisonRecord, setComparisonRecord] = useState<ComparisonRecord | null>(null);
  const [expandedCitationKey, setExpandedCitationKey] = useState<string | null>(null);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState<boolean>(false);

  // Cost Simulation State
  const [simServiceType, setSimServiceType] = useState<string>('Outpatient Surgery & Specialist Follow-up');
  const [simBilledDollars, setSimBilledDollars] = useState<string>('5000');
  const [simAllowedDollars, setSimAllowedDollars] = useState<string>('4000');
  const [isAllowedKnown, setIsAllowedKnown] = useState<boolean>(true);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [costSimulation, setCostSimulation] = useState<ComparisonCostSimulation | null>(null);

  // Status & Notification
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load Policies
  useEffect(() => {
    async function load() {
      setIsLoadingPolicies(true);
      const res = await fetchUploadedPolicies();
      setIsLoadingPolicies(false);
      if (res.data && res.data.length > 0) {
        setAvailablePolicies(res.data);
        // Pre-select first 2 policies if available
        const validIds = res.data.filter((p) => p.policy_id).map((p) => p.policy_id as string);
        if (validIds.length >= 2) {
          setSelectedPolicyIds(validIds.slice(0, 2));
        } else if (validIds.length === 1) {
          setSelectedPolicyIds([validIds[0]]);
        }
      }
    }
    load();
  }, []);

  const handleTogglePolicy = (policyId: string) => {
    setErrorMessage(null);
    if (selectedPolicyIds.includes(policyId)) {
      setSelectedPolicyIds(selectedPolicyIds.filter((id) => id !== policyId));
    } else {
      if (selectedPolicyIds.length >= 4) {
        setErrorMessage('You may compare at most 4 policies simultaneously.');
        return;
      }
      setSelectedPolicyIds([...selectedPolicyIds, policyId]);
    }
  };

  const handleRunComparison = async () => {
    setErrorMessage(null);
    if (selectedPolicyIds.length < 2) {
      setErrorMessage('Please select at least 2 policies (up to 4) to generate a comparison.');
      return;
    }

    setIsComparing(true);
    const billedCents = dollarsToCentsClient(simBilledDollars);
    const allowedCents = isAllowedKnown ? dollarsToCentsClient(simAllowedDollars) : null;

    const res = await createPolicyComparison({
      policy_ids: selectedPolicyIds,
      title: 'Multi-Plan Side-by-Side Analysis',
      cost_assumptions: {
        service_type: simServiceType,
        billed_charges_cents: billedCents,
        allowed_amount_cents: allowedCents,
        is_allowed_amount_known: isAllowedKnown,
      },
    });

    setIsComparing(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setComparisonRecord(res.data);
      if (res.data.cost_simulation) {
        setCostSimulation(res.data.cost_simulation);
      }
    }
  };

  const handleRecalculateSimulation = async () => {
    if (!comparisonRecord) return;
    setIsSimulating(true);
    setErrorMessage(null);

    const billedCents = dollarsToCentsClient(simBilledDollars);
    const allowedCents = isAllowedKnown ? dollarsToCentsClient(simAllowedDollars) : null;

    const res = await simulateComparisonCost(comparisonRecord.id, {
      service_type: simServiceType,
      billed_charges_cents: billedCents,
      allowed_amount_cents: allowedCents,
      is_allowed_amount_known: isAllowedKnown,
      prior_deductible_paid_cents: 0,
      prior_oop_paid_cents: 0,
    });

    setIsSimulating(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setCostSimulation(res.data);
    }
  };

  const handleDownloadComparisonPdf = async () => {
    if (!comparisonRecord) return;
    setIsDownloadingPdf(true);
    setErrorMessage(null);
    const res = await downloadComparisonPdf(comparisonRecord.id);
    setIsDownloadingPdf(false);
    if (res.error) {
      setErrorMessage(res.error);
    }
  };

  // Status Badge Helper
  const renderStatusBadge = (status: AttributeStatus, rawValue: string | null) => {
    switch (status) {
      case 'verified':
        return (
          <div className="flex flex-col items-start gap-1">
            <span className="font-semibold text-slate-900 dark:text-white text-sm">
              {rawValue || 'Documented'}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100/80 px-2 py-0.5 text-[10px] font-medium text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              <ShieldCheck className="h-3 w-3" /> Verified Evidence
            </span>
          </div>
        );
      case 'conflicting':
        return (
          <div className="flex flex-col items-start gap-1">
            <span className="font-semibold text-rose-700 dark:text-rose-400 text-sm">
              {rawValue || 'Conflicting'}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-medium text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
              <AlertTriangle className="h-3 w-3" /> Contradictory Clauses
            </span>
          </div>
        );
      case 'unknown':
        return (
          <div className="flex flex-col items-start gap-1">
            <span className="text-slate-400 italic text-xs">Not established</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100/70 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
              <AlertCircle className="h-3 w-3" /> Unknown Term
            </span>
          </div>
        );
      case 'not_applicable':
      default:
        return (
          <div className="flex flex-col items-start gap-1">
            <span className="text-slate-400 text-xs">N/A</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
              <HelpCircle className="h-3 w-3" /> Not Applicable
            </span>
          </div>
        );
    }
  };

  const dimensionRows: Array<{ key: string; label: string; description: string }> = [
    { key: 'deductible_individual', label: 'Individual Deductible', description: 'Amount member pays before plan cost-sharing activates' },
    { key: 'coinsurance_percentage', label: 'Member Coinsurance', description: 'Percentage of allowed amount member pays post-deductible' },
    { key: 'out_of_pocket_max', label: 'Out-of-Pocket Maximum', description: 'Annual maximum limit on member covered cost-sharing' },
    { key: 'copay_pcp', label: 'Primary Care Copay', description: 'Fixed dollar copayment for routine primary care visits' },
    { key: 'copay_specialist', label: 'Specialist Visit Copay', description: 'Fixed dollar copayment for specialty clinic consultations' },
    { key: 'copay_er', label: 'Emergency Room Copay', description: 'Emergency department fixed admission copayment' },
    { key: 'exclusions', label: 'Exclusions & Non-Covered', description: 'Explicit non-covered treatments, cosmetic, or investigational care' },
    { key: 'network_tier', label: 'Network Structure', description: 'HMO, PPO, EPO tiering, and out-of-network coverage rules' },
    { key: 'prior_authorization', label: 'Prior Authorization', description: 'Advance approval mandates for diagnostic imaging or surgeries' },
    { key: 'waiting_period', label: 'Waiting Period & Terms', description: 'Contract eligibility windows and waiting period clauses' },
  ];

  return (
    <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            >
              <ArrowLeft className="h-3 w-3" /> Dashboard
            </Link>
            <span className="text-slate-300">/</span>
            <span className="text-xs font-semibold text-emerald-600">Compare & Choose</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">
            Multi-Policy Evidence Comparator
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Side-by-side contractual evaluation across up to 4 policies with transparent evidence verification and integer-cents cost simulations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <ShieldCheck className="h-3.5 w-3.5" /> Evidence First: No Guessing
          </span>
        </div>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="rounded-xl border border-rose-300 bg-rose-50 p-4 text-xs text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300 flex items-start gap-2.5">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
          <div>
            <strong className="font-semibold">Comparison Notice: </strong>
            {errorMessage}
          </div>
        </div>
      )}

      {/* Policy Selection Section */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-emerald-600" />
            <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
              Select 2 to 4 Policies to Compare
            </h2>
          </div>
          <span className="text-xs font-mono text-slate-500">
            {selectedPolicyIds.length} / 4 Selected
          </span>
        </div>

        {isLoadingPolicies ? (
          <div className="py-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
            <RefreshCw className="h-4 w-4 animate-spin text-emerald-600" />
            Loading uploaded policies...
          </div>
        ) : availablePolicies.length < 2 ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-center dark:border-amber-900/50 dark:bg-amber-950/30">
            <GitCompare className="h-8 w-8 text-amber-600 mx-auto mb-2" />
            <h3 className="text-xs font-bold text-amber-900 dark:text-amber-200">
              At least 2 uploaded policies required
            </h3>
            <p className="text-xs text-amber-800/80 dark:text-amber-300/80 mt-1 max-w-md mx-auto">
              Please navigate to{' '}
              <Link href="/policies" className="font-semibold underline text-emerald-700 dark:text-emerald-400">
                My Policies
              </Link>{' '}
              and upload at least two insurance policy PDFs to run a side-by-side comparison.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {availablePolicies.map((pol) => {
              const pid = pol.policy_id || '';
              const isSelected = selectedPolicyIds.includes(pid);
              return (
                <div
                  key={pid}
                  onClick={() => pid && handleTogglePolicy(pid)}
                  className={`cursor-pointer rounded-xl border p-4 transition-all relative ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-50/50 shadow-sm dark:border-emerald-500 dark:bg-emerald-950/30'
                      : 'border-slate-200 bg-slate-50/50 hover:border-slate-300 dark:border-slate-800 dark:bg-slate-800/40'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-xs text-slate-900 dark:text-white truncate">
                        {pol.document_name.replace(/\.[^/.]+$/, '')}
                      </p>
                      <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                        {pol.total_clauses} clauses &bull; {pol.total_pages} pages
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 h-4 w-4"
                    />
                  </div>
                  <div className="mt-2 text-[10px] font-mono text-slate-400 truncate">
                    Hash: {pol.document_hash.substring(0, 12)}...
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {availablePolicies.length >= 2 && (
          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={handleRunComparison}
              disabled={isComparing || selectedPolicyIds.length < 2 || selectedPolicyIds.length > 4}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {isComparing ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Analyzing Clauses Across Plans...
                </>
              ) : (
                <>
                  <GitCompare className="h-3.5 w-3.5" /> Compare {selectedPolicyIds.length} Selected Policies
                </>
              )}
            </button>
          </div>
        )}
      </section>

      {/* Comparison Results Matrix */}
      {comparisonRecord && (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-100 dark:border-slate-800">
            <div>
              <h2 className="font-bold text-base text-slate-900 dark:text-white flex items-center gap-2">
                <FileText className="h-5 w-5 text-emerald-600" />
                Side-by-Side Policy Terms Matrix
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Each attribute reflects verified contract wording. Missing terms remain unknown; nothing is assumed as zero.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-md text-slate-500">
                Report ID: {comparisonRecord.id}
              </span>
              <button
                type="button"
                onClick={handleDownloadComparisonPdf}
                disabled={isDownloadingPdf}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 transition"
              >
                {isDownloadingPdf ? (
                  <>
                    <RefreshCw className="h-3 w-3 animate-spin" /> Exporting...
                  </>
                ) : (
                  <>
                    <Download className="h-3 w-3" /> Export Comparison (PDF)
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Matrix Grid */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[650px]">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800">
                  <th className="py-3 px-4 text-xs font-bold uppercase tracking-wider text-slate-500 w-1/4">
                    Insurance Dimension
                  </th>
                  {comparisonRecord.policies.map((p) => (
                    <th key={p.policy_id} className="py-3 px-4 text-xs font-bold text-slate-900 dark:text-white">
                      <div className="text-sm font-semibold">{p.policy_name}</div>
                      <div className="text-[11px] font-normal text-slate-400">{p.insurer_name}</div>
                      <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                        Hash: {p.document_hash.substring(0, 10)}...
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {dimensionRows.map((dim) => (
                  <tr key={dim.key} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition">
                    <td className="py-4 px-4 align-top">
                      <div className="font-semibold text-xs text-slate-800 dark:text-slate-200">
                        {dim.label}
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5 leading-snug">
                        {dim.description}
                      </div>
                    </td>
                    {comparisonRecord.policies.map((p) => {
                      const attr = p.attributes[dim.key];
                      const citKey = `${p.policy_id}-${dim.key}`;
                      const isExpanded = expandedCitationKey === citKey;

                      if (!attr) {
                        return (
                          <td key={p.policy_id} className="py-4 px-4 align-top text-xs text-slate-400 italic">
                            Not evaluated
                          </td>
                        );
                      }

                      return (
                        <td key={p.policy_id} className="py-4 px-4 align-top space-y-2">
                          {renderStatusBadge(attr.status, attr.raw_value)}

                          {/* Notes */}
                          {attr.notes && (
                            <p className="text-[11px] text-slate-500 leading-relaxed">
                              {attr.notes}
                            </p>
                          )}

                          {/* Citations Toggle */}
                          {attr.citations && attr.citations.length > 0 && (
                            <div>
                              <button
                                type="button"
                                onClick={() => setExpandedCitationKey(isExpanded ? null : citKey)}
                                className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 hover:text-emerald-700 dark:text-emerald-400"
                              >
                                {isExpanded ? (
                                  <>
                                    <ChevronUp className="h-3 w-3" /> Hide Source Evidence ({attr.citations.length})
                                  </>
                                ) : (
                                  <>
                                    <ChevronDown className="h-3 w-3" /> Inspect Clause Citations ({attr.citations.length})
                                  </>
                                )}
                              </button>

                              {isExpanded && (
                                <div className="mt-2 space-y-1.5 bg-slate-50 p-2.5 rounded-lg border border-slate-200 dark:bg-slate-800/60 dark:border-slate-700 text-[11px]">
                                  {attr.citations.map((c, cIdx) => (
                                    <div key={cIdx} className="space-y-0.5">
                                      <div className="flex items-center justify-between font-mono text-[10px] text-slate-500">
                                        <span>Clause: {c.clause_id}</span>
                                        <span>Page: {c.page_number}</span>
                                      </div>
                                      <p className="italic text-slate-700 dark:text-slate-300 font-sans">
                                        &ldquo;{c.exact_quote}&rdquo;
                                      </p>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Trade-Off Summary Section */}
          {comparisonRecord.tradeoff_summary && comparisonRecord.tradeoff_summary.length > 0 && (
            <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-5 dark:border-indigo-900/60 dark:bg-indigo-950/20 space-y-2">
              <h3 className="font-semibold text-xs text-indigo-900 dark:text-indigo-200 flex items-center gap-1.5 uppercase tracking-wider">
                <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
                Factual Trade-Off Synthesis & Analysis
              </h3>
              <ul className="list-disc pl-5 text-xs text-indigo-950/80 dark:text-indigo-300/80 space-y-1">
                {comparisonRecord.tradeoff_summary.map((to, tIdx) => (
                  <li key={tIdx} className="leading-relaxed">
                    {to}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Interactive Cost Simulation Modeling */}
          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calculator className="h-5 w-5 text-emerald-600" />
                <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                  Deterministic Cost Comparison Simulator
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">Pure Python Rules Engine</span>
            </div>

            <p className="text-xs text-slate-500">
              Simulate expected member out-of-pocket costs across all plans for a designated medical event.
              Calculations are computed strictly in integer cents with transparent assumptions.
            </p>

            {/* Assumptions Form */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200 dark:bg-slate-800/40 dark:border-slate-700">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Service Scenario:
                </label>
                <input
                  type="text"
                  value={simServiceType}
                  onChange={(e) => setSimServiceType(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Billed Charges ($):
                </label>
                <input
                  type="number"
                  min="0"
                  step="50"
                  value={simBilledDollars}
                  onChange={(e) => setSimBilledDollars(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Negotiated Allowed Amount ($):
                </label>
                <div className="space-y-1">
                  <input
                    type="number"
                    min="0"
                    step="50"
                    disabled={!isAllowedKnown}
                    value={isAllowedKnown ? simAllowedDollars : ''}
                    placeholder={isAllowedKnown ? '4000' : 'Unknown / Illustrative'}
                    onChange={(e) => setSimAllowedDollars(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none disabled:bg-slate-100 disabled:text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  />
                  <div className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      id="allowed-known"
                      checked={isAllowedKnown}
                      onChange={(e) => setIsAllowedKnown(e.target.checked)}
                      className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 h-3.5 w-3.5"
                    />
                    <label htmlFor="allowed-known" className="text-[11px] text-slate-600 dark:text-slate-400">
                      Allowed rate is established
                    </label>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleRecalculateSimulation}
                disabled={isSimulating}
                className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-50 dark:bg-emerald-600 dark:hover:bg-emerald-700 transition"
              >
                {isSimulating ? (
                  <>
                    <RefreshCw className="h-3 w-3 animate-spin" /> Recalculating...
                  </>
                ) : (
                  <>
                    <DollarSign className="h-3.5 w-3.5" /> Recalculate Illustrative Breakdown
                  </>
                )}
              </button>
            </div>

            {/* Simulation Results Cards */}
            {costSimulation && (
              <div className="space-y-4 pt-2">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {costSimulation.policy_estimates.map((est) => (
                    <div
                      key={est.policy_id}
                      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-800/60 space-y-3"
                    >
                      <div className="border-b border-slate-100 pb-2 dark:border-slate-700">
                        <h4 className="font-semibold text-xs text-slate-900 dark:text-white truncate">
                          {est.policy_name}
                        </h4>
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium mt-1 ${
                            est.is_complete
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                              : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                          }`}
                        >
                          {est.is_complete ? 'Complete Calculation' : 'Illustrative Estimate'}
                        </span>
                      </div>

                      <div className="space-y-1 text-xs">
                        <div className="flex justify-between text-slate-500">
                          <span>Member Responsibility:</span>
                          <strong className="text-slate-900 dark:text-white font-mono font-bold">
                            {est.member_responsibility_cents !== null
                              ? centsToDollarsClient(est.member_responsibility_cents)
                              : 'Incomplete'}
                          </strong>
                        </div>
                        <div className="flex justify-between text-slate-500">
                          <span>Insurer Payout:</span>
                          <strong className="text-emerald-700 dark:text-emerald-400 font-mono font-semibold">
                            {est.insurer_responsibility_cents !== null
                              ? centsToDollarsClient(est.insurer_responsibility_cents)
                              : 'Incomplete'}
                          </strong>
                        </div>
                        {est.deductible_portion_cents != null && (
                          <div className="flex justify-between text-[11px] text-slate-400">
                            <span>Deductible Paid:</span>
                            <span>{centsToDollarsClient(est.deductible_portion_cents)}</span>
                          </div>
                        )}
                        {est.coinsurance_portion_cents != null && (
                          <div className="flex justify-between text-[11px] text-slate-400">
                            <span>Coinsurance Paid:</span>
                            <span>{centsToDollarsClient(est.coinsurance_portion_cents)}</span>
                          </div>
                        )}
                      </div>

                      {est.caveats_and_assumptions.length > 0 && (
                        <div className="border-t border-slate-100 pt-2 dark:border-slate-700">
                          <p className="text-[10px] text-amber-700 dark:text-amber-400 leading-tight">
                            {est.caveats_and_assumptions[0]}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {costSimulation.comparative_analysis && costSimulation.comparative_analysis.length > 0 && (
                  <div className="rounded-xl bg-slate-50 p-4 border border-slate-200 dark:bg-slate-800/40 dark:border-slate-700 space-y-1 text-xs text-slate-600 dark:text-slate-300">
                    <strong className="font-semibold text-slate-800 dark:text-slate-200">
                      Material Trade-Off Observations:
                    </strong>
                    <ul className="list-disc pl-5 space-y-1 mt-1 text-[11px]">
                      {costSimulation.comparative_analysis.map((obs, oIdx) => (
                        <li key={oIdx}>{obs}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <p className="text-[10px] text-slate-400 italic">
                  {costSimulation.disclaimer}
                </p>
              </div>
            )}
          </div>
        </section>
      )}
    </main>
  );
}
