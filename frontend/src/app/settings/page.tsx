'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Lock,
  Server,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  XCircle,
  RefreshCw,
  Hash,
  Database,
} from 'lucide-react';
import { getBackendBaseUrl, fetchAuditEvents, verifyAuditChain } from '@/lib/api';
import { AuditEvent, AuditVerificationResult } from '@/types/api';

export default function SettingsPage() {
  const backendUrl = getBackendBaseUrl();
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [isLoadingAudit, setIsLoadingAudit] = useState<boolean>(true);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verificationResult, setVerificationResult] = useState<AuditVerificationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refreshAuditEvents = async () => {
    setIsLoadingAudit(true);
    const res = await fetchAuditEvents({ limit: 15 });
    setIsLoadingAudit(false);
    if (res.data) {
      setAuditEvents(res.data);
    }
  };

  useEffect(() => {
    let isMounted = true;
    fetchAuditEvents({ limit: 15 }).then((res) => {
      if (isMounted) {
        setIsLoadingAudit(false);
        if (res.data) {
          setAuditEvents(res.data);
        }
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleVerifyChain = async () => {
    setIsVerifying(true);
    setErrorMessage(null);
    const res = await verifyAuditChain();
    setIsVerifying(false);

    if (res.error) {
      setErrorMessage(res.error);
      return;
    }

    if (res.data) {
      setVerificationResult(res.data);
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
              className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            >
              <ArrowLeft className="h-3 w-3" /> Dashboard
            </Link>
            <span className="text-slate-300">/</span>
            <span className="text-xs font-semibold text-emerald-600">Settings & Security</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white mt-1">
            System Settings & Security Architecture
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Manage API connections, verify cryptographic audit hash-chains, and inspect Row Level Security policies.
          </p>
        </div>
      </div>

      {errorMessage && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Security Architecture Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: API & Environment Configuration */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <Server className="h-5 w-5 text-emerald-600" />
            <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
              Backend Connectivity & Environment Mode
            </h2>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <label className="text-slate-500 font-medium">Configured Backend Base URL</label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={backendUrl}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                />
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                Configured via <code className="font-mono">NEXT_PUBLIC_API_URL</code> environment variable.
              </p>
            </div>

            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-2">
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                Security & Service Checklist:
              </span>
              <ul className="space-y-1.5 text-slate-600 dark:text-slate-400">
                <li className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    <span>FastAPI Application Core</span>
                  </div>
                  <span className="font-mono text-[10px] bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 px-2 py-0.5 rounded">
                    ONLINE
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    <span>Authentication Verification</span>
                  </div>
                  <span className="font-mono text-[10px] bg-indigo-100 dark:bg-indigo-950 text-indigo-800 dark:text-indigo-300 px-2 py-0.5 rounded">
                    SUPABASE HS256 JWT
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    <span>Deterministic Financial Engine</span>
                  </div>
                  <span className="font-mono text-[10px] bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 px-2 py-0.5 rounded">
                    INTEGER-CENTS
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    <span>Document Retrieval Mode</span>
                  </div>
                  <span className="font-mono text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded">
                    BM25 + RRF
                  </span>
                </li>
                <li className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="h-3.5 w-3.5 text-amber-500" />
                    <span>Remote Supabase DB Pooler</span>
                  </div>
                  <span className="font-mono text-[10px] bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 px-2 py-0.5 rounded">
                    BLOCKED (Awaiting Live Config)
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Card 2: Row Level Security & Authorization */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <Lock className="h-5 w-5 text-indigo-600" />
            <h2 className="font-semibold text-sm text-slate-900 dark:text-white">
              Row Level Security (RLS) Policy Audit
            </h2>
          </div>

          <div className="text-xs space-y-3">
            <div className="rounded-xl bg-slate-50 p-3.5 dark:bg-slate-800/50 space-y-1.5">
              <span className="font-semibold text-slate-800 dark:text-slate-200">
                Non-Permissive Ownership Rules:
              </span>
              <p className="text-slate-500 dark:text-slate-400 leading-relaxed text-[11px]">
                PostgreSQL RLS ensures that all queries are scoped strictly to the authenticated caller
                using <code className="font-mono">auth.uid() = user_id</code>. Client-supplied user IDs in request
                payloads are untrusted and discarded. Cross-tenant access attempts return HTTP 403 Forbidden.
              </p>
            </div>

            <div className="space-y-2">
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                Protected Tables in Schema Migrations 001–004:
              </span>
              <div className="grid grid-cols-2 gap-1.5 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-1">profiles</span>
                <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-1">policies</span>
                <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-1">policy_chunks</span>
                <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-1">claims</span>
                <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-1">claim_documents</span>
                <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-1">comparisons</span>
                <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-1">audit_logs</span>
                <span className="rounded bg-slate-100 dark:bg-slate-800 px-2 py-1">consents</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Card 3: Cryptographic Audit Trail & Hash-Chain Verification */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <Hash className="h-5 w-5 text-emerald-600" />
              <h2 className="font-semibold text-base text-slate-900 dark:text-white">
                Cryptographic Audit Trail (SHA-256 Hash Chain)
              </h2>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Tamper-evident hash-chain linking sensitive actions: uploads, adjudications, appeal generation, and PDF exports.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleVerifyChain}
              disabled={isVerifying}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {isVerifying ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Verifying Hashes...
                </>
              ) : (
                <>
                  <ShieldCheck className="h-3.5 w-3.5" /> Verify Chain Integrity
                </>
              )}
            </button>
          </div>
        </div>

        {/* Verification Result Display */}
        {verificationResult && (
          <div
            className={`rounded-xl border p-4 text-xs transition ${
              verificationResult.is_valid
                ? 'border-emerald-300 bg-emerald-50/70 text-emerald-900 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300'
                : 'border-red-300 bg-red-50/70 text-red-900 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 font-bold text-sm">
                {verificationResult.is_valid ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                    <span>Audit Chain Status: MATHEMATICALLY VERIFIED</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                    <span>Audit Chain Status: TAMPER DETECTED</span>
                  </>
                )}
              </div>
              <span className="font-mono text-[11px]">
                {verificationResult.verified_count} / {verificationResult.total_events} Events Valid
              </span>
            </div>
            <p className="text-xs leading-relaxed">
              {verificationResult.is_valid
                ? 'All sequential SHA-256 hashes match. No tampering or reordering detected.'
                : verificationResult.error_reason || 'Tampering detected in chain.'}
            </p>
            {verificationResult.chain_head_hash && (
              <p className="mt-2 text-[11px] font-mono truncate">
                Last Root Hash: {verificationResult.chain_head_hash}
              </p>
            )}
          </div>
        )}

        {/* Audit Events Log Table */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
              Recent User Audit Events ({auditEvents.length})
            </h3>
            <button
              type="button"
              onClick={refreshAuditEvents}
              disabled={isLoadingAudit}
              className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 inline-flex items-center gap-1"
            >
              <RefreshCw className={`h-3 w-3 ${isLoadingAudit ? 'animate-spin' : ''}`} /> Refresh Log
            </button>
          </div>

          {auditEvents.length === 0 ? (
            <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-6 text-center text-xs text-slate-400 dark:border-slate-800 dark:bg-slate-800/40">
              No audit events recorded yet for this session. Perform an action (e.g. upload policy, run claim adjudication, or export PDF) to initiate the chain.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-semibold text-slate-600 dark:text-slate-300 text-[11px]">
                  <tr>
                    <th className="py-2.5 px-3">Seq</th>
                    <th className="py-2.5 px-3">Action</th>
                    <th className="py-2.5 px-3">Resource</th>
                    <th className="py-2.5 px-3">Outcome</th>
                    <th className="py-2.5 px-3">Timestamp (UTC)</th>
                    <th className="py-2.5 px-3">SHA-256 Hash</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/50 font-mono text-[11px]">
                  {auditEvents.map((evt) => (
                    <tr key={evt.event_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                      <td className="py-2 px-3 text-slate-500">#{evt.sequence_number}</td>
                      <td className="py-2 px-3 font-semibold text-slate-900 dark:text-white font-sans">
                        {evt.action}
                      </td>
                      <td className="py-2 px-3 text-slate-600 dark:text-slate-400">
                        {evt.resource_type}:{evt.resource_id ? evt.resource_id.substring(0, 8) + '...' : 'none'}
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                            evt.outcome === 'success'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                              : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                          }`}
                        >
                          {evt.outcome}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-500">{new Date(evt.timestamp).toLocaleTimeString()}</td>
                      <td className="py-2 px-3 text-emerald-700 dark:text-emerald-400 truncate max-w-[120px]">
                        {evt.event_hash.substring(0, 16)}...
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

