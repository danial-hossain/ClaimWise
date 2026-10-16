'use client';

import React from 'react';
import Link from 'next/link';
import {
  FileText,
  Layers,
  Bot,
  BookOpenText,
  ArrowUpRight,
} from 'lucide-react';
import { PolicyExtractionResult } from '@/types/api';
import { GlassCard } from './Glass';
import { CountUp } from './Motion';

interface PolicyCardProps {
  policy: PolicyExtractionResult;
  onSelect?: () => void;
  isSelected?: boolean;
  className?: string;
  animateCount?: boolean;
}

export default function PolicyCard({
  policy,
  onSelect,
  isSelected = false,
  className = '',
  animateCount = false,
}: PolicyCardProps) {
  const uploadedDate = policy.uploaded_at
    ? new Date(policy.uploaded_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    : null;
  const fileSize = policy.file_size_bytes >= 1024 * 1024
    ? `${(policy.file_size_bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${(policy.file_size_bytes / 1024).toFixed(0)} KB`;

  return (
    <GlassCard as="article"
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect?.();
        }
      }}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      aria-haspopup={onSelect ? 'dialog' : undefined}
      className={`policy-library-card cw-glass group/card rounded-2xl border bg-white p-5 transition-all duration-200 sm:p-6 ${
        isSelected
          ? 'border-teal-500 ring-2 ring-teal-500/20 shadow-sm'
          : 'border-slate-200 hover:border-slate-300'
      } ${onSelect ? 'cursor-pointer' : ''} ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="policy-card-filemark flex h-11 w-11 shrink-0 items-center justify-center rounded-xl">
            <FileText className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h3 className="policy-card-title text-[15px] font-semibold text-slate-900" title={policy.document_name}>
              {policy.document_name.replace(/\.pdf$/i, '')}
            </h3>
            {uploadedDate && <div className="mt-1 text-xs text-slate-500">Added {uploadedDate}</div>}
          </div>
        </div>
      </div>

      <div className="policy-card-facts mt-5 grid grid-cols-3 gap-2 sm:gap-3">
        <div className="rounded-lg border border-white/70 bg-white/45 px-3 py-2.5"><span className="policy-fact-label">Clauses</span><span className="policy-fact-value"><CountUp value={policy.total_clauses} enabled={animateCount} /></span></div>
        <div className="rounded-lg border border-white/70 bg-white/45 px-3 py-2.5"><span className="policy-fact-label">Pages</span><span className="policy-fact-value">{policy.total_pages.toLocaleString()}</span></div>
        <div className="rounded-lg border border-white/70 bg-white/45 px-3 py-2.5"><span className="policy-fact-label">File size</span><span className="policy-fact-value">{fileSize}</span></div>
      </div>

      <div className="policy-card-actions mt-4 flex items-center justify-between border-t border-slate-100/90 pt-3.5 text-xs">
        <div className="flex items-center gap-3">
          <Link href={`/workspace?policy_id=${encodeURIComponent(policy.policy_id || '')}`} onClick={(e) => e.stopPropagation()} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 font-semibold text-teal-800 transition hover:bg-teal-50 hover:text-teal-950">
            <Bot className="h-3.5 w-3.5" /><span>Ask</span>
          </Link>
          <Link href={`/coverage?policy_id=${encodeURIComponent(policy.policy_id || '')}`} onClick={(e) => e.stopPropagation()} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 font-medium text-slate-600 transition hover:bg-slate-100/80 hover:text-slate-900">
            <Layers className="h-3.5 w-3.5" /><span>Gaps</span>
          </Link>
        </div>
        <span className="inline-flex items-center gap-1.5 font-semibold text-teal-800">
          <BookOpenText className="h-3.5 w-3.5" /> Open policy <ArrowUpRight className="h-3.5 w-3.5" />
        </span>
      </div>
    </GlassCard>
  );
}
