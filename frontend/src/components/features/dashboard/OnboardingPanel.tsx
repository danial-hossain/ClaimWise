'use client';

import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, RefreshCw, AlertCircle } from 'lucide-react';
import { uploadPolicyFile } from '@/lib/api';
import { PolicyExtractionResult } from '@/types/api';

interface OnboardingPanelProps {
  onPolicyUploaded?: (policy: PolicyExtractionResult) => void;
  className?: string;
}

export default function OnboardingPanel({ onPolicyUploaded, className = '' }: OnboardingPanelProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndSetFile = (file: File) => {
    setUploadError(null);
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setUploadError('Only insurance policy PDF documents (.pdf) are supported.');
      setSelectedFile(null);
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setUploadError('Document exceeds 25MB limit.');
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    setUploadError(null);

    const res = await uploadPolicyFile(selectedFile);
    setIsUploading(false);

    if (res.error) {
      setUploadError(res.error);
    } else if (res.data) {
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (onPolicyUploaded) {
        onPolicyUploaded(res.data);
      }
    }
  };

  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-8 max-w-2xl mx-auto space-y-6 ${className}`}>
      <div className="text-center space-y-1.5">
        <h2 className="text-lg font-semibold text-slate-900 tracking-tight">
          Upload your insurance policy
        </h2>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Add an insurance contract or schedule of benefits to verify coverage terms, check prior authorizations, and catch gaps.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          isDragging
            ? 'border-teal-600 bg-teal-50/20'
            : 'border-slate-200 bg-slate-50/40 hover:bg-slate-50/80 hover:border-slate-300'
        }`}
      >
        <div className="space-y-4">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-600">
            <UploadCloud className="h-5 w-5" />
          </div>

          <div>
            <p className="text-xs font-medium text-slate-800">
              Drag and drop your policy PDF here, or browse files
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              PDF documents up to 25MB
            </p>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                validateAndSetFile(e.target.files[0]);
              }
            }}
            disabled={isUploading}
            className="hidden"
            id="minimal-policy-upload"
          />

          <div className="flex items-center justify-center gap-2 pt-1">
            <label
              htmlFor="minimal-policy-upload"
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
            >
              <FileText className="h-3.5 w-3.5 text-slate-500" />
              <span>{selectedFile ? selectedFile.name : 'Choose PDF file'}</span>
            </label>

            {selectedFile && (
              <button
                type="button"
                onClick={handleUpload}
                disabled={isUploading}
                className="inline-flex items-center gap-1.5 rounded-md bg-teal-700 hover:bg-teal-800 disabled:opacity-50 px-4 py-1.5 text-xs font-medium text-white transition-colors cursor-pointer"
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    <span>Extracting...</span>
                  </>
                ) : (
                  <span>Upload & extract</span>
                )}
              </button>
            )}
          </div>
        </div>

        {uploadError && (
          <div className="mt-4 rounded-md bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700 text-left flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600" />
            <p className="leading-relaxed">{uploadError}</p>
          </div>
        )}
      </div>

      <p className="text-[11px] text-center text-slate-400">
        Evidence first • Extracts clauses with verbatim page citations and tamper-evident hashes
      </p>
    </div>
  );
}
