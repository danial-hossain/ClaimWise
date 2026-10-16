'use client';
import { useEffect, useId, useRef, useSyncExternalStore } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'motion/react';
import { motionTokens, useReducedMotion } from './Motion';
import { AlertTriangle, ShieldCheck, X } from 'lucide-react';
const subscribeToMount = () => () => {};

interface ConfirmDialogProps {
  isOpen: boolean; title: string; description: string;
  confirmLabel?: string; cancelLabel?: string;
  variant?: 'primary' | 'destructive' | 'sandbox';
  isProcessing?: boolean; canConfirm?: boolean;
  onConfirm: () => void; onCancel: () => void;
}
export default function ConfirmDialog({ isOpen, title, description, confirmLabel = 'Confirm action', cancelLabel = 'Cancel', variant = 'primary', isProcessing = false, canConfirm = true, onConfirm, onCancel }: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const reduce = useReducedMotion();
  const mounted = useSyncExternalStore(subscribeToMount, () => true, () => false);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) { dialog.showModal(); dialog.querySelector<HTMLButtonElement>('[data-confirm-cancel]')?.focus(); }
    else if (!isOpen && dialog.open) dialog.close();
  }, [isOpen, mounted]);
  if (!mounted) return null;
  return createPortal(<dialog ref={ref} className="cw-confirm-dialog" aria-labelledby={titleId} aria-describedby={descriptionId} onCancel={event => { event.preventDefault(); if (!isProcessing) onCancel(); }}>
    {isOpen && <motion.div key="confirmation" initial={{ opacity: 0, scale: reduce ? 1 : .97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: reduce ? 0 : motionTokens.dialog }} className="cw-confirm-content">
      <div className="flex items-start justify-between gap-4"><div className="flex items-center gap-3">{variant === 'destructive' ? <AlertTriangle className="text-rose-700" /> : <ShieldCheck className="text-teal-700" />}<h2 id={titleId} className="text-lg font-semibold text-slate-900">{title}</h2></div><button type="button" aria-label="Close confirmation" disabled={isProcessing} onClick={onCancel}><X size={18} /></button></div>
      <p id={descriptionId} className="whitespace-pre-line text-sm leading-7 text-slate-600">{description}</p>
      <div className="flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-4"><button data-confirm-cancel type="button" disabled={isProcessing} onClick={onCancel} className="rounded-full border border-slate-300 px-4 py-2 text-sm text-slate-700">{cancelLabel}</button><button type="button" disabled={!canConfirm || isProcessing} onClick={() => { if (canConfirm && !isProcessing) onConfirm(); }} className={`rounded-full px-5 py-2 text-sm font-semibold text-white disabled:opacity-40 ${variant === 'destructive' ? 'bg-rose-700' : 'bg-[#0b2b2a]'}`}>{isProcessing ? 'Submitting…' : confirmLabel}</button></div>
    </motion.div>}
  </dialog>, document.body);
}
