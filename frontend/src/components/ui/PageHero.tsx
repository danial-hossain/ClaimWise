import Link from 'next/link';
import type { ReactNode } from 'react';
import { ArrowLeft, Sparkles } from 'lucide-react';
import HeroSection from './HeroSection';
import HeroIllustration from './HeroIllustration';

type PageHeroProps = {
  currentPage: string;
  title: string;
  description: string;
  rightSlot?: ReactNode;
  stats?: Array<{ label: string; value: string | number }>;
  illustrated?: { eyebrow: string; firstLine: string; secondLine: string; variant: 'document' | 'coverage' | 'claims' | 'chat' | 'compare' };
};

export default function PageHero({ currentPage, title, description, rightSlot, stats, illustrated }: PageHeroProps) {
  if (illustrated) return (
    <HeroSection
      eyebrow={illustrated.eyebrow}
      title={{ firstLine: illustrated.firstLine, secondLine: illustrated.secondLine }}
      description={description}
      variant={illustrated.variant}
      className="workspace-illustrated-hero"
      primaryAction={rightSlot}
      supportingContent={stats?.length ? <div className="page-hero-stats" aria-label={`${currentPage} summary`}>{stats.map(stat => <span className="page-hero-stat" key={stat.label}><span>{stat.label}</span><strong>{stat.value}</strong></span>)}</div> : undefined}
    >
      <HeroIllustration variant={illustrated.variant} />
    </HeroSection>
  );
  return (
    <header className="page-hero">
      <div className="page-hero-pattern" aria-hidden="true">
        <span className="page-hero-node page-hero-node-one" />
        <span className="page-hero-node page-hero-node-two" />
        <span className="page-hero-node page-hero-node-three" />
        <Sparkles className="page-hero-sparkle" />
      </div>
      <div className="page-hero-main">
        <nav className="page-hero-breadcrumb" aria-label="Breadcrumb">
          <Link href="/dashboard"><ArrowLeft className="h-3.5 w-3.5" />Dashboard</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{currentPage}</span>
        </nav>
        <h1>{title}</h1>
        <p className="page-hero-description">{description}</p>
        {stats && stats.length > 0 && (
          <div className="page-hero-stats" aria-label={`${currentPage} summary`}>
            {stats.map((stat) => (
              <span className="page-hero-stat" key={stat.label}>
                <span>{stat.label}</span><strong>{stat.value}</strong>
              </span>
            ))}
          </div>
        )}
      </div>
      {rightSlot && <div className="page-hero-control">{rightSlot}</div>}
      <div className="page-hero-divider" aria-hidden="true" />
    </header>
  );
}
