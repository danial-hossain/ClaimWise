'use client';

import React from 'react';
import { LucideIcon, FolderOpen } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  actionHref?: string;
  className?: string;
}

export default function EmptyState({
  icon: Icon = FolderOpen,
  title,
  description,
  actionLabel,
  onAction,
  actionHref,
  className = '',
}: EmptyStateProps) {
  return (
    <div
      className={`rounded-xl border border-dashed border-slate-200 bg-white/60 p-8 text-center space-y-3 ${className}`}
    >
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
        <Icon className="h-6 w-6" />
      </div>
      <div className="max-w-sm mx-auto space-y-1">
        <h3 className="font-semibold text-sm text-slate-900">{title}</h3>
        <p className="text-xs text-slate-500 leading-relaxed">{description}</p>
      </div>

      {(actionLabel && (onAction || actionHref)) && (
        <div className="pt-2">
          {actionHref ? (
            <a
              href={actionHref}
              className="inline-flex items-center justify-center rounded-lg bg-teal-700 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-teal-800 transition-colors"
            >
              {actionLabel}
            </a>
          ) : (
            <button
              type="button"
              onClick={onAction}
              className="inline-flex items-center justify-center rounded-lg bg-teal-700 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-teal-800 transition-colors"
            >
              {actionLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
