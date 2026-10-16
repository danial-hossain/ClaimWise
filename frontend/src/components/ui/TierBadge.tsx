'use client';

import React, { useState, useRef, useEffect } from 'react';

interface TierBadgeProps {
  tier?: 0 | 1 | 2 | 3 | 4;
  className?: string;
  compact?: boolean;
}

export default function TierBadge({ tier = 1, className = '', compact = true }: TierBadgeProps) {
  const [showInfo, setShowInfo] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowInfo(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const tierLabels: Record<number, { name: string; title: string; desc: string }> = {
    0: {
      name: 'Read only',
      title: 'Tier 0: Read Only',
      desc: 'Browse and inspect loaded policies. No suggestions or drafting active.',
    },
    1: {
      name: 'Suggest mode',
      title: 'Tier 1: Suggest Mode',
      desc: 'AI provides grounded suggestions and explanations with citations. Cannot submit or alter records.',
    },
    2: {
      name: 'Draft mode',
      title: 'Tier 2: Draft Mode',
      desc: 'Generates editable claim statements and appeal letters. Requires explicit review before use.',
    },
    3: {
      name: 'Sandbox submit',
      title: 'Tier 3: Sandbox Submit',
      desc: 'Safe simulation submission with mandatory explicit confirmation. Isolated from real insurer APIs.',
    },
    4: {
      name: 'Blocked',
      title: 'Tier 4: Blocked',
      desc: 'Live insurer EDI transmission and cross-user data access are strictly prohibited.',
    },
  };

  const current = tierLabels[tier] || tierLabels[1];

  return (
    <div ref={containerRef} className={`relative inline-block ${className}`}>
      <button
        type="button"
        onClick={() => setShowInfo(!showInfo)}
        className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors cursor-pointer"
        title="Permission Tier & Security Guarantee"
        aria-label={`Security tier: ${current.name}`}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-teal-600 shrink-0" />
        <span>{compact ? current.name : current.title}</span>
      </button>

      {showInfo && (
        <div className="absolute right-0 mt-1.5 w-64 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700 shadow-md z-50 space-y-1.5">
          <div className="font-semibold text-slate-900 flex items-center justify-between">
            <span>{current.title}</span>
            <span className="text-[10px] text-slate-500 font-mono">Permission Tier</span>
          </div>
          <p className="text-[11px] text-slate-600 leading-relaxed">{current.desc}</p>
          <div className="border-t border-slate-100 pt-1.5 text-[10px] text-slate-400">
            Safety Guarantee: Real insurer APIs and unconfirmed actions are blocked.
          </div>
        </div>
      )}
    </div>
  );
}
