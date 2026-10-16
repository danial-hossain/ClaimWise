'use client';
import { useEffect, useState } from 'react';
import { motion, useReducedMotion, type HTMLMotionProps } from 'motion/react';

export const motionTokens = { duration: .35, short: .15, dialog: .22, stagger: .05, distance: 8, ease: [.22, 1, .36, 1] as const };
export { useReducedMotion };

export function StaggerGroup({ children, ...props }: HTMLMotionProps<'div'>) {
  const reduce = useReducedMotion();
  return <motion.div {...props} initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: reduce ? 0 : motionTokens.stagger } } }}>{children}</motion.div>;
}
export function StaggerItem({ children, ...props }: HTMLMotionProps<'div'>) {
  const reduce = useReducedMotion();
  return <motion.div {...props} variants={{ hidden: { opacity: reduce ? 1 : 0, y: reduce ? 0 : motionTokens.distance }, visible: { opacity: 1, y: 0, transition: { duration: reduce ? 0 : motionTokens.duration, ease: motionTokens.ease } } }}>{children}</motion.div>;
}
export function Skeleton({ className = '' }: { className?: string }) {
  return <span aria-hidden="true" className={`cw-skeleton ${className}`} />;
}
/** Presentation only: the accessible value always stays at the true server count. */
export function CountUp({ value, enabled = false }: { value: number; enabled?: boolean }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(enabled ? 0 : value);
  useEffect(() => {
    if (!enabled || reduce) return;
    let frame = 0;
    let started: number | undefined;
    const tick = (now: number) => {
      started ??= now;
      const progress = Math.min(1, (now - started) / 450);
      setShown(progress === 1 ? value : Math.round(value * (1 - (1 - progress) ** 3)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [enabled, reduce, value]);
  return <span aria-label={value.toLocaleString()}><span aria-hidden="true">{(!enabled || reduce ? value : shown).toLocaleString()}</span></span>;
}
