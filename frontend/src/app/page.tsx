import React from 'react';
import Link from 'next/link';
import {
  Shield,
  FileText,
  AlertTriangle,
  Clock,
  ArrowRight,
  UploadCloud,
  FileQuestion,
  HelpCircle,
  ExternalLink,
  Bot,
  Info,
} from 'lucide-react';
import BackendHealthWidget from '@/components/BackendHealthWidget';

export default function DashboardPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Hero Banner: Evidence First */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-slate-900 via-slate-800 to-emerald-950 p-8 sm:p-10 text-white shadow-xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 ring-1 ring-inset ring-emerald-500/20 backdrop-blur-sm">
            <Shield className="h-3.5 w-3.5" />
            FinTechathon 2026 Core Foundation
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white leading-tight">
            Evidence first.{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-300">
              If no proof, no answer.
            </span>
          </h1>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl">
            ClaimWise protects policyholders from artificial hallucination. Every coverage
            statement cites the exact clause and page number. Math calculations are solved with a
            deterministic rules engine—never estimated.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link
              href="/workspace"
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 transition-colors"
            >
              <Bot className="h-4 w-4" />
              Open AI Workspace
            </Link>
            <Link
              href="/policies"
              className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-5 py-2.5 text-sm font-semibold text-white hover:bg-white/20 backdrop-blur-sm transition-colors"
            >
              <UploadCloud className="h-4 w-4" />
              Upload Policy Contract
            </Link>
          </div>
        </div>

        {/* Background glow styling */}
        <div className="absolute -top-24 -right-24 h-96 w-96 rounded-full bg-emerald-600/20 blur-3xl pointer-events-none" />
      </section>

      {/* Real-time Backend Connectivity & Telemetry Widget */}
      <section>
        <BackendHealthWidget />
      </section>

      {/* Milestone 1 Notice */}
      <div className="rounded-2xl border border-blue-200 bg-blue-50/70 p-4 text-blue-900 dark:border-blue-900/40 dark:bg-blue-950/20 dark:text-blue-300 flex items-start gap-3">
        <Info className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
        <div className="text-xs space-y-1">
          <p className="font-semibold text-blue-900 dark:text-blue-200">
            Milestone 1 Foundation Active — Zero Fabricated Data Policy
          </p>
          <p className="text-blue-800/80 dark:text-blue-400 leading-relaxed">
            All placeholder sections below display genuine zero-state indicators. We deliberately do
            not fabricate fake user policies, imaginary claims, or mock claim payouts. Document
            parsing, BGE-M3 vector generation, and sandbox claim submission are staged for Milestone 2.
          </p>
        </div>
      </div>

      {/* Metrics Row (Transparent Zero-States) */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Active Policies</span>
            <FileText className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">0</span>
            <span className="text-xs font-medium text-slate-400">contracts loaded</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">Vault empty. Upload policy PDF to begin.</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Active Claims</span>
            <Shield className="h-4 w-4 text-indigo-600" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">0</span>
            <span className="text-xs font-medium text-slate-400">in investigation</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">No open claims or dispute packages.</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Exclusion Warnings</span>
            <AlertTriangle className="h-4 w-4 text-amber-600" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">0</span>
            <span className="text-xs font-medium text-slate-400">gaps detected</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">Exclusions analyzed upon document upload.</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Filing Deadlines</span>
            <Clock className="h-4 w-4 text-teal-600" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900 dark:text-white">0</span>
            <span className="text-xs font-medium text-slate-400">pending deadlines</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">Contract time limits monitored automatically.</p>
        </div>
      </section>

      {/* Main 4 Dashboard Activity Panels (Clearly Labelled Placeholder States) */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Panel 1: Policies Placeholder */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-emerald-600" />
                <h3 className="font-semibold text-slate-900 dark:text-white">Active Policies</h3>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                Placeholder State
              </span>
            </div>

            <div className="my-8 flex flex-col items-center justify-center text-center px-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400 mb-4">
                <UploadCloud className="h-7 w-7" />
              </div>
              <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                No Insurance Policies Uploaded Yet
              </h4>
              <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 max-w-sm leading-relaxed">
                Upload your health, auto, or home policy contract (PDF) to parse deductibles,
                out-of-pocket maximums, and coverage exclusions with verifiable clause citations.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center">
            <span className="text-xs text-slate-400">Supports PDF contracts up to 25MB</span>
            <Link
              href="/policies"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400"
            >
              Go to My Policies <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* Panel 2: Claims Placeholder */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-indigo-600" />
                <h3 className="font-semibold text-slate-900 dark:text-white">
                  Claims & Denial Investigations
                </h3>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                Placeholder State
              </span>
            </div>

            <div className="my-8 flex flex-col items-center justify-center text-center px-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400 mb-4">
                <FileQuestion className="h-7 w-7" />
              </div>
              <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                No Active Claims Being Tracked
              </h4>
              <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 max-w-sm leading-relaxed">
                Prepare a new claim with evidence, or upload a rejection notice from your insurer.
                ClaimWise checks denial codes against contract wording to identify appeal arguments.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center">
            <span className="text-xs text-slate-400">Sandbox submissions only</span>
            <Link
              href="/claims"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
            >
              Go to My Claims <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* Panel 3: Deadlines Placeholder */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-teal-600" />
                <h3 className="font-semibold text-slate-900 dark:text-white">
                  Filing Deadlines & Time Limits
                </h3>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                Placeholder State
              </span>
            </div>

            <div className="my-8 flex flex-col items-center justify-center text-center px-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-50 text-teal-600 dark:bg-teal-950/40 dark:text-teal-400 mb-4">
                <Clock className="h-7 w-7" />
              </div>
              <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                No Pending Deadlines
              </h4>
              <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 max-w-sm leading-relaxed">
                Insurance contracts impose strict 30, 60, or 90-day time limits on appeals and receipts.
                Milestone 2 will automatically extract these clauses and maintain deadline reminders.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center">
            <span className="text-xs text-slate-400">Rules extracted automatically</span>
            <span className="text-xs font-medium text-slate-400">Pending policy upload</span>
          </div>
        </div>

        {/* Panel 4: Exclusions & Warnings Placeholder */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
                <h3 className="font-semibold text-slate-900 dark:text-white">
                  Exclusions & Gap Warnings
                </h3>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                Placeholder State
              </span>
            </div>

            <div className="my-8 flex flex-col items-center justify-center text-center px-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400 mb-4">
                <AlertTriangle className="h-7 w-7" />
              </div>
              <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                Zero High-Risk Exclusions Detected
              </h4>
              <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 max-w-sm leading-relaxed">
                Hidden clauses like out-of-network travel exclusions, pre-existing condition waiting
                periods, and cosmetic restrictions will appear here with page citations.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center">
            <span className="text-xs text-slate-400">Evidence citations required</span>
            <Link
              href="/compare"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-600 hover:text-amber-700 dark:text-amber-400"
            >
              Compare Policies <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Architecture & Engineering Principles Card */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h3 className="text-base font-semibold text-slate-900 dark:text-white">
          ClaimWise Architectural Principles
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          How ClaimWise protects users against financial risk and generative AI hallucinations:
        </p>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/40">
            <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-semibold text-xs">
              <Shield className="h-4 w-4" />
              1. Verifiable Citations
            </div>
            <p className="mt-1.5 text-xs text-slate-600 dark:text-slate-400">
              Every answer links directly to an exact clause and PDF page. Uncited statements are
              filtered out.
            </p>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/40">
            <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-400 font-semibold text-xs">
              <HelpCircle className="h-4 w-4" />
              2. Deterministic Math Engine
            </div>
            <p className="mt-1.5 text-xs text-slate-600 dark:text-slate-400">
              Deductibles, out-of-pocket maximums, and co-insurance splits are calculated using
              Python code, never LLM estimates.
            </p>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/40">
            <div className="flex items-center gap-2 text-teal-700 dark:text-teal-400 font-semibold text-xs">
              <ExternalLink className="h-4 w-4" />
              3. Honest Uncertainty
            </div>
            <p className="mt-1.5 text-xs text-slate-600 dark:text-slate-400">
              When terms are ambiguous or missing, ClaimWise explicitly says so and drafts clarifying
              questions for the insurer.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
