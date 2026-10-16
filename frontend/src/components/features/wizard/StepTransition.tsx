"use client";
import { useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { motionTokens, useReducedMotion } from '@/components/ui/Motion';

export default function StepTransition({ index, identity = '', children }: { index: number; identity?: string; children: ReactNode }) {
  const [travel, setTravel] = useState({ index, direction: 1 });
  if (travel.index !== index) setTravel({ index, direction: index > travel.index ? 1 : -1 });
  const direction = travel.direction;
  const reduce = useReducedMotion();
  const distance = reduce ? 0 : 12;
  return <AnimatePresence mode="wait" initial={false} custom={direction}>
    <motion.div key={`${identity}:${index}`} custom={direction} data-step-transition={index} variants={{
      enter: (way: number) => ({ opacity: 0, x: way * distance }),
      visible: { opacity: 1, x: 0 },
      exit: (way: number) => ({ opacity: 0, x: -way * distance }),
    }} initial="enter" animate="visible" exit="exit" transition={{ duration: reduce ? .12 : motionTokens.duration, ease: motionTokens.ease }} onAnimationComplete={phase => {
      if (phase !== 'visible') return;
      const heading = document.querySelector<HTMLElement>(`[data-step-transition="${index}"] [data-wizard-heading]`);
      // Don't steal focus from a dialog or from typing within the current panel.
      if (document.activeElement === document.body || document.activeElement?.closest('.wizard-stepper, .wizard-footer')) {
        heading?.focus({ preventScroll: true });
        const top = (document.querySelector('.cw-header')?.getBoundingClientRect().height || 0) + (document.querySelector('.wizard-stepper')?.getBoundingClientRect().height || 0);
        if (heading && heading.getBoundingClientRect().top < top) heading.closest('header')?.scrollIntoView({ block: 'start', behavior: 'instant' });
      }
    }} className="wizard-transition">{children}</motion.div>
  </AnimatePresence>;
}
