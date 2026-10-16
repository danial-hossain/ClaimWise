import { Bot, ClipboardList, FileText, GitCompare, Paperclip, Send, ShieldCheck } from 'lucide-react';

type HeroIllustrationProps = {
  variant: 'document' | 'coverage' | 'upload' | 'claims' | 'chat' | 'compare';
};

export default function HeroIllustration({ variant }: HeroIllustrationProps) {
  if (variant === 'compare') return (
    <div className="compare-hero-art" aria-hidden="true">
      <div className="compare-hero-glow" />
      {[0, 1].map(index => <div key={index} className={`compare-hero-policy compare-hero-policy-${index}`}><span className="compare-hero-policy-icon"><FileText size={23} /></span><strong>{index ? 'Policy two' : 'Policy one'}</strong><small>Coverage and conditions</small><i /><i /><div className="compare-hero-highlight"><span />Policy evidence</div><i /></div>)}
      <div className="compare-hero-connection"><GitCompare size={24} /></div>
      <div className="compare-hero-caption"><ShieldCheck size={19} /><div><strong>Find the shared coverage</strong><small>Compare the clauses. See the differences.</small></div></div>
    </div>
  );
  if (variant === 'chat') return (
    <div className="chat-hero-art" aria-hidden="true">
      <div className="chat-hero-halo" />
      <div className="chat-hero-window">
        <div className="chat-hero-heading"><span><Bot size={22} /></span><div><strong>Ask ClaimWise</strong><small>Your policy, in conversation</small></div><i /></div>
        <div className="chat-hero-question">A question about your policy…</div>
        <div className="chat-hero-reply"><Bot size={17} /><div><span /><span /><span /></div></div>
        <div className="chat-hero-source"><FileText size={15} /><div><strong>Supporting policy clauses</strong><small>Quotes and page references</small></div></div>
        <div className="chat-hero-input"><span>Ask a follow-up question</span><Send size={15} /></div>
      </div>
      <span className="chat-hero-label"><ShieldCheck size={16} />Answers you can check</span>
    </div>
  );
  if (variant === 'claims') return (
    <div className="claims-hero-art" aria-hidden="true">
      <div className="claims-hero-glow" />
      <div className="claims-hero-backing" />
      <div className="claims-hero-file">
        <div className="claims-hero-file-heading"><span><ClipboardList size={21} /></span><div><small>CLAIM PREPARATION</small><strong>Your claim file</strong></div><span className="claims-hero-draft">Draft</span></div>
        <div className="claims-hero-file-rule" />
        <p className="claims-hero-checklist-title">Keep the details together</p>
        <div className="claims-hero-checklist-row"><FileText size={16} /><span>Incident details</span><i /></div>
        <div className="claims-hero-checklist-row"><Paperclip size={16} /><span>Supporting documents</span><i /></div>
        <div className="claims-hero-checklist-row"><ShieldCheck size={16} /><span>Policy evidence</span><i /></div>
        <div className="claims-hero-file-note">Organize. Review. Prepare.</div>
      </div>
      <div className="claims-hero-evidence"><ShieldCheck size={21} /><div><strong>Grounded in your policy</strong><small>Evidence at every step</small></div></div>
    </div>
  );
  return (
    <div
      aria-hidden="true"
      className={`hero-illustration hero-illustration--${variant}`}
    >
      <div className="hero-illustration-orb" />
      <div className="hero-illustration-sheet" />
      <div className="hero-illustration-document">
        <div className="hero-illustration-accent" />
        <div className="hero-illustration-topline">
          <span />
          <span />
        </div>
        <p>Clarity, clause by clause.</p>
        <div className="hero-illustration-rule hero-illustration-rule--long" />
        <div className="hero-illustration-rule" />
        <div className="hero-illustration-highlight">
          <span />
          <div>
            <i />
            <i />
          </div>
        </div>
        <div className="hero-illustration-rule hero-illustration-rule--medium" />
        <div className="hero-illustration-rule hero-illustration-rule--short" />
      </div>
      {variant === 'coverage' && (
        <div className="hero-illustration-statuses">
          <span className="hero-illustration-chip hero-illustration-chip--covered">
            Covered
          </span>
          <span className="hero-illustration-chip hero-illustration-chip--conditional">
            Conditional
          </span>
          <span className="hero-illustration-chip hero-illustration-chip--unspecified">
            Not specified
          </span>
        </div>
      )}
      {variant !== 'upload' && (
        <span className="hero-illustration-float">Policy clarity</span>
      )}
    </div>
  );
}
