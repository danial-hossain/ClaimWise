'use client';

import React from 'react';
import { Check, Upload, ListChecks, CheckSquare, FileText, Send } from 'lucide-react';

interface ClaimStepperProps {
  currentStep: number; // 1 to 5
  onStepClick?: (step: number) => void;
  className?: string;
}

export default function ClaimStepper({
  currentStep,
  onStepClick,
  className = '',
}: ClaimStepperProps) {
  const steps = [
    { number: 1, title: '1. Incident', icon: Upload },
    { number: 2, title: '2. Details', icon: ListChecks },
    { number: 3, title: '3. Checklist', icon: CheckSquare },
    { number: 4, title: '4. Draft', icon: FileText },
    { number: 5, title: '5. Review', icon: Send },
  ];

  return (
    <div className={`w-full py-2 ${className}`}>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {steps.map((s) => {
          const isComplete = currentStep > s.number;
          const isCurrent = currentStep === s.number;
          const Icon = s.icon;

          return (
            <button
              key={s.number}
              type="button"
              disabled={!onStepClick || (!isComplete && !isCurrent)}
              onClick={() => onStepClick && onStepClick(s.number)}
              className={`flex flex-col sm:flex-row items-center gap-2 p-2.5 rounded-lg border text-left transition-all ${
                isCurrent
                  ? 'border-teal-500 bg-teal-50/50 text-teal-900 ring-1 ring-teal-500/20 shadow-xs'
                  : isComplete
                  ? 'border-emerald-200 bg-emerald-50/30 text-slate-700 hover:bg-emerald-50/50'
                  : 'border-slate-200 bg-white text-slate-400 opacity-60'
              } ${onStepClick && (isComplete || isCurrent) ? 'cursor-pointer' : 'cursor-default'}`}
            >
              <div
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  isComplete
                    ? 'bg-emerald-600 text-white'
                    : isCurrent
                    ? 'bg-teal-700 text-white'
                    : 'bg-slate-200 text-slate-600'
                }`}
              >
                {isComplete ? <Check className="h-3.5 w-3.5" /> : s.number}
              </div>
              <div className="min-w-0 text-center sm:text-left">
                <p className="text-xs font-semibold truncate leading-tight">{s.title}</p>
                <p className="text-[10px] text-slate-400 hidden sm:block">
                  {isComplete ? 'Completed' : isCurrent ? 'In progress' : 'Upcoming'}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
