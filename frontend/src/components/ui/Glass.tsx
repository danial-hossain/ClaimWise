import type { HTMLAttributes } from 'react';

type GlassProps = HTMLAttributes<HTMLElement> & {
  as?: 'div' | 'section' | 'article' | 'aside' | 'header';
};

/** Light glass for summaries. Use GlassPanel for evidence, forms, and dense content. */
export function GlassCard({ as: Tag = 'section', className = '', ...props }: GlassProps) {
  return <Tag {...props} data-glass="card" className={`glass-card ${className}`} />;
}

/** Opaque enough for long-form reading; nested surfaces never add another blur. */
export function GlassPanel({ as: Tag = 'section', className = '', ...props }: GlassProps) {
  return <Tag {...props} data-glass="panel" className={`glass-panel ${className}`} />;
}

/** Sticky page chrome. Menus within the bar use opaque surfaces without extra blur. */
export function GlassBar({ className = '', ...props }: HTMLAttributes<HTMLElement>) {
  return <header {...props} data-glass="bar" className={`glass-bar ${className}`} />;
}
