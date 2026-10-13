'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  FileText,
  UploadCloud,
  ArrowLeft,
  Shield,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Copy,
  Hash,
  BookOpen,
  Calculator,
  RefreshCw,
  Search,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  uploadPolicyFile,
  fetchUploadedPolicies,
  calculateCostSharing,
} from '@/lib/api';
import {
  PolicyExtractionResult,
  ExtractedClause,
  CostCalculationResult,
} from '@/types/api';

export default function PoliciesPage() {
  // Upload & Extraction state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [activePolicy, setActivePolicy] = useState<PolicyExtractionResult | null>(null);
  const [sessionPolicies, setSessionPolicies] = useState<PolicyExtractionResult[]>([]);
  const [selectedPageFilter, setSelectedPageFilter] = useState<number | 'all'>('all');
  const [clauseSearch, setClauseSearch] = useState('');
  const [expandedClauses, setExpandedClauses] = useState<Record<string, boolean>>({});
  const [copiedHash, setCopiedHash] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Rules Engine Calculator state
  const [calcExpense, setCalcExpense] = useState('1000.00');
  const [calcDeductible, setCalcDeductible] = useState('500.00');
  const [calcCoinsurance, setCalcCoinsurance] = useState('20');
  const [calcOopMax, setCalcOopMax] = useState('2500.00');
  const [calcPolicyLimit, setCalcPolicyLimit] = useState('');
  const [calcLoading, setCalcLoading] = useState(false);
  const [calcError, setCalcError] = useState<string | null>(null);
  const [calcResult, setCalcResult] = useState<CostCalculationResult | null>(null);

  // Load existing policies from local development session on mount
  useEffect(() => {
    async function loadPolicies() {
      const res = await fetchUploadedPolicies();
      if (res.data && res.data.length > 0) {
        setSessionPolicies(res.data);
        setActivePolicy(res.data[res.data.length - 1]);
      }
    }
    loadPolicies();
  }, []);

  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null);
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setUploadError('Only PDF files (.pdf) are supported. Please select a valid policy document.');
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
    }
  };

  // Execute upload action
  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadError(null);

    const res = await uploadPolicyFile(selectedFile);
    setIsUploading(false);

    if (res.error) {
      setUploadError(res.error);
    } else if (res.data) {
      setActivePolicy(res.data);
      setSessionPolicies((prev) => [res.data!, ...prev.filter((p) => p.document_hash !== res.data!.document_hash)]);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Copy SHA-256 hash to clipboard
  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  // Toggle clause text expansion
  const toggleClause = (id: string) => {
    setExpandedClauses((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // Execute deterministic rules calculation
  const handleRunCalculation = async (e: React.FormEvent) => {
    e.preventDefault();
    setCalcError(null);
    setCalcLoading(true);

    try {
      const expenseCents = Math.round(parseFloat(calcExpense) * 100);
      const deductibleCents = Math.round(parseFloat(calcDeductible) * 100);
      const coinsurancePct = parseFloat(calcCoinsurance);
      const oopMaxCents = Math.round(parseFloat(calcOopMax) * 100);
      const policyLimitCents = calcPolicyLimit ? Math.round(parseFloat(calcPolicyLimit) * 100) : null;

      if (isNaN(expenseCents) || expenseCents < 0) throw new Error('Eligible expense must be a non-negative amount.');
      if (isNaN(deductibleCents) || deductibleCents < 0) throw new Error('Deductible must be a non-negative amount.');
      if (isNaN(coinsurancePct) || coinsurancePct < 0 || coinsurancePct > 100) {
        throw new Error('Coinsurance must be between 0% and 100%.');
      }
      if (isNaN(oopMaxCents) || oopMaxCents < 0) throw new Error('Out-of-pocket maximum must be non-negative.');

      const res = await calculateCostSharing({
        eligible_expense_cents: expenseCents,
        remaining_deductible_cents: deductibleCents,
        member_coinsurance_percentage: coinsurancePct,
        remaining_out_of_pocket_max_cents: oopMaxCents,
        policy_coverage_limit_cents: policyLimitCents,
        deductible_counts_towards_oop: true,
      });

      setCalcLoading(false);
      if (res.error) {
        setCalcError(res.error);
      } else {
        setCalcResult(res.data);
      }
    } catch (err: unknown) {
      setCalcLoading(false);
      const msg = err instanceof Error ? err.message : 'Invalid numeric values.';
      setCalcError(msg);
    }
  };

  // Filter clauses based on page and search text
  const filteredClauses = activePolicy?.clauses.filter((clause) => {
    const pageMatch = selectedPageFilter === 'all' || clause.page_number === selectedPageFilter;
    const searchMatch =
      !clauseSearch ||
      clause.clause_id.toLowerCase().includes(clauseSearch.toLowerCase()) ||
      (clause.clause_heading && clause.clause_heading.toLowerCase().includes(clauseSearch.toLowerCase())) ||
      clause.text.toLowerCase().includes(clauseSearch.toLowerCase());
    return pageMatch && searchMatch;
  });

  return (
    <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
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
            <span className="text-xs font-semibold text-emerald-600">My Policies</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">
            Policy Vault & Clause Evidence
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Upload PDF insurance contracts, extract verifiable clause references, and simulate cost sharing.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-950/40 dark:text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5" /> Milestone 2 Active
          </span>
        </div>
      </div>

      {/* Upload Dropzone Section */}
      <section className="rounded-2xl border-2 border-dashed border-slate-300 bg-white p-6 dark:border-slate-700 dark:bg-slate-900 shadow-sm">
        <div className="max-w-xl mx-auto text-center space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400">
            <UploadCloud className="h-6 w-6" />
          </div>

          <div>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              Upload Policy Document (PDF)
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Supports policy contracts, benefit schedules, and coverage riders up to 25MB.
            </p>
          </div>

          {/* Hidden File Input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            disabled={isUploading}
            className="hidden"
            id="policy-file-upload"
          />

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <label
              htmlFor="policy-file-upload"
              className="inline-flex items-center gap-2 cursor-pointer rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-750"
            >
              <FileText className="h-4 w-4 text-emerald-600" />
              {selectedFile ? selectedFile.name : 'Select PDF File'}
            </label>

            {selectedFile && (
              <button
                onClick={handleUpload}
                disabled={isUploading}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 disabled:opacity-50 transition-colors"
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    Extracting Clauses with PyMuPDF...
                  </>
                ) : (
                  <>
                    <UploadCloud className="h-4 w-4" />
                    Upload & Extract
                  </>
                )}
              </button>
            )}
          </div>

          {/* Validation Notice */}
          <div className="flex items-center justify-center gap-2 text-[11px] text-slate-400 font-mono">
            <Shield className="h-3 w-3 text-emerald-500" />
            PDF magic bytes (%PDF) inspection &bull; SHA-256 hash &bull; 1-based page indexing
          </div>
        </div>

        {/* Upload Error Banner */}
        {uploadError && (
          <div className="mt-4 max-w-xl mx-auto rounded-xl bg-rose-50 border border-rose-200 p-3.5 text-xs text-rose-700 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-300 flex items-start gap-2.5">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Upload Validation Error</p>
              <p className="mt-0.5">{uploadError}</p>
            </div>
          </div>
        )}
      </section>

      {/* Session Ingested Policies Switcher (if multiple exist) */}
      {sessionPolicies.length > 1 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-2 text-xs">
          <span className="text-slate-400 font-semibold uppercase text-[10px] shrink-0">Switch Policy:</span>
          {sessionPolicies.map((p, idx) => (
            <button
              key={p.document_hash + idx}
              onClick={() => setActivePolicy(p)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-colors whitespace-nowrap ${
                activePolicy?.document_hash === p.document_hash
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300'
              }`}
            >
              {p.document_name} ({p.total_clauses} clauses)
            </button>
          ))}
        </div>
      )}

      {/* Extracted Policy Evidence View */}
      {activePolicy ? (
        <section className="space-y-6">
          {/* Metadata Card */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-5 border-b border-slate-100 dark:border-slate-800">
              <div>
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                    {activePolicy.status === 'success' ? 'Extracted Successfully' : activePolicy.status}
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    Mode: {activePolicy.persistence_mode}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-white mt-1.5 flex items-center gap-2">
                  <FileText className="h-5 w-5 text-emerald-600" />
                  {activePolicy.document_name}
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  {activePolicy.message}
                </p>
              </div>

              {/* SHA-256 Hash Display */}
              <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3 border border-slate-200 dark:border-slate-700 flex flex-col justify-center">
                <div className="flex items-center justify-between gap-3 text-[11px] text-slate-500 dark:text-slate-400">
                  <span className="flex items-center gap-1 font-semibold uppercase tracking-wider text-[10px]">
                    <Hash className="h-3 w-3 text-indigo-500" /> SHA-256 Hash
                  </span>
                  <button
                    onClick={() => handleCopyHash(activePolicy.document_hash)}
                    className="inline-flex items-center gap-1 text-[10px] text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 font-medium"
                  >
                    <Copy className="h-3 w-3" />
                    {copiedHash ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <p className="font-mono text-[11px] text-slate-700 dark:text-slate-300 break-all mt-1 max-w-sm">
                  {activePolicy.document_hash}
                </p>
              </div>
            </div>

            {/* Quick Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-5">
              <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/40">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Total Pages</span>
                <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {activePolicy.total_pages}
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/40">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Clauses Extracted</span>
                <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {activePolicy.total_clauses}
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/40">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Document Size</span>
                <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {(activePolicy.file_size_bytes / 1024).toFixed(1)} KB
                </p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/40">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Digital Text</span>
                <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {activePolicy.has_extractable_text ? 'Verifiable' : 'Scanned / OCR Pending'}
                </p>
              </div>
            </div>
          </div>

          {/* Scanned PDF Notice if OCR unavailable */}
          {activePolicy.is_scanned && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-900/60 dark:bg-amber-950/30">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                    Scanned Document Detected (OCR Staged)
                  </h4>
                  <p className="mt-1 text-xs text-amber-700 dark:text-amber-400 leading-relaxed">
                    This file contains raster images or scanned pages without digital text streams. Under the
                    ClaimWise &quot;Evidence first. If no proof, no answer&quot; standard, we do not hallucinate
                    extracted text when digital proof is absent. Optical Character Recognition (OCR) fallback
                    will be enabled in a future milestone.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Clause Explorer & Filter Controls */}
          {activePolicy.has_extractable_text && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-emerald-600" />
                  <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
                    Verifiable Clause Inspector
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">
                    ({filteredClauses?.length || 0} visible)
                  </span>
                </div>

                {/* Search Bar */}
                <div className="relative w-full sm:w-64">
                  <Search className="h-3.5 w-3.5 absolute left-3 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    value={clauseSearch}
                    onChange={(e) => setClauseSearch(e.target.value)}
                    placeholder="Search clause text or ID..."
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 pl-8 pr-3 py-1.5 text-xs text-slate-700 placeholder-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              {/* Page Number Tabs */}
              {activePolicy.total_pages > 1 && (
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 border-b border-slate-100 dark:border-slate-800 text-xs">
                  <button
                    onClick={() => setSelectedPageFilter('all')}
                    className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                      selectedPageFilter === 'all'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
                    }`}
                  >
                    All Pages ({activePolicy.total_clauses})
                  </button>
                  {activePolicy.pages.map((p) => (
                    <button
                      key={p.page_number}
                      onClick={() => setSelectedPageFilter(p.page_number)}
                      className={`px-3 py-1.5 rounded-lg font-medium transition-colors whitespace-nowrap ${
                        selectedPageFilter === p.page_number
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
                      }`}
                    >
                      Page {p.page_number} ({p.clause_count})
                    </button>
                  ))}
                </div>
              )}

              {/* Clauses Accordion List */}
              <div className="space-y-3">
                {filteredClauses && filteredClauses.length > 0 ? (
                  filteredClauses.map((clause: ExtractedClause, idx: number) => {
                    const isExpanded = !!expandedClauses[clause.clause_id + idx];
                    return (
                      <div
                        key={clause.clause_id + idx}
                        className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 transition-all dark:border-slate-800 dark:bg-slate-850"
                      >
                        <div
                          onClick={() => toggleClause(clause.clause_id + idx)}
                          className="flex items-start justify-between gap-3 cursor-pointer select-none"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                              {clause.clause_id}
                            </span>
                            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300">
                              Page {clause.page_number}
                            </span>
                            {clause.clause_heading && (
                              <span className="text-xs font-medium text-slate-800 dark:text-slate-200">
                                {clause.clause_heading}
                              </span>
                            )}
                            <span className="text-[10px] text-slate-400 capitalize">
                              ({clause.heading_confidence} confidence)
                            </span>
                          </div>

                          <button className="text-slate-400 hover:text-slate-600">
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </button>
                        </div>

                        {/* Clause Verbatim Text Snippet */}
                        <div className="mt-2.5">
                          <p
                            className={`text-xs text-slate-600 dark:text-slate-300 leading-relaxed font-mono ${
                              isExpanded ? '' : 'line-clamp-2'
                            }`}
                          >
                            {clause.text}
                          </p>
                        </div>

                        {/* Tokens & Evidence Footer */}
                        <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400 pt-2 border-t border-slate-200/60 dark:border-slate-800">
                          <span>~{clause.token_count} tokens</span>
                          <span className="font-mono">Doc Hash: {clause.document_hash.substring(0, 12)}...</span>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="py-8 text-center text-xs text-slate-400">
                    No clauses match the current filter criteria.
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      ) : (
        /* Empty State */
        <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-400 dark:bg-slate-800 mb-3">
            <FileText className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
            No Policy Uploaded Yet
          </h3>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
            Select a PDF document above to begin ingestion. ClaimWise will parse clauses, extract 1-based page
            references, and prepare evidence citations.
          </p>
        </section>
      )}

      {/* Interactive Deterministic Rules Engine Simulator */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-4 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Calculator className="h-5 w-5 text-emerald-600" />
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                Deterministic Cost-Sharing Calculator
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Pure Python mathematical engine operating in integer cents. No LLM arithmetic.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40 px-2.5 py-1 rounded-md">
            POST /api/v1/rules/calculate
          </span>
        </div>

        {/* Calculator Form */}
        <form onSubmit={handleRunCalculation} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div>
            <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Eligible Expense ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={calcExpense}
              onChange={(e) => setCalcExpense(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Remaining Deductible ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={calcDeductible}
              onChange={(e) => setCalcDeductible(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Member Coinsurance (%)
            </label>
            <input
              type="number"
              step="1"
              min="0"
              max="100"
              required
              value={calcCoinsurance}
              onChange={(e) => setCalcCoinsurance(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Remaining Out-of-Pocket Max ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={calcOopMax}
              onChange={(e) => setCalcOopMax(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Policy Limit (Optional $)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              placeholder="e.g. 50000"
              value={calcPolicyLimit}
              onChange={(e) => setCalcPolicyLimit(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
            />
          </div>

          <div className="sm:col-span-2 lg:col-span-5 flex justify-end">
            <button
              type="submit"
              disabled={calcLoading}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
            >
              {calcLoading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Calculator className="h-4 w-4" />}
              Run Deterministic Calculation
            </button>
          </div>
        </form>

        {calcError && (
          <div className="rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-300">
            {calcError}
          </div>
        )}

        {/* Calculation Result Breakdown Cards */}
        {calcResult && (
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-5 dark:border-slate-800 dark:bg-slate-850 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Calculation Breakdown
            </h4>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="rounded-xl bg-white p-3 border border-slate-200 dark:border-slate-700 dark:bg-slate-800">
                <span className="text-[10px] uppercase font-semibold text-slate-400">Member Responsibility</span>
                <p className="text-base font-bold text-emerald-600 mt-0.5">
                  ${(calcResult.member_total_cents / 100).toFixed(2)}
                </p>
              </div>

              <div className="rounded-xl bg-white p-3 border border-slate-200 dark:border-slate-700 dark:bg-slate-800">
                <span className="text-[10px] uppercase font-semibold text-slate-400">Insurer Responsibility</span>
                <p className="text-base font-bold text-indigo-600 mt-0.5">
                  ${(calcResult.insurer_total_cents / 100).toFixed(2)}
                </p>
              </div>

              <div className="rounded-xl bg-white p-3 border border-slate-200 dark:border-slate-700 dark:bg-slate-800">
                <span className="text-[10px] uppercase font-semibold text-slate-400">Deductible Applied</span>
                <p className="text-base font-bold text-slate-800 dark:text-slate-200 mt-0.5">
                  ${(calcResult.deductible_paid_cents / 100).toFixed(2)}
                </p>
              </div>

              <div className="rounded-xl bg-white p-3 border border-slate-200 dark:border-slate-700 dark:bg-slate-800">
                <span className="text-[10px] uppercase font-semibold text-slate-400">Coinsurance Paid</span>
                <p className="text-base font-bold text-slate-800 dark:text-slate-200 mt-0.5">
                  ${(calcResult.member_coinsurance_cents / 100).toFixed(2)}
                </p>
              </div>
            </div>

            {/* Step-by-step audit log */}
            <div className="pt-2">
              <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                Deterministic Audit Steps:
              </span>
              <ul className="mt-1.5 space-y-1 text-xs text-slate-500 dark:text-slate-400 font-mono">
                {calcResult.calculation_steps.map((step, idx) => (
                  <li key={idx} className="flex items-start gap-1.5">
                    <span className="text-emerald-500 font-bold">&rsaquo;</span> {step}
                  </li>
                ))}
              </ul>
            </div>

            {/* Educational Disclaimer */}
            <div className="rounded-lg bg-amber-50/80 border border-amber-200/60 p-3 text-[11px] text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-300">
              <span className="font-semibold">Educational Simulation Notice: </span>
              {calcResult.disclaimer}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
