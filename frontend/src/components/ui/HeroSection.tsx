import type { ReactNode } from 'react';
import { GlassCard } from '@/components/ui/Glass';

type HeroSectionProps = {
  eyebrow: string;
  title: {
    firstLine: string;
    secondLine: string;
  };
  description: string;
  primaryAction?: ReactNode;
  secondaryAction?: ReactNode;
  supportingContent?: ReactNode;
  children?: ReactNode;
  variant: 'document' | 'coverage' | 'upload' | 'claims' | 'chat' | 'compare';
  className?: string;
};

export default function HeroSection({
  eyebrow,
  title,
  description,
  primaryAction,
  secondaryAction,
  supportingContent,
  children,
  variant,
  className = '',
}: HeroSectionProps) {
  return (
    <GlassCard
      className={`hero-section hero-section--${variant} ${className}`}
    >
      <div className="hero-section-copy">
        <p className="hero-section-eyebrow">{eyebrow}</p>
        <h1>
          <span>{title.firstLine}</span>
          <span className="hero-section-title-accent">{title.secondLine}</span>
        </h1>
        <p className="hero-section-description">{description}</p>
        {(primaryAction || secondaryAction) && (
          <div className="hero-section-actions">
            {primaryAction}
            {secondaryAction}
          </div>
        )}
        {supportingContent}
      </div>
      {children && <div className="hero-section-visual">{children}</div>}
    </GlassCard>
  );
}
