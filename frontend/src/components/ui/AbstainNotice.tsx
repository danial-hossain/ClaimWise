'use client';

import React from 'react';
import { HelpCircle, MessageSquareQuote } from 'lucide-react';

interface AbstainNoticeProps {
  reason?: string | null;
  evidenceStatus?: 'supported' | 'explicitly_excluded' | 'not_specified' | 'evidence_unavailable';
  suggestedQuestions?: string[];
  className?: string;
}

export default function AbstainNotice({
  reason = 'The policy contract does not contain explicit terms for this question.',
  evidenceStatus = 'not_specified',
  suggestedQuestions,
  className = '',
}: AbstainNoticeProps) {
  const isEvidenceUnavailable = evidenceStatus === 'evidence_unavailable';
  return (
    <aside role="note"
      className={`cw-abstain-notice rounded-xl border border-slate-200 bg-slate-50/80 p-4 text-xs text-slate-700 space-y-3 ${className}`}
    >
      <div className="flex items-start gap-2.5">
        <HelpCircle className="h-4 w-4 text-slate-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-900">
              {isEvidenceUnavailable ? 'Policy evidence unavailable' : 'Not specified in your policy'}
            </span>
            <span className="rounded bg-slate-200/80 px-1.5 py-0.5 text-[10px] font-medium text-slate-700">
              {isEvidenceUnavailable ? 'Evidence unavailable' : 'Not specified'}
            </span>
          </div>
          <p className="text-slate-600 leading-relaxed">
            {reason || 'ClaimWise strictly abstains from guessing when supporting contractual evidence is missing.'}
          </p>
        </div>
      </div>

      {suggestedQuestions && suggestedQuestions.length > 0 && (
        <div className="border-t border-slate-200/80 pt-2.5 pl-6 space-y-1.5">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-700">
            <MessageSquareQuote className="h-3.5 w-3.5 text-teal-600" />
            <span>Questions to ask your insurer</span>
          </div>
          <ul className="list-disc list-inside space-y-1 text-slate-600 pl-1">
            {suggestedQuestions.map((q, idx) => (
              <li key={idx} className="leading-snug">
                {q}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
