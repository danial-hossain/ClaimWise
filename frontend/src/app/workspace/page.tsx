'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Bot,
  FileText,
  Search,
  Sparkles,
  AlertCircle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Send,
  RefreshCw,
  ShieldCheck,
  Layers,
  ExternalLink,
  Clock,
} from 'lucide-react';
import { fetchUploadedPolicies, askPolicyQuestion, fetchQAPipelineStatus } from '@/lib/api';
import {
  PolicyExtractionResult,
  QAResponse,
  QAPipelineStatus,
  VerifiedCitation,
  RetrievedEvidenceClause,
} from '@/types/api';

export default function AIWorkspacePage() {
  const [policies, setPolicies] = useState<PolicyExtractionResult[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string>('');
  const [pipelineStatus, setPipelineStatus] = useState<QAPipelineStatus | null>(null);
  const [question, setQuestion] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentResponse, setCurrentResponse] = useState<QAResponse | null>(null);
  const [qaHistory, setQaHistory] = useState<QAResponse[]>([]);
  const [expandedEvidenceId, setExpandedEvidenceId] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<VerifiedCitation | null>(null);

  // Suggested prompts
  const samplePrompts = [
    'What is the emergency room copayment?',
    'What is the annual deductible for in-network care?',
    'Are pre-existing condition exclusions subject to a waiting period?',
    'What is the out-of-pocket maximum limit?',
  ];

  useEffect(() => {
    async function initWorkspace() {
      // 1. Load uploaded policies
      const polRes = await fetchUploadedPolicies();
      if (polRes.data && polRes.data.length > 0) {
        setPolicies(polRes.data);
        // Default to first policy if available
        const firstWithId = polRes.data.find((p) => p.policy_id);
        if (firstWithId && firstWithId.policy_id) {
          setSelectedPolicyId(firstWithId.policy_id);
        } else if (polRes.data[0].policy_id) {
          setSelectedPolicyId(polRes.data[0].policy_id);
        }
      }

      // 2. Fetch retrieval & LLM pipeline health
      const statusRes = await fetchQAPipelineStatus();
      if (statusRes.data) {
        setPipelineStatus(statusRes.data);
      }
    }

    initWorkspace();
  }, []);

  const handleSubmitQuestion = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanQ = question.trim();
    if (!cleanQ || isSubmitting) return;

    if (!selectedPolicyId && policies.length === 0) {
      setErrorMessage('Please upload a policy document in My Policies first.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const res = await askPolicyQuestion({
      question: cleanQ,
      policy_id: selectedPolicyId || undefined,
    });

    setIsSubmitting(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setCurrentResponse(res.data);
      setQaHistory((prev) => [res.data as QAResponse, ...prev]);
      if (res.data.citations.length > 0) {
        setActiveCitation(res.data.citations[0]);
      } else {
        setActiveCitation(null);
      }
    }
  };

  const handlePromptClick = (promptText: string) => {
    setQuestion(promptText);
  };

  const selectedPolicy = policies.find((p) => p.policy_id === selectedPolicyId) || policies[0];

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
            <span className="text-xs font-semibold text-emerald-600">AI Workspace</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">
            Evidence-Grounded Policy AI
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            ClaimWise Tagline: <span className="font-semibold italic text-slate-700 dark:text-slate-300">&ldquo;Evidence first. If no proof, no answer.&rdquo;</span>
          </p>
        </div>

        {/* Pipeline Status Indicator */}
        <div className="flex flex-wrap items-center gap-2">
          {pipelineStatus && (
            <div className="inline-flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-1.5 text-xs border border-slate-200 dark:bg-slate-800/80 dark:border-slate-700">
              <span className="flex items-center gap-1 font-mono text-[11px] text-slate-600 dark:text-slate-300">
                <Layers className="h-3.5 w-3.5 text-emerald-600" />
                BM25 ({pipelineStatus.bm25_lexical.indexed_clauses_count} clauses)
              </span>
              <span className="text-slate-300">&bull;</span>
              <span className="flex items-center gap-1 font-mono text-[11px] text-slate-600 dark:text-slate-300">
                {pipelineStatus.dense_embeddings.status === 'blocked' ? (
                  <span className="text-amber-600 dark:text-amber-400" title={pipelineStatus.dense_embeddings.blocker_reason || ''}>
                    Dense: Blocked
                  </span>
                ) : (
                  <span className="text-emerald-600">Dense: 1024d</span>
                )}
              </span>
              <span className="text-slate-300">&bull;</span>
              <span className="flex items-center gap-1 font-mono text-[11px] text-slate-600 dark:text-slate-300">
                <Bot className="h-3.5 w-3.5 text-indigo-500" />
                {pipelineStatus.gemini_engine.model_name}
              </span>
            </div>
          )}
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-950/40 dark:text-emerald-400">
            <ShieldCheck className="h-3.5 w-3.5" />
            Milestone 3: Grounded Q&A
          </span>
        </div>
      </div>

      {/* Policy Selector & Scope Bar */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <label htmlFor="policy-select" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
              Authorized Policy Document
            </label>
            <p className="text-[11px] text-slate-500">
              {selectedPolicy
                ? `Active: ${selectedPolicy.document_name} (${selectedPolicy.total_pages} pages, ${selectedPolicy.total_clauses} clauses). Isolated scope.`
                : 'Evidence search is strictly isolated to your selected document.'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
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
                Upload Policy <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Main Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Inquiry Console & Answer Results */}
        <div className="lg:col-span-2 space-y-6">
          {/* Question Form */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-emerald-600" />
                <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
                  Ask a Policy Question
                </h2>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Mode: Verified Citations
              </span>
            </div>

            <form onSubmit={handleSubmitQuestion} className="mt-4 space-y-4">
              <div>
                <textarea
                  rows={3}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      handleSubmitQuestion();
                    }
                  }}
                  placeholder="e.g. What is my copayment for an emergency room visit, and does it apply before the deductible?"
                  disabled={isSubmitting || policies.length === 0}
                  className="w-full rounded-xl border border-slate-200 p-3.5 text-xs text-slate-800 placeholder-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800/80 dark:text-slate-100 dark:placeholder-slate-500 disabled:opacity-50"
                />
              </div>

              {/* Sample Prompts */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                  Sample Inquiries:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {samplePrompts.map((promptText, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handlePromptClick(promptText)}
                      disabled={isSubmitting || policies.length === 0}
                      className="rounded-full bg-slate-100 px-3 py-1 text-[11px] text-slate-600 hover:bg-emerald-50 hover:text-emerald-700 transition dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 disabled:opacity-50"
                    >
                      {promptText}
                    </button>
                  ))}
                </div>
              </div>

              {errorMessage && (
                <div className="rounded-xl bg-red-50 p-3 border border-red-200 text-xs text-red-700 flex items-start gap-2 dark:bg-red-950/40 dark:border-red-900/50 dark:text-red-300">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-red-500" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <span className="text-[11px] text-slate-400">
                  Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px]">Ctrl+Enter</kbd> to ask
                </span>

                <button
                  type="submit"
                  disabled={isSubmitting || !question.trim() || policies.length === 0}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 transition"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      Retrieving & Verifying...
                    </>
                  ) : (
                    <>
                      <Send className="h-3.5 w-3.5" />
                      Ask ClaimWise
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Active Answer Card */}
          {currentResponse && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-5">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-emerald-600" />
                  <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
                    Verified Answer
                  </h3>
                </div>
                <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" /> {currentResponse.latency_ms}ms
                  </span>
                  <span>&bull;</span>
                  <span>Mode: {currentResponse.retrieval_mode}</span>
                </div>
              </div>

              {/* Insufficient Evidence / Honest Abstention Banner */}
              {!currentResponse.evidence_sufficient && (
                <div className="rounded-xl bg-amber-50 p-4 border border-amber-200 dark:bg-amber-950/40 dark:border-amber-900/50 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-amber-800 dark:text-amber-300">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                    <span>ClaimWise Honest Abstention: Evidence Not Established</span>
                  </div>
                  {currentResponse.abstention_reason && (
                    <p className="text-xs text-amber-700 dark:text-amber-400 leading-relaxed pl-6">
                      {currentResponse.abstention_reason}
                    </p>
                  )}
                  {currentResponse.clarification_question && (
                    <div className="mt-2 pl-6 pt-2 border-t border-amber-200/60 dark:border-amber-900/40">
                      <span className="text-[11px] font-semibold text-amber-900 dark:text-amber-200">
                        Suggested Clarification for your Insurer:
                      </span>
                      <p className="text-xs text-amber-800 dark:text-amber-300 mt-0.5 italic">
                        &ldquo;{currentResponse.clarification_question}&rdquo;
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Answer Text */}
              <div className="space-y-3">
                <p className="text-xs leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-line font-sans">
                  {currentResponse.answer}
                </p>

                {/* Verified Citations List */}
                {currentResponse.citations.length > 0 && (
                  <div className="pt-3 border-t border-slate-100 dark:border-slate-800 space-y-2">
                    <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                      Verified Clause Citations:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {currentResponse.citations.map((cit, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => setActiveCitation(cit)}
                          className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-mono transition border ${
                            activeCitation?.clause_id === cit.clause_id
                              ? 'bg-emerald-50 border-emerald-300 text-emerald-800 dark:bg-emerald-950/60 dark:border-emerald-700 dark:text-emerald-300 shadow-sm'
                              : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300'
                          }`}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                          <span className="font-bold">{cit.clause_id}</span>
                          <span className="text-slate-400">&bull;</span>
                          <span>Page {cit.page_number}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Previous Questions in Session */}
          {qaHistory.length > 1 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-3">
              <h3 className="font-semibold text-xs text-slate-500 uppercase tracking-wider">
                Session History ({qaHistory.length} Inquiries)
              </h3>
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {qaHistory.slice(1).map((hist, idx) => (
                  <div
                    key={idx}
                    onClick={() => {
                      setCurrentResponse(hist);
                      if (hist.citations.length > 0) setActiveCitation(hist.citations[0]);
                    }}
                    className="p-3 rounded-xl bg-slate-50 hover:bg-slate-100 border border-slate-100 cursor-pointer transition dark:bg-slate-800/60 dark:hover:bg-slate-800 dark:border-slate-700/60 text-xs"
                  >
                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mb-1">
                      <span>{new Date(hist.created_at).toLocaleTimeString()}</span>
                      <span>
                        {hist.evidence_sufficient ? (
                          <span className="text-emerald-600 font-semibold">&bull; Grounded</span>
                        ) : (
                          <span className="text-amber-600 font-semibold">&bull; Abstained</span>
                        )}
                      </span>
                    </div>
                    <p className="font-medium text-slate-800 dark:text-slate-200 line-clamp-1">
                      {hist.question}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Col: Citation & Evidence Inspector */}
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
              <FileText className="h-5 w-5 text-indigo-600" />
              <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
                Citation & Evidence Inspector
              </h2>
            </div>

            {activeCitation ? (
              <div className="space-y-3">
                <div className="rounded-xl bg-emerald-50/80 p-3.5 border border-emerald-200 dark:bg-emerald-950/40 dark:border-emerald-900/50 space-y-1">
                  <div className="flex items-center justify-between font-mono text-[11px] text-emerald-800 dark:text-emerald-300">
                    <span className="font-bold flex items-center gap-1">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      {activeCitation.clause_id}
                    </span>
                    <span>Document Page {activeCitation.page_number}</span>
                  </div>
                  {activeCitation.clause_heading && (
                    <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                      {activeCitation.clause_heading}
                    </p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    Verbatim Document Quote:
                  </span>
                  <div className="rounded-xl bg-slate-50 p-3.5 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 font-serif italic leading-relaxed">
                    &ldquo;{activeCitation.exact_quote}&rdquo;
                  </div>
                  <span className="text-[10px] text-emerald-600 flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" /> Exact match verified against ingested PDF clause
                  </span>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-center dark:border-slate-800">
                <Search className="h-6 w-6 text-slate-400 mx-auto mb-2" />
                <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  No Citation Selected
                </h4>
                <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                  Ask a question or click any verified citation pill to inspect verbatim proof excerpts.
                </p>
              </div>
            )}

            {/* Retrieved Evidence Set Drawer */}
            {currentResponse && currentResponse.retrieved_evidence.length > 0 && (
              <div className="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
                <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Retrieved Evidence Pool ({currentResponse.retrieved_evidence.length})</span>
                  <span className="font-mono text-[10px] text-slate-400">RRF Top-K</span>
                </span>

                <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                  {currentResponse.retrieved_evidence.map((clause: RetrievedEvidenceClause) => {
                    const isExpanded = expandedEvidenceId === clause.clause_id;
                    return (
                      <div
                        key={clause.clause_id}
                        className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 text-xs dark:border-slate-700/60 dark:bg-slate-800/40"
                      >
                        <div
                          className="flex items-center justify-between cursor-pointer"
                          onClick={() => setExpandedEvidenceId(isExpanded ? null : clause.clause_id)}
                        >
                          <div className="flex items-center gap-1.5 font-mono text-[11px]">
                            <span className="font-bold text-slate-800 dark:text-slate-200">
                              {clause.clause_id}
                            </span>
                            <span className="text-slate-400">&bull;</span>
                            <span className="text-slate-500">P.{clause.page_number}</span>
                          </div>
                          <div className="flex items-center gap-1 text-[11px] text-slate-400">
                            {clause.fused_rank && <span>Rank #{clause.fused_rank}</span>}
                            {isExpanded ? (
                              <ChevronUp className="h-3.5 w-3.5" />
                            ) : (
                              <ChevronDown className="h-3.5 w-3.5" />
                            )}
                          </div>
                        </div>

                        {clause.clause_heading && (
                          <p className="text-[11px] font-medium text-slate-600 dark:text-slate-300 mt-1 line-clamp-1">
                            {clause.clause_heading}
                          </p>
                        )}

                        {isExpanded && (
                          <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-700 space-y-2">
                            <p className="text-[11px] text-slate-600 dark:text-slate-300 font-mono leading-relaxed bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-100 dark:border-slate-800">
                              {clause.text}
                            </p>
                            <div className="flex flex-wrap gap-2 text-[10px] font-mono text-slate-400">
                              {clause.lexical_rank && <span>BM25: #{clause.lexical_rank}</span>}
                              {clause.dense_rank && <span>Dense: #{clause.dense_rank}</span>}
                              {clause.rrf_score && <span>RRF: {clause.rrf_score.toFixed(4)}</span>}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Evidence First Guarantee Card */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-2">
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Evidence-First Integrity Guarantee
            </span>
            <p className="text-[11px] text-slate-500 leading-relaxed dark:text-slate-400">
              ClaimWise enforces deterministic post-generation citation validation. Every cited clause ID, page number, and quote is cross-referenced against the extracted PDF bytes. If proof is missing or altered, the claim is rejected and an honest abstention is returned.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
