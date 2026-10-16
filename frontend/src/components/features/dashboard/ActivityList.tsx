import React, { useState } from 'react';
import Link from 'next/link';
import { AuditEvent } from '@/types/api';
import { ChevronDown, ChevronUp, Check, Clock3, CircleAlert, CircleDot } from 'lucide-react';

interface ActivityListProps {
  events: AuditEvent[];
  className?: string;
}

function formatActionTitle(action: string): string {
  const map: Record<string, string> = {
    'policy.upload': 'Policy uploaded',
    'claim.create': 'Claim created',
    'claim.adjudicate': 'Claim adjudicated',
    'claim.upload_bill': 'Medical bill analyzed',
    'sandbox.submit': 'Payer simulation submitted',
    'appeal.generate': 'Appeal draft generated',
    'appeal.edit': 'Appeal draft updated',
    'appeal.export_pdf': 'Appeal PDF exported',
    'comparison.create': 'Policies compared',
    'comparison.simulate_cost': 'Cost estimate generated',
    'qa.ask': 'Policy question asked',
  };
  return map[action] || action.replace(/[._]/g, ' ');
}

function formatEventTime(timestamp: string): { time: string; date: string } {
  try {
    const d = new Date(timestamp);
    if (isNaN(d.getTime())) return { time: '—', date: '—' };
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    const date = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    return { time, date };
  } catch {
    return { time: '—', date: '—' };
  }
}

function formatOutcome(outcome?: string): { label: string; tone: 'success' | 'pending' | 'issue' | 'neutral' } {
  const normalized = outcome?.trim().toLowerCase().replace(/[._-]+/g, ' ') || '';
  const label = normalized
    ? normalized.replace(/\b\w/g, (letter) => letter.toUpperCase())
    : 'Recorded';

  if (['success', 'completed', 'healthy'].includes(normalized)) return { label, tone: 'success' };
  if (['pending', 'processing', 'queued', 'in progress'].includes(normalized)) return { label, tone: 'pending' };
  if (['failed', 'error', 'rejected', 'denied'].includes(normalized)) return { label, tone: 'issue' };
  return { label, tone: 'neutral' };
}

export default function ActivityList({ events, className = '' }: ActivityListProps) {
  const [showMore, setShowMore] = useState(false);

  if (!events || events.length === 0) {
    return (
      <div className={`dashboard-panel dashboard-activity-empty p-6 text-center text-xs text-slate-500 ${className}`}>
        No recent activity has been recorded yet.
      </div>
    );
  }

  const displayCount = showMore ? 10 : 5;
  const displayedEvents = events.slice(0, displayCount);

  return (
    <div className={`dashboard-panel dashboard-activity-panel overflow-hidden ${className}`}>
      <div className="overflow-x-auto">
        <table className="dashboard-audit-table w-full text-left border-collapse text-xs">
          <thead>
            <tr className="dashboard-table-head border-b text-[10px] font-semibold text-slate-500 uppercase tracking-[.08em]">
              <th className="py-2.5 px-4 w-28">Date</th>
              <th className="py-2.5 px-4">Activity</th>
              <th className="py-2.5 px-4 w-28 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {displayedEvents.map((ev, idx) => {
              const { time, date } = formatEventTime(ev.timestamp);
              const outcome = formatOutcome(ev.outcome);
              const OutcomeIcon = outcome.tone === 'success'
                ? Check
                : outcome.tone === 'pending'
                ? Clock3
                : outcome.tone === 'issue'
                ? CircleAlert
                : CircleDot;

              const detailText =
                (ev.metadata?.filename as string) ||
                (ev.metadata?.claim_reference as string) ||
                (ev.metadata?.title as string);

              return (
                <tr key={ev.event_id || idx} className="dashboard-activity-row transition-colors">
                  <td className="dashboard-date-cell py-3 px-4 whitespace-nowrap align-middle">
                    <span>{date}</span>
                    <span className="text-slate-300 mx-1.5">•</span>
                    <span>{time}</span>
                  </td>
                  <td className="py-3 px-4 align-middle">
                    <span className="font-medium text-slate-900 block leading-tight">
                      {formatActionTitle(ev.action)}
                    </span>
                    {detailText && (
                      <span className="text-[11px] text-slate-400 font-mono block truncate max-w-lg mt-0.5">
                        {detailText}
                      </span>
                    )}
                  </td>
                  <td className="dashboard-outcome-cell py-3 px-4 text-right whitespace-nowrap align-middle">
                    <span className={`dashboard-outcome-badge is-${outcome.tone}`}>
                      <OutcomeIcon aria-hidden="true" />
                      <span>{outcome.label}</span>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="dashboard-table-footer flex items-center justify-between border-t px-4 py-2.5 text-xs">
        {events.length > 5 ? (
          <button
            type="button"
            onClick={() => setShowMore(!showMore)}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
          >
            {showMore ? (
              <>
                <ChevronUp className="h-3.5 w-3.5" />
                <span>Show latest 5</span>
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                <span>Show {Math.min(10, events.length) - 5} more</span>
              </>
            )}
          </button>
        ) : (
          <span className="text-[11px] text-slate-400">
            Showing {events.length} {events.length === 1 ? 'event' : 'events'}
          </span>
        )}

        <Link
          href="/activity"
          className="inline-flex items-center gap-1 text-[11px] font-medium text-teal-700 hover:text-teal-800 hover:underline transition-colors"
        >
          <span>View complete audit log</span>
          <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </div>
  );
}
