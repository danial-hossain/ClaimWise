'use client';

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  Activity,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Check,
  Clock3,
  CircleAlert,
  CircleDot,
  Search,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  FileText,
  ClipboardList,
  CheckCircle2,
  Hash,
  ExternalLink,
  Lock,
  Layers,
  Sparkles,
  ArrowRight,
  Database,
  KeyRound,
  FileCheck,
} from 'lucide-react';
import { GlassPanel, GlassCard } from '@/components/ui/Glass';
import EmptyState from '@/components/ui/EmptyState';
import { Skeleton, StaggerGroup, StaggerItem } from '@/components/ui/Motion';
import { useAuth } from '@/context/AuthContext';
import { fetchAuditEvents, verifyAuditChain } from '@/lib/api';
import type { AuditEvent, AuditVerificationResult } from '@/types/api';

// ==============================================================================
// HELPERS
// ==============================================================================

function formatActionTitle(action: string): string {
  const map: Record<string, string> = {
    'policy.upload': 'Policy Uploaded',
    'policy.delete': 'Policy Deleted',
    'coverage.analyze': 'Coverage Evaluated',
    'claim.create': 'Claim Draft Created',
    'claim.adjudicate': 'Claim Adjudicated',
    'claim.upload_bill': 'Medical Bill Analyzed',
    'claim.document.download': 'Evidence Downloaded',
    'claim.delete': 'Claim Removed',
    'sandbox.submit': 'Payer Simulation Submitted',
    'appeal.generate': 'Appeal Draft Generated',
    'appeal.edit': 'Appeal Draft Updated',
    'appeal.export_pdf': 'Appeal PDF Exported',
    'comparison.create': 'Policies Compared',
    'comparison.simulate_cost': 'Cost Simulation Generated',
    'qa.ask': 'Policy Q&A Queried',
    'auth.signup': 'Account Registered',
    'auth.login': 'User Signed In',
    'auth.logout': 'User Signed Out',
    'auth.login_failed': 'Sign In Attempt Failed',
    'auth.rotate_token': 'Session Token Rotated',
  };
  return map[action] || action.replace(/[._]/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

function getActionIcon(action: string) {
  if (action.startsWith('policy.')) return FileText;
  if (action.startsWith('claim.')) return ClipboardList;
  if (action.startsWith('coverage.')) return CheckCircle2;
  if (action.startsWith('auth.')) return KeyRound;
  if (action.startsWith('appeal.')) return FileCheck;
  return Activity;
}

function formatEventTime(timestamp: string): { time: string; date: string; full: string } {
  try {
    const d = new Date(timestamp);
    if (isNaN(d.getTime())) return { time: '—', date: '—', full: '—' };
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    const date = d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
    const full = `${date} at ${time}`;
    return { time, date, full };
  } catch {
    return { time: '—', date: '—', full: '—' };
  }
}

function formatOutcome(outcome?: string): { label: string; tone: 'success' | 'pending' | 'issue' | 'neutral' } {
  const normalized = outcome?.trim().toLowerCase().replace(/[._-]+/g, ' ') || '';
  const label = normalized
    ? normalized.replace(/\b\w/g, (letter) => letter.toUpperCase())
    : 'Recorded';

  if (['success', 'completed', 'healthy', 'covered', 'adjudicated', 'valid'].includes(normalized)) {
    return { label, tone: 'success' };
  }
  if (['pending', 'processing', 'queued', 'in progress', 'review'].includes(normalized)) {
    return { label, tone: 'pending' };
  }
  if (['failed', 'error', 'rejected', 'denied', 'invalid', 'tampered'].includes(normalized)) {
    return { label, tone: 'issue' };
  }
  return { label, tone: 'neutral' };
}

// ==============================================================================
// COMPONENT
// ==============================================================================

type AuditRequest = {
  userId: string | undefined;
  page: number;
  pageSize: number;
  actionFilter: string;
  outcomeFilter: string;
  version: number;
};

export default function ActivityPage() {
  const { user, isAuthenticated, openAuthModal } = useAuth();

  const [eventResult, setEventResult] = useState<{
    userId: string;
    requestKey: AuditRequest;
    events: AuditEvent[];
    total: number;
    error: string | null;
  } | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);

  // Filters & Pagination
  const [actionFilter, setActionFilter] = useState<string>('all');
  const [outcomeFilter, setOutcomeFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(25);

  // Expanded event rows
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // Chain Verification
  const [verificationResult, setVerificationResult] = useState<{
    userId: string;
    requestKey: AuditRequest;
    data: AuditVerificationResult | null;
  } | null>(null);
  const [verificationVersion, setVerificationVersion] = useState(0);

  const userId = isAuthenticated ? user?.id : undefined;
  const eventRequestKey = useMemo<AuditRequest>(() => ({
    userId, page, pageSize, actionFilter, outcomeFilter, version: refreshVersion,
  }), [userId, page, pageSize, actionFilter, outcomeFilter, refreshVersion]);
  const verificationRequestKey = useMemo<AuditRequest>(() => ({
    userId, page, pageSize, actionFilter, outcomeFilter, version: verificationVersion,
  }), [userId, page, pageSize, actionFilter, outcomeFilter, verificationVersion]);
  const currentEvents = eventResult?.userId === userId ? eventResult : null;
  const events = useMemo(() => currentEvents?.events ?? [], [currentEvents]);
  const totalCount = currentEvents?.total ?? 0;
  const loading = Boolean(userId) && currentEvents?.requestKey !== eventRequestKey;
  const error = loading ? null : currentEvents?.error ?? null;
  const verification = verificationResult && verificationResult.userId === userId ? verificationResult.data : null;
  const verifying = Boolean(userId) && verificationResult?.requestKey !== verificationRequestKey;

  const loadEvents = () => setRefreshVersion((version) => version + 1);
  const handleVerifyChain = () => setVerificationVersion((version) => version + 1);

  const toggleExpand = (eventId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  };

  // Loading is derived from the active request; only completed requests set state.
  useEffect(() => {
    const { userId, page, pageSize, actionFilter, outcomeFilter } = eventRequestKey;
    if (!userId) return;
    let ignore = false;
    const params = {
      action: actionFilter === 'all' ? undefined : actionFilter,
      outcome: outcomeFilter === 'all' ? undefined : outcomeFilter,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    };

    const fetchEvents = async () => {
      try {
        const result = await fetchAuditEvents(params);
        if (ignore) return;
        setEventResult({
          userId,
          requestKey: eventRequestKey,
          events: result.error ? [] : result.data || [],
          total: result.error ? 0 : result.total || (result.data ? result.data.length : 0),
          error: result.error,
        });
      } catch (err: unknown) {
        if (ignore) return;
        setEventResult({
          userId,
          requestKey: eventRequestKey,
          events: [],
          total: 0,
          error: err instanceof Error ? err.message : 'Failed to retrieve activity events.',
        });
      }
    };

    void fetchEvents();
    return () => { ignore = true; };
  }, [eventRequestKey]);

  // Retain the last verification on failure, but never reuse another account's result.
  useEffect(() => {
    const { userId } = verificationRequestKey;
    if (!userId) return;
    let ignore = false;
    const verify = async () => {
      let data: AuditVerificationResult | null = null;
      try {
        const result = await verifyAuditChain();
        data = result.data;
      } catch {
        // Preserve the existing non-blocking verification error behavior.
      }

      if (ignore) return;
      setVerificationResult((previous) => ({
        userId,
        requestKey: verificationRequestKey,
        data: data ?? (previous?.userId === userId ? previous.data : null),
      }));
    };

    void verify();
    return () => { ignore = true; };
  }, [verificationRequestKey]);

  // Client-side search filtering (by resource_id, filename, or event_id)
  const filteredEvents = useMemo(() => {
    if (!searchQuery.trim()) return events;
    const q = searchQuery.toLowerCase().trim();
    return events.filter((ev) => {
      const resource = (ev.resource_id || '').toLowerCase();
      const action = (ev.action || '').toLowerCase();
      const filename = (typeof ev.metadata?.filename === 'string' ? ev.metadata.filename : '').toLowerCase();
      const title = (typeof ev.metadata?.title === 'string' ? ev.metadata.title : '').toLowerCase();
      const eventId = (ev.event_id || '').toLowerCase();
      return (
        resource.includes(q) ||
        action.includes(q) ||
        filename.includes(q) ||
        title.includes(q) ||
        eventId.includes(q)
      );
    });
  }, [events, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const isFilterActive = actionFilter !== 'all' || outcomeFilter !== 'all' || searchQuery.trim() !== '';

  const resetFilters = () => {
    setActionFilter('all');
    setOutcomeFilter('all');
    setSearchQuery('');
    setPage(1);
  };

  const isUnauthenticated = !isAuthenticated || (error && /401|unauthorized|bearer token/i.test(error));

  return (
    <div className="overview-shell mx-auto max-w-6xl px-4 py-8 sm:px-7 sm:py-12 lg:px-10">
      {/* Header */}
      <header className="cw-overview-heading mb-8">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="cw-label font-mono text-[11px] font-bold text-teal-800 bg-teal-50 border border-teal-200/80 px-2.5 py-0.5 rounded-lg shadow-2xs">
              Cryptographic Audit Ledger
            </span>
            {verification && verification.is_valid && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                <span>SHA-256 Chain Verified</span>
              </span>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Activity & Audit Log
          </h1>
          <p className="mt-1.5 text-sm text-slate-500 max-w-2xl">
            Tamper-evident, cryptographically chained record of all policy extractions, coverage analyses, and claim evaluations.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={handleVerifyChain}
            disabled={verifying || !isAuthenticated}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-white hover:text-slate-900 transition-all disabled:opacity-50"
            title="Cryptographically verify sequence numbers and SHA-256 canonical JSON hash chain"
          >
            {verifying ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-teal-600" />
            ) : (
              <Shield className="h-3.5 w-3.5 text-teal-600" />
            )}
            <span>{verifying ? 'Verifying...' : 'Verify Cryptographic Ledger'}</span>
          </button>

          <button
            type="button"
            onClick={() => void loadEvents()}
            disabled={loading || !isAuthenticated}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-white transition-all disabled:opacity-50"
            aria-label="Refresh events"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-teal-600' : 'text-slate-500'}`} />
            <span>Refresh</span>
          </button>
        </div>
      </header>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4 mb-8">
        <GlassCard className="p-4 rounded-2xl border border-slate-200/70 bg-white/70 shadow-xs">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Total Recorded Events</p>
          <p className="mt-1.5 text-2xl font-bold text-slate-900 font-mono">
            {loading ? '—' : totalCount}
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500">Authorized audit trail</p>
        </GlassCard>

        <GlassCard className="p-4 rounded-2xl border border-slate-200/70 bg-white/70 shadow-xs">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Hash Chain Integrity</p>
          <div className="mt-1.5 flex items-center gap-1.5">
            {verification ? (
              verification.is_valid ? (
                <>
                  <ShieldCheck className="h-5 w-5 text-emerald-600" />
                  <span className="text-base font-bold text-emerald-700">Valid</span>
                </>
              ) : (
                <>
                  <ShieldAlert className="h-5 w-5 text-rose-600" />
                  <span className="text-base font-bold text-rose-700">Tampered</span>
                </>
              )
            ) : (
              <span className="text-sm font-medium text-slate-500">Unverified</span>
            )}
          </div>
          <p className="mt-0.5 text-[11px] text-slate-500">
            {verification?.verified_count ? `${verification.verified_count} sequential hashes` : 'SHA-256 monotonic'}
          </p>
        </GlassCard>

        <GlassCard className="p-4 rounded-2xl border border-slate-200/70 bg-white/70 shadow-xs">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Active Filters</p>
          <p className="mt-1.5 text-2xl font-bold text-slate-900 font-mono">
            {isFilterActive ? filteredEvents.length : totalCount}
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500">
            {isFilterActive ? 'Matches applied criteria' : 'All events displayed'}
          </p>
        </GlassCard>

        <GlassCard className="p-4 rounded-2xl border border-slate-200/70 bg-white/70 shadow-xs">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Tenant Scope</p>
          <p className="mt-1.5 text-xs font-semibold text-slate-900 truncate" title={user?.email || 'Guest'}>
            {user?.email || (isAuthenticated ? 'Authenticated User' : 'Sign-in required')}
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500 font-mono">
            {user?.role ? `Role: ${user.role}` : 'Isolated session'}
          </p>
        </GlassCard>
      </div>

      {/* Unauthenticated Alert */}
      {isUnauthenticated && (
        <div className="mb-8 rounded-2xl border border-teal-200 bg-white/85 p-6 text-center shadow-xs">
          <Lock className="mx-auto h-8 w-8 text-teal-700 mb-3" />
          <h2 className="text-base font-bold text-slate-900">Authentication Required</h2>
          <p className="mt-1 text-xs text-slate-600 max-w-md mx-auto">
            Audit trail records enforce strict tenant isolation. Please sign in to securely view and verify your account activity.
          </p>
          <button
            type="button"
            onClick={() => openAuthModal('login')}
            className="mt-4 inline-flex items-center justify-center rounded-xl bg-teal-700 px-5 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-teal-800 transition-colors"
          >
            Sign in to your account
          </button>
        </div>
      )}

      {/* Filter Toolbar */}
      {!isUnauthenticated && (
        <GlassPanel className="p-4 rounded-2xl border border-slate-200/70 bg-white/75 shadow-xs mb-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by resource ID, document name, or keyword..."
                className="w-full rounded-xl border border-slate-200/80 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Filter Dropdowns */}
            <div className="flex flex-wrap items-center gap-2.5">
              {/* Action Filter */}
              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-slate-500 font-medium">Action:</span>
                <select
                  value={actionFilter}
                  onChange={(e) => {
                    setActionFilter(e.target.value);
                    setPage(1);
                  }}
                  className="rounded-lg border border-slate-200 bg-white py-1.5 px-2 text-xs font-medium text-slate-700 focus:border-teal-500 focus:outline-none"
                >
                  <option value="all">All Actions</option>
                  <option value="policy.upload">Policy Uploaded</option>
                  <option value="coverage.analyze">Coverage Evaluated</option>
                  <option value="claim.create">Claim Created</option>
                  <option value="claim.adjudicate">Claim Adjudicated</option>
                  <option value="claim.upload_bill">Medical Bill Analyzed</option>
                  <option value="auth.login">User Signed In</option>
                  <option value="auth.logout">User Signed Out</option>
                  <option value="comparison.create">Policies Compared</option>
                  <option value="qa.ask">Policy Q&A</option>
                </select>
              </div>

              {/* Outcome Filter */}
              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-slate-500 font-medium">Outcome:</span>
                <select
                  value={outcomeFilter}
                  onChange={(e) => {
                    setOutcomeFilter(e.target.value);
                    setPage(1);
                  }}
                  className="rounded-lg border border-slate-200 bg-white py-1.5 px-2 text-xs font-medium text-slate-700 focus:border-teal-500 focus:outline-none"
                >
                  <option value="all">All Outcomes</option>
                  <option value="success">Success / Valid</option>
                  <option value="covered">Covered</option>
                  <option value="denied">Denied / Excluded</option>
                  <option value="failed">Failed / Error</option>
                </select>
              </div>

              {isFilterActive && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-200 transition-colors"
                >
                  Reset filters
                </button>
              )}
            </div>
          </div>
        </GlassPanel>
      )}

      {/* Main Activity Table Panel */}
      {!isUnauthenticated && (
        <GlassPanel className="dashboard-panel dashboard-activity-panel overflow-hidden border border-slate-200/80 bg-white/70 shadow-xs mb-6">
          {loading && !events.length ? (
            <div className="p-6 space-y-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : error ? (
            <div className="p-6 text-center">
              <CircleAlert className="mx-auto h-8 w-8 text-rose-500 mb-2" />
              <p className="text-sm font-semibold text-rose-800">Error loading audit events</p>
              <p className="text-xs text-rose-600 mt-1">{error}</p>
              <button
                type="button"
                onClick={() => void loadEvents()}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-rose-100 px-3 py-1.5 text-xs font-semibold text-rose-800 hover:bg-rose-200"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Retry</span>
              </button>
            </div>
          ) : filteredEvents.length === 0 ? (
            <EmptyState
              icon={Activity}
              title={isFilterActive ? 'No matching audit events' : 'No activity recorded yet'}
              description={
                isFilterActive
                  ? 'No events matched your current search filters. Try resetting the filters.'
                  : 'Your account has no recorded actions yet. Upload a policy or test coverage to begin generating cryptographic records.'
              }
              actionLabel={isFilterActive ? 'Clear filters' : 'Upload a policy'}
              onAction={isFilterActive ? resetFilters : undefined}
              actionHref={isFilterActive ? undefined : '/policies'}
              className="border-0 bg-transparent py-12"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="dashboard-audit-table w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="dashboard-table-head border-b text-[10px] font-semibold text-slate-500 uppercase tracking-[.08em]">
                    <th className="py-3 px-4 w-16 text-center">#Seq</th>
                    <th className="py-3 px-4 w-36">Timestamp</th>
                    <th className="py-3 px-4">Action & Context</th>
                    <th className="py-3 px-4 w-44">Target Resource</th>
                    <th className="py-3 px-4 w-32 text-center">Status</th>
                    <th className="py-3 px-4 w-20 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {filteredEvents.map((ev) => {
                    const { time, date, full } = formatEventTime(ev.timestamp);
                    const outcome = formatOutcome(ev.outcome);
                    const ActionIcon = getActionIcon(ev.action);
                    const isExpanded = expandedIds.has(ev.event_id);

                    const OutcomeIcon =
                      outcome.tone === 'success'
                        ? Check
                        : outcome.tone === 'pending'
                        ? Clock3
                        : outcome.tone === 'issue'
                        ? CircleAlert
                        : CircleDot;

                    // Extract clauses if recorded in metadata
                    const clauses = Array.isArray(ev.metadata?.clauses)
                      ? (ev.metadata.clauses as Array<{ clause_id: string; heading?: string; page_number?: number }>)
                      : [];

                    // Extract validation check summary if present
                    const validationCheck = ev.metadata?.validation_check as Record<string, unknown> | undefined;

                    // Detail summary string
                    const detailSummary =
                      (typeof ev.metadata?.filename === 'string' && ev.metadata.filename) ||
                      (typeof ev.metadata?.claim_reference === 'string' && ev.metadata.claim_reference) ||
                      (typeof ev.metadata?.procedure_name === 'string' && ev.metadata.procedure_name) ||
                      (typeof ev.metadata?.title === 'string' && ev.metadata.title) ||
                      null;

                    return (
                      <React.Fragment key={ev.event_id}>
                        <tr
                          className={`dashboard-activity-row transition-colors cursor-pointer ${
                            isExpanded ? 'bg-slate-50/80 font-medium' : ''
                          }`}
                          onClick={() => toggleExpand(ev.event_id)}
                        >
                          {/* Sequence */}
                          <td className="py-3 px-4 text-center align-middle font-mono text-[11px] text-slate-400">
                            #{ev.sequence_number}
                          </td>

                          {/* Timestamp */}
                          <td className="dashboard-date-cell py-3 px-4 whitespace-nowrap align-middle" title={full}>
                            <span className="font-semibold text-slate-700">{date}</span>
                            <span className="text-slate-300 mx-1.5">•</span>
                            <span>{time}</span>
                          </td>

                          {/* Action */}
                          <td className="py-3 px-4 align-middle">
                            <div className="flex items-center gap-2">
                              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-50 border border-teal-200/60 text-teal-700 shrink-0">
                                <ActionIcon className="h-3.5 w-3.5" />
                              </div>
                              <div className="min-w-0">
                                <span className="font-semibold text-slate-900 block leading-tight">
                                  {formatActionTitle(ev.action)}
                                </span>
                                {detailSummary && (
                                  <span className="text-[11px] text-slate-500 font-normal block truncate max-w-xs sm:max-w-md mt-0.5">
                                    {detailSummary}
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Resource ID & Type */}
                          <td className="py-3 px-4 align-middle">
                            {ev.resource_id ? (
                              <div className="space-y-0.5">
                                <span className="font-mono text-[11px] font-semibold text-slate-800 block truncate max-w-[140px]">
                                  {ev.resource_id}
                                </span>
                                <span className="text-[10px] text-slate-500 uppercase font-mono tracking-wider">
                                  {ev.resource_type}
                                </span>
                              </div>
                            ) : (
                              <span className="text-slate-400 font-mono text-[11px]">—</span>
                            )}
                          </td>

                          {/* Outcome Status */}
                          <td className="dashboard-outcome-cell py-3 px-4 text-center whitespace-nowrap align-middle">
                            <span className={`dashboard-outcome-badge is-${outcome.tone}`}>
                              <OutcomeIcon aria-hidden="true" />
                              <span>{outcome.label}</span>
                            </span>
                          </td>

                          {/* Details Toggle */}
                          <td className="py-3 px-4 text-right align-middle">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleExpand(ev.event_id);
                              }}
                              className="inline-flex items-center justify-center h-6 w-6 rounded-md hover:bg-slate-200/70 text-slate-500 transition-colors"
                              aria-label={isExpanded ? 'Collapse event' : 'Expand event details'}
                            >
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </button>
                          </td>
                        </tr>

                        {/* Expanded Drawer: Evidence, Cryptographic Hash Chain, Clauses */}
                        {isExpanded && (
                          <tr className="bg-slate-50/95 border-b border-slate-200">
                            <td colSpan={6} className="p-4 sm:p-6 space-y-4">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {/* Cryptographic Proof Panel */}
                                <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2.5 shadow-2xs">
                                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                                    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
                                      <Hash className="h-3.5 w-3.5 text-teal-600" />
                                      <span>Cryptographic Linkage</span>
                                    </div>
                                    <span className="text-[10px] font-mono text-slate-500">
                                      Schema v{ev.schema_version}
                                    </span>
                                  </div>

                                  <div className="space-y-1.5 text-[11px]">
                                    <div>
                                      <span className="font-semibold text-slate-500 block">Event Hash (SHA-256):</span>
                                      <span className="font-mono text-teal-900 bg-teal-50 px-1.5 py-0.5 rounded break-all block">
                                        {ev.event_hash}
                                      </span>
                                    </div>

                                    <div>
                                      <span className="font-semibold text-slate-500 block">Previous Hash:</span>
                                      <span className="font-mono text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded break-all block">
                                        {ev.previous_hash || 'GENESIS_BLOCK'}
                                      </span>
                                    </div>

                                    <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
                                      <span>Sequence: #{ev.sequence_number}</span>
                                      <span>Actor User: {ev.user_id}</span>
                                    </div>
                                  </div>
                                </div>

                                {/* Validation & Policy Clauses Panel */}
                                <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2.5 shadow-2xs">
                                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                                    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-800">
                                      <Layers className="h-3.5 w-3.5 text-teal-600" />
                                      <span>Policy Clauses & Validation</span>
                                    </div>
                                    {ev.resource_type === 'policy' && ev.resource_id && (
                                      <Link
                                        href="/policies"
                                        className="inline-flex items-center gap-1 text-[11px] font-medium text-teal-700 hover:text-teal-900"
                                      >
                                        <span>View policy</span>
                                        <ExternalLink className="h-3 w-3" />
                                      </Link>
                                    )}
                                    {ev.resource_type === 'claim' && ev.resource_id && (
                                      <Link
                                        href={`/claims?claim_id=${encodeURIComponent(ev.resource_id)}`}
                                        className="inline-flex items-center gap-1 text-[11px] font-medium text-teal-700 hover:text-teal-900"
                                      >
                                        <span>View claim</span>
                                        <ExternalLink className="h-3 w-3" />
                                      </Link>
                                    )}
                                  </div>

                                  {/* Clauses */}
                                  {clauses.length > 0 ? (
                                    <div className="space-y-1.5">
                                      <span className="text-[11px] font-semibold text-slate-600 block">
                                        Recorded Policy Clauses:
                                      </span>
                                      <div className="flex flex-wrap gap-1.5">
                                        {clauses.map((clause) => (
                                          <span
                                            key={clause.clause_id}
                                            className="inline-flex items-center gap-1 rounded bg-teal-50 px-2 py-0.5 text-[11px] font-mono text-teal-800 border border-teal-200/70"
                                            title={clause.heading}
                                          >
                                            Clause {clause.clause_id}
                                            {clause.page_number ? ` · p.${clause.page_number}` : ''}
                                            {clause.heading ? ` (${clause.heading})` : ''}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  ) : null}

                                  {/* Validation Check Details */}
                                  {validationCheck ? (
                                    <div className="space-y-1.5 pt-1">
                                      <span className="text-[11px] font-semibold text-slate-600 block">
                                        Validation Checks Recorded:
                                      </span>
                                      <div className="rounded-lg bg-slate-50 p-2 text-[11px] space-y-1">
                                        {Object.entries(validationCheck).map(([k, v]) => (
                                          <div key={k} className="flex items-start justify-between gap-2">
                                            <span className="font-medium text-slate-600 capitalize">
                                              {k.replace(/_/g, ' ')}:
                                            </span>
                                            <span className="font-mono text-slate-900 text-right">
                                              {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                            </span>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  ) : (
                                    !clauses.length && (
                                      <p className="text-xs text-slate-500 italic py-2">
                                        No specific policy clauses or custom validation checks attached to this event.
                                      </p>
                                    )
                                  )}
                                </div>
                              </div>

                              {/* Sanitized Metadata JSON */}
                              {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                                <details className="rounded-xl border border-slate-200/80 bg-white p-3 text-xs">
                                  <summary className="font-semibold text-slate-700 cursor-pointer select-none">
                                    View Full Event Metadata Payload
                                  </summary>
                                  <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-900 p-3 text-[11px] font-mono text-slate-200">
                                    {JSON.stringify(ev.metadata, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Table Footer / Pagination */}
          {!isUnauthenticated && totalCount > 0 && (
            <div className="dashboard-table-footer flex flex-wrap items-center justify-between border-t px-4 py-3 text-xs gap-3">
              <div className="text-[11px] text-slate-500">
                Showing{' '}
                <span className="font-semibold text-slate-700">
                  {Math.min(totalCount, (page - 1) * pageSize + 1)}
                </span>{' '}
                to{' '}
                <span className="font-semibold text-slate-700">
                  {Math.min(totalCount, page * pageSize)}
                </span>{' '}
                of <span className="font-semibold text-slate-700">{totalCount}</span> events
              </div>

              {/* Pagination controls */}
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-500 mr-2">
                  Page {page} of {totalPages}
                </span>

                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="inline-flex items-center justify-center h-7 w-7 rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>

                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="inline-flex items-center justify-center h-7 w-7 rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </GlassPanel>
      )}
    </div>
  );
}
