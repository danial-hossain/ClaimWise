'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Code2 } from 'lucide-react';

interface TechnicalDetailsProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export default function TechnicalDetails({
  title = 'Advanced / Technical Details',
  children,
  className = '',
}: TechnicalDetailsProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={`rounded-lg border border-slate-200 bg-slate-50/60 text-xs ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between p-2.5 text-left font-medium text-slate-500 hover:text-slate-800 transition-colors"
      >
        <span className="flex items-center gap-1.5 text-[11px]">
          <Code2 className="h-3.5 w-3.5 text-slate-400" />
          <span>{title}</span>
        </span>
        {isOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {isOpen && (
        <div className="border-t border-slate-200 p-3 bg-white rounded-b-lg font-mono text-[11px] text-slate-600 space-y-2 overflow-x-auto">
          {children}
        </div>
      )}
    </div>
  );
}
