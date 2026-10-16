'use client';

import React, { useState } from 'react';
import { BookOpen, Check, ChevronDown, ChevronUp } from 'lucide-react';
import { VerifiedCitation } from '@/types/api';

interface CitationChipProps {
  citation: VerifiedCitation;
  policyName?: string;
  showQuoteModal?: boolean;
  className?: string;
  defaultExpanded?: boolean;
}

export default function CitationChip({ citation, policyName, className = '', defaultExpanded = false }: CitationChipProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className={`inline-block ${className}`}>
      <button
        type="button"
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded(!isExpanded)}
        className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-all shadow-2xs ${
          isExpanded
            ? 'border-teal-500 bg-teal-50/80 text-teal-900 ring-1 ring-teal-500/20'
            : 'border-slate-200 bg-white text-slate-700 hover:border-teal-300 hover:bg-teal-50/30 hover:text-teal-900'
        }`}
        title={policyName ? `Source: ${policyName}. Inspect the verified clause quote.` : 'Inspect verifiable source clause quote'}
      >
        <BookOpen className="h-3 w-3 text-teal-600 shrink-0" />
        <span className="font-mono text-[11px] font-semibold text-slate-900">
          Clause {citation.clause_id}
        </span>
        {policyName && (
          <span className="max-w-36 truncate border-l border-slate-200 pl-1.5 text-[10px] text-slate-500" title={policyName}>
            {policyName.replace(/\.pdf$/i, '')}
          </span>
        )}
        <span className="text-slate-300">&bull;</span>
        <span className="text-slate-500 text-[11px] font-mono">PDF p. {citation.page_number}{citation.printed_page_label ? ` (printed p. ${citation.printed_page_label})` : ''}</span>
        {isExpanded ? (
          <ChevronUp className="h-3 w-3 text-teal-700 ml-0.5" />
        ) : (
          <ChevronDown className="h-3 w-3 text-slate-400 ml-0.5" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-1.5 p-3.5 rounded-xl border border-teal-200/90 bg-white text-xs shadow-sm space-y-2 max-w-lg border-l-3 border-l-teal-600">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-bold text-slate-800">
              {citation.clause_heading || `Contract Clause ${citation.clause_id}`}
            </span>
            <span className="inline-flex items-center gap-1 text-emerald-800 font-semibold text-[10px] bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200/80">
              <Check className="h-3 w-3 text-emerald-600" /> Verbatim Policy Proof
            </span>
          </div>
          <p className="text-slate-700 font-mono text-[11px] bg-slate-50/80 p-2.5 rounded-lg border border-slate-200/80 leading-relaxed italic">
            &ldquo;{citation.exact_quote}&rdquo;
          </p>
        </div>
      )}
    </div>
  );
}
