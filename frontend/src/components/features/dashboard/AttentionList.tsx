import React from 'react';
import Link from 'next/link';
import { ArrowRight, CheckCircle2 } from 'lucide-react';
import { GlassPanel } from '@/components/ui/Glass';

export type AttentionStatus = 'covered' | 'conditional' | 'excluded' | 'uncertain';

export interface AttentionItem {
  id: string;
  title: string;
  explanation: string;
  clauseRef?: string;
  quote?: string;
  status: AttentionStatus;
  statusLabel?: string;
  actionLabel?: string;
  actionHref?: string;
  importance?: number;
}

interface AttentionListProps {
  items: AttentionItem[];
  className?: string;
}

const statusDotColors: Record<AttentionStatus, string> = {
  covered: 'bg-emerald-500',
  conditional: 'bg-amber-500',
  excluded: 'bg-rose-500',
  uncertain: 'bg-slate-400',
};

export default function AttentionList({ items, className = '' }: AttentionListProps) {
  if (!items || items.length === 0) {
    return (
      <GlassPanel className={`dashboard-panel dashboard-attention-empty p-6 text-center ${className}`}>
        <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 mb-2">
          <CheckCircle2 className="h-4 w-4" />
        </div>
        <p className="text-xs font-medium text-slate-800">
          No preparation items to show
        </p>
        <p className="text-[11px] text-slate-400 mt-0.5">
          Saved policy and checklist items will appear here when they need review.
        </p>
      </GlassPanel>
    );
  }

  // Prioritize and show up to 4 items
  const displayItems = [...items]
    .sort((a, b) => (a.importance ?? 99) - (b.importance ?? 99))
    .slice(0, 4);

  return (
    <GlassPanel
      className={`dashboard-panel dashboard-attention-panel divide-y overflow-hidden ${className}`}
      role="list"
    >
      {displayItems.map((item) => {
        const dotColor = statusDotColors[item.status] || statusDotColors.uncertain;

        return (
          <div
            key={item.id}
            className="dashboard-attention-row flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 transition-colors"
            role="listitem"
          >
            {/* Status dot + Title + Explanation */}
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <span
                className={`h-2 w-2 rounded-full ${dotColor} shrink-0 mt-1.5`}
                title={item.statusLabel || item.status}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                    <span title={item.title} className="min-w-0 truncate text-[13px] font-semibold text-slate-900 leading-tight">
                    {item.title}
                  </span>
                  {item.statusLabel && (
                    <span className="dashboard-attention-status text-[10px] font-medium">
                      • {item.statusLabel}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                  {item.explanation}
                </p>
                {item.quote && <blockquote className="mt-2 border-l-2 border-teal-200 pl-3 text-xs leading-6 text-slate-600">“{item.quote}”</blockquote>}
              </div>
            </div>

            {/* Citation Pill + Action Link */}
            <div className="flex items-center gap-3 shrink-0 self-end sm:self-center pl-5 sm:pl-0">
              {item.clauseRef ? (
                <span
                  className="dashboard-source font-mono text-[10px] px-2 py-1 rounded-md shrink-0"
                  title={`Source clause: ${item.clauseRef}`}
                >
                  {item.clauseRef}
                </span>
              ) : <span className="text-xs text-slate-600">No clause linked</span>}

              {item.actionHref && (
                <Link
                  href={item.actionHref}
                  className="inline-flex items-center gap-1 text-xs font-medium text-teal-700 hover:text-teal-900 transition-colors whitespace-nowrap"
                >
                  <span>{item.actionLabel || 'Review'}</span>
                  <ArrowRight className="h-3 w-3" />
                </Link>
              )}
            </div>
          </div>
        );
      })}
    </GlassPanel>
  );
}
