import Link from 'next/link';
import { ArrowDownRight, ArrowRight, BookOpenCheck, FileCheck2, LockKeyhole, ShieldCheck } from 'lucide-react';
import './home-hero.css';

export default function HomeHero({ startHref }: { startHref: string }) {
  return (
    <section className="restored-home-hero" aria-labelledby="home-title">
      <div className="restored-home-copy">
        <div className="restored-home-eyebrow"><span />Insurance, made legible</div>
        <h1 id="home-title">Know what<br />your policy<br /><em>actually</em><br />covers.</h1>
        <p className="restored-home-description">Choose a policy from your saved documents, describe a care scenario, and see whether the policy covers it—with the supporting clause in view.</p>
        <div className="restored-home-actions">
          <Link href={startHref} className="restored-home-primary">Start with your situation <ArrowRight size={17} /></Link>
          <Link href="/policies" className="restored-home-secondary">Add a policy <ArrowDownRight size={16} /></Link>
        </div>
        <p className="restored-home-trust"><FileCheck2 size={18} /><ShieldCheck size={18} />Answers tied to your documents, with page-level citations.</p>
      </div>
      <div className="restored-home-visual">
        <div className="restored-home-art home-art">
          <div className="art-orbit art-orbit-one" /><div className="art-orbit art-orbit-two" />
          <div className="art-line art-line-one" /><div className="art-line art-line-two" />
          <div className="restored-policy-paper" aria-hidden="true">
            <div className="restored-paper-header"><span />Schedule of benefits</div>
            <i /><i /><i /><div className="restored-paper-highlight" /><i />
            <small>POLICY · SECTION 04</small>
          </div>
          <div className="restored-assistant">
            <div className="restored-assistant-header">
              <span className="restored-assistant-icon"><FileCheck2 size={20} /></span>
              <div><strong>ClaimWise</strong><small>Policy assistant</small></div>
              <span className="restored-preview">● &nbsp;Workspace preview</span>
            </div>
            <div className="restored-question">How will you help me understand my policy?</div>
            <p className="restored-assistant-answer">Choose your policy and describe your situation. Your findings will link to supporting clauses, quotes, and pages when the document provides evidence.</p>
            <div className="restored-evidence">
              <strong><BookOpenCheck size={14} />Your policy evidence</strong>
              <p>No policy selected. Clause IDs, page references, and quotes appear after checking your document.</p>
              <small>When the policy is silent: <b>Not specified.</b></small>
            </div>
            <div className="restored-preview-input"><span>Ask about your policy...</span><ArrowRight size={15} /></div>
          </div>
          <div className="restored-source"><LockKeyhole size={20} /><div><strong>Source verified</strong><small>Answer grounded in your plan</small></div></div>
          <div className="restored-art-caption"><small>Understand the details</small><p>Clarity, clause by clause.</p></div>
        </div>
        <div className="restored-art-meta"><span>Policy intelligence</span><span>01 / Evidence first</span></div>
      </div>
    </section>
  );
}
