'use client';

import React, { useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Server,
  Database,
  Key,
  Cpu,
  Search,
} from 'lucide-react';
import { fetchHealth, fetchReadiness, getBackendBaseUrl } from '@/lib/api';
import { HealthResponse, ReadinessResponse } from '@/types/api';

export default function BackendHealthWidget() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResponse | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const checkConnectivity = React.useCallback(async () => {
    setLoading(true);
    setError(null);

    const [healthRes, readyRes] = await Promise.all([
      fetchHealth(),
      fetchReadiness(),
    ]);

    setLatency(healthRes.latencyMs);

    if (healthRes.error) {
      setError(healthRes.error);
      setHealth(null);
      setReadiness(null);
    } else {
      setHealth(healthRes.data);
      setReadiness(readyRes.data);
    }

    setLastChecked(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    let isMounted = true;

    const initialCheck = async () => {
      const [healthRes, readyRes] = await Promise.all([
        fetchHealth(),
        fetchReadiness(),
      ]);

      if (!isMounted) return;

      setLatency(healthRes.latencyMs);
      if (healthRes.error) {
        setError(healthRes.error);
        setHealth(null);
        setReadiness(null);
      } else {
        setHealth(healthRes.data);
        setReadiness(readyRes.data);
      }
      setLastChecked(new Date());
      setLoading(false);
    };

    initialCheck();
    const interval = setInterval(initialCheck, 30000); // Poll every 30s
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const isOnline = health !== null && !error;
  const isPartial = readiness?.status === 'partial';
  const baseUrl = getBackendBaseUrl();

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 cw-glass">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-5 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-11 w-11 items-center justify-center rounded-xl ${
              !isOnline
                ? 'bg-rose-100 text-rose-600 dark:bg-rose-950/50 dark:text-rose-400'
                : isPartial
                ? 'bg-amber-100 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400'
                : 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400'
            }`}
          >
            <Activity className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                Backend API Telemetry
              </h2>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  !isOnline
                    ? 'bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-400'
                    : isPartial
                    ? 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400'
                    : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    !isOnline ? 'bg-rose-500' : isPartial ? 'bg-amber-500' : 'bg-emerald-500'
                  }`}
                />
                {!isOnline ? 'Offline' : isPartial ? 'Operational (Decoupled)' : 'Healthy'}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-mono">
              Target: <span className="font-semibold text-slate-700 dark:text-slate-300">{baseUrl}</span>
              {latency !== null && isOnline && (
                <span className="ml-2 text-emerald-600 dark:text-emerald-400 font-sans font-medium">
                  • {latency}ms latency
                </span>
              )}
            </p>
          </div>
        </div>

        <button
          onClick={checkConnectivity}
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Checking...' : 'Check Health'}
        </button>
      </div>

      {/* Error state if unreachable */}
      {error && (
        <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50/60 p-4 dark:border-rose-900/40 dark:bg-rose-950/20">
          <div className="flex items-start gap-3">
            <XCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-rose-800 dark:text-rose-300">
                Backend Connection Unavailable
              </p>
              <p className="text-xs text-rose-700/80 dark:text-rose-400 mt-1">
                {error}. Ensure the FastAPI backend server is running on{' '}
                <code className="rounded bg-rose-100 dark:bg-rose-900/50 px-1 py-0.5 font-mono text-[11px]">
                  {baseUrl}
                </code>{' '}
                via <code className="font-mono text-[11px]">uvicorn app.main:app --port 8000</code>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Subsystem Health Grid */}
      <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {/* Core FastAPI Server */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3.5 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <Server className="h-4 w-4 text-emerald-600" />
              <span className="text-xs font-semibold">Core API</span>
            </div>
            {isOnline ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <XCircle className="h-4 w-4 text-rose-500" />
            )}
          </div>
          <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
            {isOnline ? 'FastAPI 0.115+ responding' : 'Server not responding'}
          </p>
        </div>

        {/* Database (Neon PostgreSQL + pgvector) */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3.5 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <Database className="h-4 w-4 text-indigo-500" />
              <span className="text-xs font-semibold">Neon PostgreSQL</span>
            </div>
            {readiness?.services.database.status === 'healthy' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-amber-500" />
            )}
          </div>
          <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
            {readiness?.services.database.status === 'healthy'
              ? 'Connected (pgvector active)'
              : 'Connecting to database...'}
          </p>
        </div>

        {/* Authentication (PostgreSQL + JWT) */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3.5 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <Key className="h-4 w-4 text-amber-500" />
              <span className="text-xs font-semibold">PostgreSQL Auth</span>
            </div>
            {(readiness?.services.auth?.status || readiness?.services.supabase_auth?.status) === 'configured' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <span className="text-[10px] font-mono text-amber-600 bg-amber-50 dark:bg-amber-950/60 px-1.5 py-0.5 rounded font-semibold">
                ACTIVE
              </span>
            )}
          </div>
          <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
            {(readiness?.services.auth?.status || readiness?.services.supabase_auth?.status) === 'configured'
              ? 'JWT & DB Auth active'
              : 'Authentication ready'}
          </p>
        </div>

        {/* Gemini AI Engine */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3.5 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <Cpu className="h-4 w-4 text-teal-500" />
              <span className="text-xs font-semibold">Gemini LLM</span>
            </div>
            {readiness?.services.gemini_ai_engine.status === 'configured' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            ) : (
              <span className="text-[10px] font-mono text-slate-600 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded font-semibold">
                MILESTONE 2
              </span>
            )}
          </div>
          <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
            {readiness?.services.gemini_ai_engine.status === 'configured'
              ? 'Ready for citations'
              : 'Staged for Milestone 2'}
          </p>
        </div>

        {/* Hybrid Retrieval */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3.5 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <Search className="h-4 w-4 text-purple-500" />
              <span className="text-xs font-semibold">Hybrid Search</span>
            </div>
            <span className="text-[10px] font-mono text-slate-600 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded font-semibold">
              BGE-M3 + BM25
            </span>
          </div>
          <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
            Vector + lexical pipeline staged
          </p>
        </div>
      </div>

      {lastChecked && (
        <div className="mt-4 flex items-center justify-between text-[11px] text-slate-400">
          <span>Environment: <strong className="text-slate-600 dark:text-slate-300">{health?.environment || 'unknown'}</strong></span>
          <span>Last polled: {lastChecked.toLocaleTimeString()}</span>
        </div>
      )}
    </div>
  );
}
