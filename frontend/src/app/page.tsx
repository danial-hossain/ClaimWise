'use client';

import Link from 'next/link';
import Brand from '@/components/Brand';
import { useAuth } from '@/context/AuthContext';
import {
  ArrowRight,
  ArrowUpRight,
  LockKeyhole,
} from 'lucide-react';
import HomeHero from '@/components/features/home/HomeHero';

function PaperworkArtwork() {
  return (
    <svg viewBox="0 0 360 210" role="img" aria-label="A stack of insurance documents with important terms buried in the fine print" className="story-art h-full w-full">
      <rect x="42" y="34" width="167" height="142" rx="5" fill="#d5e5ec" transform="rotate(-8 42 34)" />
      <rect x="68" y="31" width="161" height="146" rx="5" fill="#ffffff" stroke="#d1e0e9" transform="rotate(5 68 31)" />
      <rect x="93" y="42" width="164" height="142" rx="5" fill="#ffffff" stroke="#d1e0e9" />
      <circle cx="116" cy="64" r="8" fill="#b9e6e7" /><path d="M132 61h89M132 67h64" stroke="#95b9c2" strokeWidth="3" strokeLinecap="round" />
      <path d="M111 88h128M111 98h119M111 108h127M111 118h99" stroke="#d5e5ec" strokeWidth="4" strokeLinecap="round" />
      <rect x="106" y="129" width="111" height="23" rx="3" fill="#e0f2f3" />
      <path d="M115 137h91M115 144h70" stroke="#4c9fa5" strokeWidth="3" strokeLinecap="round" />
      <circle cx="273" cy="139" r="28" fill="#c5e4e8" fillOpacity=".55" /><circle cx="273" cy="139" r="17" fill="none" stroke="#087e8b" strokeWidth="3" /><path d="m286 152 13 13" stroke="#087e8b" strokeWidth="4" strokeLinecap="round" />
      <path d="M247 48h52M247 58h40" stroke="#5a9ba8" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function QuestionArtwork() {
  return (
    <svg viewBox="0 0 360 210" role="img" aria-label="A person trying to understand confusing insurance terms" className="story-art h-full w-full">
      <rect x="54" y="37" width="250" height="139" rx="11" fill="#ffffff" stroke="#d5e5ec" />
      <path d="M76 62h119M76 73h171M76 84h158" stroke="#d3e5ea" strokeWidth="5" strokeLinecap="round" />
      <rect x="76" y="101" width="203" height="47" rx="7" fill="#e8f4f7" />
      <path d="M89 114h173M89 125h155M89 136h116" stroke="#94b9c0" strokeWidth="4" strokeLinecap="round" />
      <circle cx="278" cy="137" r="38" fill="#e0f2f3" /><path d="M270 131c0-8 5-13 13-13 7 0 12 4 12 11 0 10-13 11-13 21" fill="none" stroke="#087e8b" strokeWidth="4" strokeLinecap="round" /><circle cx="282" cy="160" r="2.5" fill="#087e8b" />
      <path d="M111 166v16m32-16v16m-16-16v16" stroke="#bbd3dd" strokeWidth="3" strokeLinecap="round" />
      <path d="M225 36V25m18 11 7-9m-43 9-7-9" stroke="#32a9ae" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function ClaimArtwork() {
  return (
    <svg viewBox="0 0 360 210" role="img" aria-label="A medical bill and explanation of benefits that are difficult to compare" className="story-art h-full w-full">
      <rect x="61" y="28" width="132" height="157" rx="6" fill="#ffffff" stroke="#d5e5ec" />
      <rect x="176" y="46" width="125" height="135" rx="6" fill="#edf7f8" stroke="#d5e5ec" />
      <path d="M82 52h52M82 64h90M82 79h77M82 102h89M82 114h79M82 126h86M82 149h53" stroke="#c4dce4" strokeWidth="4" strokeLinecap="round" />
      <path d="M194 70h87M194 83h69M194 105h85M194 118h52" stroke="#bfd9df" strokeWidth="4" strokeLinecap="round" />
      <rect x="191" y="134" width="94" height="29" rx="4" fill="#d4eff0" />
      <path d="M201 145h42M201 153h66" stroke="#137e85" strokeWidth="3" strokeLinecap="round" />
      <path d="m156 91 33 6m-34 15 27-2" stroke="#299ba8" strokeWidth="3" strokeDasharray="4 5" />
      <circle cx="155" cy="91" r="4" fill="#299ba8" /><circle cx="155" cy="110" r="4" fill="#299ba8" />
    </svg>
  );
}

function EvidenceArtwork() {
  return (
    <svg viewBox="0 0 440 220" role="img" aria-label="A policy answer linked to a highlighted source clause and page number" className="solution-art h-full w-full">
      <rect x="27" y="27" width="190" height="166" rx="9" fill="#ffffff" stroke="#d5e5ec" />
      <path d="M48 52h99M48 64h138M48 76h121" stroke="#c9dce3" strokeWidth="4" strokeLinecap="round" />
      <rect x="45" y="91" width="148" height="39" rx="4" fill="#dce9d9" />
      <path d="M55 103h126M55 115h104" stroke="#4b99a6" strokeWidth="4" strokeLinecap="round" />
      <path d="M49 146h131M49 158h115" stroke="#c9dce3" strokeWidth="4" strokeLinecap="round" />
      <path d="M216 110h35" stroke="#087e8b" strokeWidth="2" strokeDasharray="4 5" />
      <rect x="250" y="57" width="162" height="107" rx="12" fill="#fbfdff" stroke="#d5e5ec" />
      <circle cx="271" cy="78" r="8" fill="#087e8b" /><path d="m267 78 3 3 5-6" fill="none" stroke="white" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M286 76h90M268 99h123M268 111h109" stroke="#cbd6ca" strokeWidth="4" strokeLinecap="round" />
      <rect x="268" y="126" width="112" height="22" rx="4" fill="#e0f2f3" />
      <path d="M278 137h53" stroke="#087e8b" strokeWidth="3" strokeLinecap="round" />
      <path d="M220 106c12-25 16-25 31-25" fill="none" stroke="#087e8b" strokeWidth="2" />
    </svg>
  );
}

function CoverageArtwork() {
  return (
    <svg viewBox="0 0 440 220" role="img" aria-label="A coverage overview showing benefits, limits, and prior authorization" className="solution-art h-full w-full">
      <rect x="31" y="30" width="378" height="160" rx="10" fill="#ffffff" stroke="#d5e5ec" />
      <path d="M31 65h378" stroke="#d9eaf0" strokeWidth="2" />
      <circle cx="55" cy="48" r="7" fill="#c5e4e8" /><path d="M72 45h86" stroke="#c4dce4" strokeWidth="5" strokeLinecap="round" />
      <rect x="55" y="83" width="98" height="85" rx="7" fill="#edf8fa" />
      <path d="M69 101h68M69 114h49" stroke="#c7e0e7" strokeWidth="4" strokeLinecap="round" />
      <path d="M72 146c9-16 18-21 30-7s21 11 31-10" fill="none" stroke="#0a8791" strokeWidth="3" strokeLinecap="round" />
      <rect x="169" y="83" width="100" height="85" rx="7" fill="#f1f8fa" />
      <path d="M184 103h68M184 116h51" stroke="#cfe4e9" strokeWidth="4" strokeLinecap="round" />
      <circle cx="219" cy="145" r="14" fill="#d4eff0" /><path d="M213 145h12m-6-6v12" stroke="#087e8b" strokeWidth="2.5" strokeLinecap="round" />
      <rect x="285" y="83" width="101" height="85" rx="7" fill="#edf8fa" />
      <path d="M301 103h68M301 116h49" stroke="#bcd9e2" strokeWidth="4" strokeLinecap="round" />
      <path d="m302 145 8 8 17-19" fill="none" stroke="#087e8b" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ClaimsArtwork() {
  return (
    <svg viewBox="0 0 440 220" role="img" aria-label="An organized claim file with a checklist and draft appeal letter" className="solution-art h-full w-full">
      <rect x="47" y="42" width="154" height="146" rx="8" fill="#ffffff" stroke="#d5e5ec" />
      <path d="M68 67h95M68 81h111" stroke="#c8dce2" strokeWidth="4" strokeLinecap="round" />
      <rect x="67" y="99" width="17" height="17" rx="4" fill="#ddf2f2" /><path d="m72 107 4 4 7-8" fill="none" stroke="#087e8b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M95 107h82" stroke="#b8d5dd" strokeWidth="4" strokeLinecap="round" />
      <rect x="67" y="126" width="17" height="17" rx="4" fill="#ddf2f2" /><path d="m72 134 4 4 7-8" fill="none" stroke="#087e8b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M95 134h70" stroke="#b8d5dd" strokeWidth="4" strokeLinecap="round" />
      <rect x="67" y="153" width="17" height="17" rx="4" fill="#e4f3f5" /><path d="M95 161h56" stroke="#c9dfe6" strokeWidth="4" strokeLinecap="round" />
      <path d="M205 114h41" stroke="#4b99a6" strokeWidth="2" strokeDasharray="4 5" />
      <rect x="247" y="31" width="144" height="168" rx="8" fill="#e0f2f3" transform="rotate(4 247 31)" />
      <rect x="257" y="40" width="143" height="160" rx="7" fill="#ffffff" stroke="#d5e5ec" />
      <path d="M276 66h83M276 79h105M276 103h103M276 116h91M276 140h103M276 153h69" stroke="#c9dce3" strokeWidth="4" strokeLinecap="round" />
      <rect x="276" y="166" width="67" height="17" rx="3" fill="#ddf2f2" />
    </svg>
  );
}

export default function HomePage() {
  const { user, isAuthenticated, isLoading } = useAuth();

  return (
    <main className="home-page min-h-screen overflow-hidden bg-[#f7fbff] text-[#10233f]">
      <header className="home-nav mx-auto flex max-w-[1440px] items-center justify-between px-6 py-6 sm:px-10 lg:px-16">
        <Link href="/" className="flex items-center" aria-label="ClaimWise home">
          <Brand />
        </Link>

        <nav className="hidden items-center gap-9 text-[13px] text-[#596b65] md:flex" aria-label="Main navigation">
          <a className="home-nav-link" href="#solutions">What we do</a>
          <a className="home-nav-link" href="#how-it-works">How it works</a>
        </nav>

        <div className="flex items-center gap-3">
          {isLoading ? (
            <span className="px-2 py-1 text-[12px] text-[#718079]">Checking account…</span>
          ) : isAuthenticated && user ? (
            <span className="sr-only">Signed in</span>
          ) : (
            <Link
              href="/login"
              className="px-2 py-1 text-[13px] font-medium text-[#102b4c] transition-colors hover:text-[#087e8b]"
            >
              Sign in
            </Link>
          )}
          <Link
            href={isAuthenticated ? '/dashboard' : '/login'}
            className="home-nav-cta inline-flex items-center gap-2 rounded-full border border-[#d5e5ec] px-4 py-2.5 text-[12px] font-semibold text-[#102b4c] transition-colors hover:border-[#102b4c] hover:bg-white"
          >
            {isAuthenticated ? 'Open overview' : 'Get started'} <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </header>

      <HomeHero startHref={isAuthenticated ? '/dashboard' : '/login'} />

      <section id="insurance-problems" className="home-story-section border-y border-[#dce8ef] bg-[#edf5f8] px-6 py-20 sm:px-10 sm:py-24 lg:px-16">
        <div className="mx-auto max-w-[1280px]">
          <div className="grid gap-5 md:grid-cols-[1fr_.7fr] md:items-end">
            <div className="home-reveal"><div className="home-eyebrow"><span /> The hard part</div><h2 className="home-section-title mt-5 max-w-[690px]">Insurance is there when you need it. Understanding it shouldn’t be another burden.</h2></div>
            <p className="home-reveal max-w-[430px] pb-1 text-sm leading-[1.8] text-[#667989]">Plans are packed with conditions, exclusions, and unfamiliar terms. The details that matter can be hard to find until a bill arrives.</p>
          </div>
          <div className="mt-12 grid gap-5 lg:grid-cols-3">
            <article className="home-story-card glass-card">
              <div className="home-illustration"><span className="glass-chip">Policy details</span><PaperworkArtwork /></div>
              <div className="p-6 sm:p-7"><div className="home-card-index">01 / Dense paperwork</div><h3>Important details hide in long documents.</h3><p>Deductibles, limits, and exclusions are scattered across pages of formal policy language.</p></div>
            </article>
            <article className="home-story-card glass-card">
              <div className="home-illustration home-illustration-sand"><span className="glass-chip">Coverage question</span><QuestionArtwork /></div>
              <div className="p-6 sm:p-7"><div className="home-card-index">02 / Unclear answers</div><h3>“Is this covered?” can be hard to answer.</h3><p>A plan may cover a service only with conditions, networks, or prior approval attached.</p></div>
            </article>
            <article className="home-story-card glass-card">
              <div className="home-illustration home-illustration-rose"><span className="glass-chip">Medical bill</span><ClaimArtwork /></div>
              <div className="p-6 sm:p-7"><div className="home-card-index">03 / Confusing bills</div><h3>A claim decision leaves you with more questions.</h3><p>When a bill and explanation of benefits don’t line up, it takes effort to see what happened.</p></div>
            </article>
          </div>
        </div>
      </section>

      <section id="solutions" className="home-story-section px-6 py-20 sm:px-10 sm:py-24 lg:px-16">
        <div className="mx-auto max-w-[1280px]">
          <div className="home-eyebrow home-reveal"><span /> A clearer way through</div>
          <div className="mt-5 grid gap-5 md:grid-cols-[1fr_.65fr] md:items-end">
            <h2 className="home-section-title home-reveal max-w-[650px]">From policy fine print to useful next steps.</h2>
            <p className="home-reveal pb-1 text-sm leading-[1.8] text-[#667989]">ClaimWise turns your own insurance documents into something you can search, question, and check.</p>
          </div>
          <div className="mt-12 grid gap-5 lg:grid-cols-3">
            <article className="home-solution-card glass-card">
              <div className="home-solution-art"><span className="glass-chip">Page 18 · Section 6.2</span><EvidenceArtwork /></div>
              <div className="px-6 pb-7 sm:px-7"><div className="home-card-index">Find the source</div><h3>Answers with receipts.</h3><p>Ask in everyday language and see the exact clause and page behind each answer.</p></div>
            </article>
            <article className="home-solution-card glass-card">
              <div className="home-solution-art home-illustration-sand"><span className="glass-chip">Benefit overview</span><CoverageArtwork /></div>
              <div className="px-6 pb-7 sm:px-7"><div className="home-card-index">See the conditions</div><h3>Coverage in context.</h3><p>Review benefits, limits, exclusions, and authorization requirements in one place.</p></div>
            </article>
            <article className="home-solution-card glass-card">
              <div className="home-solution-art home-illustration-rose"><span className="glass-chip">Claim file</span><ClaimsArtwork /></div>
              <div className="px-6 pb-7 sm:px-7"><div className="home-card-index">Get organized</div><h3>Claims, made clearer.</h3><p>Review bill details, understand claim outcomes, and prepare an appeal draft to check.</p></div>
            </article>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="home-process px-6 py-20 sm:px-10 sm:py-24 lg:px-16">
        <div className="mx-auto max-w-[1280px]">
          <div className="home-eyebrow home-eyebrow-light home-reveal"><span /> A simple starting point</div>
          <h2 className="home-section-title home-section-title-light home-reveal mt-5 max-w-[680px]">Your policy stays at the center of every answer.</h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3 md:gap-10">
            <div className="home-step"><span>01</span><h3>Save your policy</h3><p>Upload a PDF contract or schedule of benefits to My Policies in your profile.</p></div>
            <div className="home-step"><span>02</span><h3>Choose a policy and describe your scenario</h3><p>Select one of your saved policies, then enter the care, treatment, or service you want to check.</p></div>
            <div className="home-step"><span>03</span><h3>Check its clauses</h3><p>See whether the selected policy covers your scenario, with matching clauses and page citations—or a clear note when it cannot confirm.</p></div>
          </div>
          <Link href="/policies" className="mt-11 inline-flex items-center gap-3 rounded-full bg-[#8ededa] px-5 py-3.5 text-[13px] font-semibold text-[#102b4c] transition-all hover:-translate-y-0.5 hover:bg-[#b8efeb]">Add your first policy <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </section>

      <section id="principles" className="home-proof mx-auto grid max-w-[1440px] gap-8 border-b border-[#dce8ef] px-6 py-12 sm:px-10 md:grid-cols-[1fr_2fr] md:items-center lg:px-16">
        <div className="home-reveal flex items-center gap-3 text-[#14566b]"><span className="flex h-9 w-9 items-center justify-center rounded-full border border-[#d5e5ec]"><LockKeyhole className="h-4 w-4" /></span><span className="text-[11px] font-semibold uppercase tracking-[.13em]">Built around your evidence</span></div>
        <div className="grid gap-6 sm:grid-cols-3 sm:gap-8">
          <div className="home-reveal"><div className="text-[12px] font-semibold text-[#173250]">Your policy, first</div><p className="mt-1.5 text-[11px] leading-relaxed text-[#718294]">Answers come from the documents you provide.</p></div>
          <div className="home-reveal"><div className="text-[12px] font-semibold text-[#173250]">Sources in view</div><p className="mt-1.5 text-[11px] leading-relaxed text-[#718294]">Check the cited clause and page for yourself.</p></div>
          <div className="home-reveal"><div className="text-[12px] font-semibold text-[#173250]">Honest uncertainty</div><p className="mt-1.5 text-[11px] leading-relaxed text-[#718294]">If the policy is silent, ClaimWise says so.</p></div>
        </div>
      </section>

      <section className="home-last-call home-reveal mx-6 my-16 px-7 py-12 text-center sm:mx-10 sm:px-12 sm:py-16 lg:mx-16">
        <div className="home-eyebrow justify-center"><span /> Start with what you have</div>
        <h2 className="home-section-title mx-auto mt-5 max-w-[680px]">A little more clarity can change the whole conversation.</h2>
        <p className="mx-auto mt-4 max-w-[490px] text-sm leading-[1.8] text-[#667989]">Choose a saved policy, describe what you need, and check the answer against its clauses.</p>
        <Link href={isAuthenticated ? '/dashboard' : '/login'} className="mt-7 inline-flex items-center gap-3 rounded-full bg-[#102b4c] px-5 py-3.5 text-[13px] font-semibold text-white transition-all hover:-translate-y-0.5 hover:bg-[#126b7a]">Check a scenario <ArrowRight className="h-4 w-4" /></Link>
      </section>

      <footer className="mx-auto flex max-w-[1440px] flex-col gap-3 px-6 py-6 text-[10px] text-[#829087] sm:flex-row sm:items-center sm:justify-between sm:px-10 lg:px-16">
        <span>© 2026 ClaimWise · Evidence first. If no proof, no answer.</span>
        <Link href="/dashboard" className="inline-flex items-center gap-1.5 text-[#14566b] hover:text-[#102b4c]">Go to your workspace <ArrowUpRight className="h-3 w-3" /></Link>
      </footer>
    </main>
  );
}
