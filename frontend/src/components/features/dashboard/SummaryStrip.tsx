import React from 'react';
import { GlassPanel } from '@/components/ui/Glass';

export interface SummaryMetric {
  id: string;
  label: string;
  value: string | number;
  subtext?: string;
  highlight?: boolean;
}

interface SummaryStripProps {
  metrics: SummaryMetric[];
  className?: string;
}

export default function SummaryStrip({ metrics, className = '' }: SummaryStripProps) {
  if (!metrics || metrics.length === 0) return null;

  return (
    <GlassPanel as="div"
      className={`cw-summary-strip ${className}`}
      role="region"
      aria-label="Portfolio figures"
    >
      {metrics.map((metric) => {
        const isActionNeeded = metric.highlight && typeof metric.value === 'number' && metric.value > 0;

        return (
          <div
            key={metric.id}
            className="cw-summary-figure"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-600">
                {metric.label}
              </span>
            </div>

            <div className="mt-3 flex items-baseline justify-between">
              <span className="dashboard-metric-number text-3xl font-semibold tracking-tight tabular-nums">
                {metric.value}
              </span>
              {isActionNeeded && (
                <span className="dashboard-metric-review inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold">
                  Review needed
                </span>
              )}
            </div>

            {metric.subtext && (
              <p className="mt-1 text-xs text-slate-500 leading-normal">
                {metric.subtext}
              </p>
            )}
          </div>
        );
      })}
    </GlassPanel>
  );
}
