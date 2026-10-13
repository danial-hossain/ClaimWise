import React from 'react';
import { Shield, Lock, FileCode, CheckCircle2 } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950 py-10">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white">
              <Shield className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">
                ClaimWise — FinTechathon Edition
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Evidence first. If no proof, no answer.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6 text-xs text-slate-600 dark:text-slate-400">
            <span className="inline-flex items-center gap-1.5">
              <Lock className="h-3.5 w-3.5 text-emerald-600" />
              Row Level Security Enforced
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-teal-600" />
              Deterministic Arithmetic Engine
            </span>
            <span className="inline-flex items-center gap-1.5">
              <FileCode className="h-3.5 w-3.5 text-indigo-600" />
              Zero Hallucination Tolerance
            </span>
          </div>

          <p className="text-xs text-slate-400 dark:text-slate-500">
            © 2026 ClaimWise. All rights reserved. Built for FinTechathon.
          </p>
        </div>
      </div>
    </footer>
  );
}
