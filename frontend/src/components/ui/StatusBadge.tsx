'use client';

import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle } from 'lucide-react';

export type CoverageStatus = 'covered' | 'conditional' | 'excluded' | 'uncertain' | 'not_specified';

interface StatusBadgeProps {
  status: CoverageStatus | string;
  label?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export default function StatusBadge({
  status,
  label,
  size = 'md',
  className = '',
}: StatusBadgeProps) {
  const normStatus = (status || '').toLowerCase().trim();

  let config = {
    tone: 'not_specified',
    icon: HelpCircle,
    defaultLabel: 'Not specified',
  };

  if (normStatus === 'covered' || normStatus === 'potentially_covered' || normStatus === 'verified') {
    config = {
      tone: 'covered',
      icon: CheckCircle2,
      defaultLabel: normStatus === 'potentially_covered' ? 'Potentially covered' : 'Covered',
    };
  } else if (normStatus === 'conditional' || normStatus === 'conditionally_covered' || normStatus === 'requires_review') {
    config = {
      tone: 'conditional',
      icon: AlertTriangle,
      defaultLabel: 'Conditionally covered',
    };
  } else if (normStatus === 'excluded' || normStatus === 'potentially_excluded' || normStatus === 'conflicting') {
    config = {
      tone: 'excluded',
      icon: XCircle,
      defaultLabel: normStatus === 'potentially_excluded' ? 'Potentially excluded' : 'Excluded',
    };
  } else {
    config = {
      tone: 'not_specified',
      icon: HelpCircle,
      defaultLabel: 'Not specified',
    };
  }

  const Icon = config.icon;
  const displayLabel = label || config.defaultLabel;
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[11px] gap-1' : 'px-2.5 py-1 text-xs gap-1.5';
  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5';

  return (
    <span
      data-status={config.tone}
      className={`cw-status inline-flex items-center font-semibold rounded-full border ${sizeClasses} ${className}`}
    >
      <Icon className={`${iconSize} shrink-0`} aria-hidden="true" />
      <span>{displayLabel}</span>
    </span>
  );
}
