"use client";
import { createContext, useContext, useEffect, useLayoutEffect, useRef } from 'react';
export type WizardAction = { label: string; disabled?: boolean; busy?: boolean; form?: string; autoAdvanceReady?: boolean; onClick?: () => void };
export const WizardActionContext = createContext<((action: WizardAction | null) => void) | null>(null);
/** The reused screen owns its native form/validation; the wizard supplies the footer. */
export function useWizardAction(action: WizardAction) {
  const publish = useContext(WizardActionContext);
  const callback = useRef(action.onClick);
  useLayoutEffect(() => { callback.current = action.onClick; });
  useEffect(() => {
    publish?.({ label: action.label, disabled: action.disabled, busy: action.busy, form: action.form, autoAdvanceReady: action.autoAdvanceReady, onClick: () => callback.current?.() });
    return () => publish?.(null);
  }, [publish, action.label, action.disabled, action.busy, action.form, action.autoAdvanceReady]);
}
