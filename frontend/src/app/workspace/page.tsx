'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useScenario, type ScenarioMessage } from '@/context/ScenarioContext';
import { useWizardAction } from '@/components/features/wizard/WizardAction';
import GuidanceSummary from '@/components/features/wizard/GuidanceSummary';
import { requestEpoch } from '@/lib/evidencePresentation';
import { GlassPanel } from '@/components/ui/Glass';
import GlassModal from '@/components/ui/GlassModal';
import { Skeleton } from '@/components/ui/Motion';
import { useRouter } from 'next/navigation';
import AnalysisContext from '@/components/ui/AnalysisContext';
import { workflowRequest, type AnalysisConversation } from '@/lib/claimWorkflow';
import {
  Bot,
  User,
  Send,
  RefreshCw,
  AlertCircle,
  BookOpen,
  ShieldCheck,
  Sparkles,
  ArrowRight,
  HelpCircle,
  FileText,
  Compass,
} from 'lucide-react';
import { fetchUploadedPolicies, askPolicyQuestion } from '@/lib/api';
import {
  PolicyExtractionResult,
  QAResponse,
} from '@/types/api';
import GroundedAnswer from '@/components/ui/GroundedAnswer';
import PageHero from '@/components/ui/PageHero';

type ChatMessage = ScenarioMessage;

const ALL_POLICIES = '__all__';

function isPlatformQuestion(question: string): boolean {
  return /\b(?:how\s+(?:does|do)\s+(?:claimwise|this|the)\s+(?:site|website|app)?\s*work|what\s+is\s+claimwise|what\s+(?:features|tools|pages|services)\s+(?:does\s+)?claimwise\s+(?:have|offer|include)?|what\s+can\s+claimwise\s+do|what\s+can\s+you\s+do|tell\s+me\s+about\s+claimwise)\b/i.test(question);
}

const PLATFORM_GUIDE_ANSWER = `ClaimWise helps you understand your insurance policies and prepare claims:

- **My Policies:** Upload and review your policy documents.
- **Ask ClaimWise:** Ask questions about saved policies and review the cited policy clauses behind answers.
- **Coverage Analysis:** Check a situation against a selected policy and see matching coverage evidence.
- **Claims:** Get policy based preparation guidance, collect document requirements, save a claim draft, and track preparation progress.
- **Compare Policies:** Compare saved policies and review differences.
- **Dashboard:** Navigate between your workspace pages and see account-level policy and claim summaries.

ClaimWise can help organize and explain your information. It does not promise an insurer's decision or submit a claim unless a supported insurer integration is available.`;

function formatInline(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-slate-900">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="italic text-slate-800">$1</em>')
    .replace(/`([^`]+)`/g, '<code class="bg-slate-100 text-teal-800 px-1 py-0.5 rounded font-mono text-[11px]">$1</code>');
}

function FormattedMessage({ text }: { text: string }) {
  const lines = text.split('\n');
  return (
    <div className="space-y-1.5 text-xs leading-relaxed text-slate-800">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={idx} className="h-1" />;

        // Headings
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={idx} className="font-bold text-slate-900 text-xs pt-1.5 border-b border-slate-200/60 pb-1">
              {trimmed.replace(/^###\s+/, '')}
            </h4>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={idx} className="font-bold text-slate-900 text-sm pt-2 border-b border-slate-200 pb-1">
              {trimmed.replace(/^##\s+/, '')}
            </h3>
          );
        }

        // Bullet points
        if (/^[-*]\s+/.test(trimmed)) {
          const content = trimmed.replace(/^[-*]\s+/, '');
          return (
            <div key={idx} className="flex items-start gap-2 pl-2">
              <span className="text-teal-600 font-bold leading-none mt-1">•</span>
              <span dangerouslySetInnerHTML={{ __html: formatInline(content) }} />
            </div>
          );
        }

        // Numbered list
        const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start gap-2 pl-2">
              <span className="font-bold text-teal-800 shrink-0 bg-teal-50 border border-teal-200/80 rounded px-1.5 py-0.5 text-[10.5px]">
                {numMatch[1]}
              </span>
              <span dangerouslySetInnerHTML={{ __html: formatInline(numMatch[2]) }} />
            </div>
          );
        }

        return (
          <p key={idx} dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }} />
        );
      })}
    </div>
  );
}

export default function AskClaimWisePage() {
  const [chatOpen, setChatOpen] = useState(true);
  const { remember, scenario, isWizard, wizardHref } = useScenario();
  const [initialJourney] = useState(() => isWizard ? scenario : null);
  const { analysisId: currentAnalysisId, policyId: currentPolicyId, claimId: currentClaimId } = scenario;
  const router = useRouter();
  const [contextLoading, setContextLoading] = useState(true);
  const [contextFailed, setContextFailed] = useState(false);
  const responseEpoch = useRef(requestEpoch());
  const [analysisContext, setAnalysisContext] = useState<AnalysisConversation | null>(null);
  const [claimContext, setClaimContext] = useState('');
  const [linkedClaimId, setLinkedClaimId] = useState('');
  const [policies, setPolicies] = useState<PolicyExtractionResult[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string>(ALL_POLICIES);
  const [question, setQuestion] = useState<string>(isWizard ? scenario.questionDraft || '' : '');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(Array.isArray(initialJourney?.guidanceMessages) ? initialJourney.guidanceMessages : []);
  useEffect(() => {
    if (isWizard && !contextLoading && !analysisContext) remember({ guidanceMessages: chatMessages });
  }, [isWizard, contextLoading, analysisContext, chatMessages, remember]);
  useWizardAction({
    label: 'Continue to My claims',
    disabled: contextLoading || contextFailed || !analysisContext,
    busy: isSubmitting,
    onClick: () => {
      remember({ guidanceReviewed: true });
      router.push(wizardHref('draft'), { scroll: false });
    },
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Grouped starter questions covering platform walkthrough, situations, evidence, and benefits
  const starterGroups = [
    {
      title: 'Platform Guide & Website Features',
      icon: Compass,
      questions: [
        'How does ClaimWise work?',
        'What features does ClaimWise have?',
      ],
    },
    {
      title: 'Situational Guidance & First Steps',
      icon: HelpCircle,
      questions: [
        'What should I do first after my luggage is stolen?',
        'What steps must I take if I am in a car accident overseas?',
      ],
    },
    {
      title: 'Evidence & Claim Filing Instructions',
      icon: FileText,
      questions: [
        'What evidence and documentation do I need to submit with a claim?',
        'Which elective procedures require prior authorization before treatment?',
      ],
    },
  ];

  useEffect(() => {
    let active = true;
    let generation = 0;
    async function initPolicies() {
      const ticket = ++generation;
      responseEpoch.current.invalidate();
      setAnalysisContext(null);
      setClaimContext('');
      setChatMessages([]);
      setIsSubmitting(false);
      setContextLoading(true);
      setContextFailed(false);
      const polRes = await fetchUploadedPolicies();
      if (!active || ticket !== generation) return;
      const params = new URLSearchParams(window.location.search);
      if (params.get('scenario')) setQuestion(params.get('scenario')!.slice(0, 1000));
      setLinkedClaimId(params.get('claim_id') || currentClaimId || '');
      if (params.get('claim_id')) {
        try {
          const claim = await workflowRequest<import('@/types/api').ClaimRecord>(`claims/${encodeURIComponent(params.get('claim_id')!)}`);
          if (!active || ticket !== generation) return;
          setClaimContext(`Incident: ${claim.incident_description || 'Not provided'}. Date: ${claim.incident_date}. Location: ${claim.incident_location || 'Not provided'}.`);
          setSelectedPolicyId(claim.policy_id);
        } catch (error) { if (!active || ticket !== generation) return; setContextFailed(true); setErrorMessage(error instanceof Error ? error.message : 'Could not load claim.'); }
      }
      const analysisId = params.get('analysis_id') || currentAnalysisId;
      if (analysisId) {
        try {
          const context = await workflowRequest<AnalysisConversation>(`coverage/analyses/${encodeURIComponent(analysisId)}`);
          if (!active || ticket !== generation) return;
          setAnalysisContext(context);
          setSelectedPolicyId(context.analysis.policy_id);
          setChatMessages(context.messages.map((m, i) => ({ ...m, id: `saved-${i}`, timestamp: '' })));
          setPolicies(polRes.data || []);
        } catch (error) { if (!active || ticket !== generation) return; setContextFailed(true); setErrorMessage(error instanceof Error ? error.message : 'Could not load analysis context.'); }
        setContextLoading(false);
        return;
      }
      if (polRes.data && polRes.data.length > 0) {
        setPolicies(polRes.data);
        const first = polRes.data.find((p) => p.policy_id) || polRes.data[0];
        if (first.policy_id && !params.get('claim_id')) setSelectedPolicyId(params.get('policy_id') || currentPolicyId || ALL_POLICIES);
      } else {
        setPolicies([]);
        setSelectedPolicyId('');
      }
      setContextLoading(false);
    }
    initPolicies();
    window.addEventListener('claimwise_profile_updated', initPolicies);
    window.addEventListener('storage', initPolicies);
    return () => {
      active = false;
      responseEpoch.current.invalidate();
      window.removeEventListener('claimwise_profile_updated', initPolicies);
      window.removeEventListener('storage', initPolicies);
    };
  }, [currentAnalysisId, currentPolicyId, currentClaimId]);

  useEffect(() => {
    if (!chatMessages.length) return;
    const canvas = messagesEndRef.current?.parentElement;
    canvas?.scrollTo({ top: canvas.scrollHeight, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  }, [chatMessages, isSubmitting]);

  const messageCounter = useRef(0);

  const handleSendQuestion = useCallback(
    async (textToSend?: string) => {
      const qText = (textToSend || question).trim();
      if (!qText || isSubmitting || contextLoading || contextFailed) return;

      const isPlatformQuery = isPlatformQuestion(qText);
      if (!selectedPolicyId && policies.length === 0 && !isPlatformQuery) {
        setErrorMessage('Please select or upload a policy to ask policy-specific questions, or ask "How does ClaimWise work?".');
        return;
      }

      setErrorMessage(null);
      setQuestion('');
      if (isWizard) remember({ questionDraft: '' });

      messageCounter.current += 1;
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      // Add user message to stream
      const userMsg: ChatMessage = {
        id: `user-${messageCounter.current}`,
        sender: 'user',
        text: qText,
        timestamp: timeStr,
      };
      setChatMessages((prev) => [...prev, userMsg]);
      setIsSubmitting(true);

      if (isPlatformQuery) {
        messageCounter.current += 1;
        setChatMessages((prev) => [...prev, {
          id: `assistant-${messageCounter.current}`,
          sender: 'assistant',
          text: PLATFORM_GUIDE_ANSWER,
          messageType: 'platform_guide',
          timestamp: timeStr,
        }]);
        setIsSubmitting(false);
        return;
      }

      const recentHistory = chatMessages.slice(-6).map((m) => ({
        role: m.sender,
        content: m.text,
      }));

      const ticket = responseEpoch.current.begin();
      let res: { data?: QAResponse | null; error?: string | null };
      try {
        res = analysisContext
          ? { data: await workflowRequest<QAResponse>(`coverage/analyses/${encodeURIComponent(analysisContext.analysis.id)}/ask`, 'POST', { question: qText }) }
          : await askPolicyQuestion({
        question: qText,
        policy_id: selectedPolicyId === ALL_POLICIES ? undefined : selectedPolicyId || undefined,
        policy_ids: selectedPolicyId === ALL_POLICIES
          ? policies.map((policy) => policy.policy_id).filter((id): id is string => Boolean(id))
          : undefined,
        history: claimContext ? [{ role: 'user', content: claimContext }, ...recentHistory] : recentHistory,
      });
      } catch (error) { res = { error: error instanceof Error ? error.message : 'Could not send question.' }; }

      if (!responseEpoch.current.isCurrent(ticket)) return;
      setIsSubmitting(false);

      if (res.error) {
        setErrorMessage(res.error);
        return;
      }

      if (res.data) {
        messageCounter.current += 1;
        const assistantMsg: ChatMessage = {
          id: `assistant-${messageCounter.current}`,
          sender: 'assistant',
          text: res.data.answer,
          qaResponse: res.data,
          timestamp: timeStr,
        };
        setChatMessages((prev) => [...prev, assistantMsg]);
      }
    },
    [question, isSubmitting, selectedPolicyId, policies, chatMessages, analysisContext, claimContext, contextLoading, contextFailed, isWizard, remember]
  );

  const selectedPolicy = selectedPolicyId === ALL_POLICIES
    ? null
    : policies.find((p) => p.policy_id === selectedPolicyId) || policies[0];
  const queriedClauseCount = selectedPolicy
    ? selectedPolicy.total_clauses
    : policies.reduce((total, policy) => total + policy.total_clauses, 0);

  return (
    <div className="app-page workspace-page mx-auto max-w-7xl px-4 sm:px-7 lg:px-10 py-8 sm:py-10 space-y-7">
      <PageHero
        currentPage="Ask ClaimWise"
        illustrated={{ eyebrow: 'Ask ClaimWise', firstLine: 'Your questions.', secondLine: 'Policy-backed answers.', variant: 'chat' }}
        title="Ask ClaimWise"
        description="Conversational assistant for real situations, next steps, and policy terms grounded strictly in contract clauses with honest abstention."
        rightSlot={
          <div className="flex flex-wrap items-center gap-3">
          {policies.length > 0 ? (
            <div className="flex items-center gap-2">
              <label htmlFor="workspace-policy-select" className="text-xs font-medium text-slate-500">
                Policy Scope:
              </label>
              <select disabled={Boolean(analysisContext) || Boolean(linkedClaimId) || contextLoading}
                id="workspace-policy-select"
                value={selectedPolicyId}
                onChange={(e) => { responseEpoch.current.invalidate(); setChatMessages([]); setIsSubmitting(false); setErrorMessage(null); setSelectedPolicyId(e.target.value); remember({ policyId: e.target.value === ALL_POLICIES ? undefined : e.target.value, analysisId: undefined, claimId: undefined, title: undefined }); }}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 shadow-xs focus:border-teal-500 focus:outline-none"
              >
                <option value={ALL_POLICIES}>All saved policies ({policies.length})</option>
                {policies.map((p) => (
                  <option key={p.policy_id || p.document_hash} value={p.policy_id || ''}>
                    {p.document_name.replace(/\.pdf$/i, '')} ({p.total_clauses} clauses)
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <Link
              href="/policies"
              className="inline-flex items-center gap-1.5 rounded-lg border border-teal-300 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800 hover:bg-teal-100 transition-colors"
            >
              <FileText className="h-3.5 w-3.5" />
              <span>Upload Policy</span>
            </Link>
          )}
          </div>
        }
      />

      {contextLoading && <p role="status" className="text-xs text-slate-600">Loading policy and conversation context…</p>}
      {isWizard && !contextLoading && !analysisContext && <section className="wizard-guidance-section"><h2>Complete your coverage analysis first</h2><p>Your verified findings and clause references will appear here after a successful analysis. You can ask general questions below while you prepare.</p><Link className="mt-3 inline-block text-sm font-semibold text-teal-800 underline" href={wizardHref('analysis')}>Back to Analysis</Link></section>}
      {analysisContext && <AnalysisContext analysis={analysisContext.analysis} />}
      {analysisContext && isWizard && <GuidanceSummary analysis={analysisContext.analysis} />}
      {claimContext && <p className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-xs">{claimContext}</p>}
      {((!analysisContext && !isWizard) || linkedClaimId) && <nav className="workspace-context-actions" aria-label="Scenario and claim actions">
        {!analysisContext && !isWizard && (<Link href={`/coverage?policy_id=${encodeURIComponent(selectedPolicyId === ALL_POLICIES ? '' : selectedPolicyId)}&scenario=${encodeURIComponent(claimContext || question || chatMessages.find(m => m.sender === 'user')?.text || '')}`}>Analyze Scenario</Link>)}
        {linkedClaimId && <Link href={`/claims?claim_id=${encodeURIComponent(linkedClaimId)}`}>Back to claim</Link>}
      </nav>}

      {/* Main Chat Canvas */}
      <div className="workspace-chat-launcher-wrap">
        <button type="button" onClick={() => setChatOpen(true)} aria-haspopup="dialog" className="hero-section-primary workspace-chat-launcher"><Bot className="h-4 w-4" />Open Ask ClaimWise</button>
      </div>
      <GlassModal open={chatOpen} onClose={() => setChatOpen(false)} title="Ask ClaimWise" description="Ask a question and review the supporting policy evidence." className="workspace-chat-modal">
      {policies.length > 0 && <label className="workspace-chat-scope">Policy scope<select disabled={Boolean(analysisContext) || Boolean(linkedClaimId) || contextLoading} value={selectedPolicyId} onChange={event => { responseEpoch.current.invalidate(); setChatMessages([]); setIsSubmitting(false); setErrorMessage(null); setSelectedPolicyId(event.target.value); remember({ policyId: event.target.value === ALL_POLICIES ? undefined : event.target.value, analysisId: undefined, claimId: undefined, title: undefined }); }}><option value={ALL_POLICIES}>All saved policies ({policies.length})</option>{policies.map(policy => <option key={policy.policy_id || policy.document_hash} value={policy.policy_id || ''}>{policy.document_name}</option>)}</select></label>}
      <GlassPanel as="div" className="cw-chat-panel rounded-2xl border border-slate-200 bg-white shadow-xs flex flex-col min-h-[580px] cw-glass">
        {/* Active Policy Context Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 px-5 py-3 text-xs bg-slate-50/70 rounded-t-2xl gap-2">
          <div className="flex items-center gap-2 text-slate-600">
            <BookOpen className="h-4 w-4 text-teal-700 shrink-0" />
            <span>
              Querying:{' '}
              <strong>
                {policies.length > 0
                  ? selectedPolicy?.document_name || `All ${policies.length} saved policies`
                  : 'Platform Guide & Help'}
              </strong>
            </span>
            {policies.length > 0 && (
              <span className="text-slate-400 font-mono text-[11px]">
                ({selectedPolicy ? `${selectedPolicy.total_pages} pages` : `${queriedClauseCount} clauses`}
                {selectedPolicy ? ` • ${selectedPolicy.total_clauses} clauses` : ''})
              </span>
            )}
          </div>
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 shrink-0">
            <ShieldCheck className="h-3 w-3" /> Grounded Citations &middot; No Outside Advice
          </span>
        </div>

        {/* Informational banner when no policies uploaded */}
        {policies.length === 0 && (
          <div className="mx-5 mt-4 flex items-center justify-between gap-3 bg-teal-50/70 border border-teal-200/80 rounded-xl px-4 py-2.5 text-xs text-teal-900">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-teal-700 shrink-0" />
              <span>
                No policy document uploaded yet. You can ask <strong>&quot;How does ClaimWise work?&quot;</strong>, or upload a contract in My Policies.
              </span>
            </div>
            <Link href="/policies" className="shrink-0 font-semibold text-teal-800 hover:text-teal-950 underline text-xs">
              Upload PDF &rarr;
            </Link>
          </div>
        )}

        {/* Chat Messages Stream */}
        <div className="flex-1 p-5 space-y-5 overflow-y-auto max-h-[540px]">
          {chatMessages.length === 0 ? (
            /* Empty State with Categorized Starter Questions */
            <div className="py-6 sm:py-8 text-center space-y-6">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-700">
                <Bot className="h-6 w-6" />
              </div>
              <div className="max-w-md mx-auto space-y-1">
                <h3 className="font-semibold text-sm text-slate-900">
                  How can ClaimWise help you today?
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Ask what to do after a theft or accident, clarify coverage terms, or learn how ClaimWise works.
                </p>
              </div>

              {/* Categorized starter question cards */}
              <div className="ask-claimwise-question-grid max-w-2xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-3 text-left">
                {starterGroups.map((group, gIdx) => {
                  const GroupIcon = group.icon;
                  return (
                    <div
                      key={gIdx}
                      className="ask-claimwise-question-card rounded-xl p-3.5 space-y-2.5 flex flex-col justify-between"
                    >
                      <div className="flex items-center gap-1.5 text-teal-900 font-semibold text-xs border-b border-slate-200/60 pb-1.5">
                        <GroupIcon className="h-3.5 w-3.5 text-teal-700" />
                        <span>{group.title}</span>
                      </div>
                      <div className="space-y-1.5">
                        {group.questions.map((q, qIdx) => (
                          <button
                            key={qIdx}
                            type="button"
                            onClick={() => handleSendQuestion(q)}
                            className="ask-claimwise-question-button w-full text-left rounded-lg border p-2 text-[11.5px] text-slate-700 hover:border-teal-500 hover:bg-teal-50/80 hover:text-teal-950 transition-all shadow-2xs cursor-pointer"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            chatMessages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.sender === 'assistant' && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-700 text-white mt-1 shadow-2xs">
                    <Bot className="h-4 w-4" />
                  </div>
                )}

                <div className={`space-y-2.5 max-w-xl ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
                  {/* User bubble */}
                  {msg.sender === 'user' ? (
                    <div className="rounded-2xl rounded-tr-xs bg-teal-700 px-4 py-2.5 text-xs text-white shadow-xs">
                      {msg.text}
                    </div>
                  ) : (
                    /* Assistant card */
                    <div className="rounded-2xl rounded-tl-xs border border-slate-200 bg-slate-50/60 p-4.5 shadow-xs space-y-3 text-xs">
                      {/* Confidence Label */}
                      <div className="flex items-center justify-between text-[11px] text-slate-500 pb-2 border-b border-slate-200/60">
                        <span className="inline-flex items-center gap-1 font-medium text-emerald-800">
                          <ShieldCheck className="h-3 w-3 text-emerald-600" />
                          {msg.messageType === 'platform_guide'
                            ? 'ClaimWise Guide'
                            : msg.qaResponse?.evidence_sufficient
                            ? 'Verified Citation Grounding'
                            : 'Policy Abstention'}
                        </span>
                        <span className="font-mono text-[10px] text-slate-400">
                          {msg.timestamp}
                        </span>
                      </div>

                      <GroundedAnswer response={msg.qaResponse} policyNames={Object.fromEntries(policies.filter(p => p.policy_id).map(p => [p.policy_id!, p.document_name]))}>
                        <FormattedMessage text={msg.text} />
                      </GroundedAnswer>

                          {/* Contextual Action & Follow-up Recommendations */}
                          {msg.qaResponse && <div className="pt-2.5 border-t border-slate-200/60 flex flex-wrap items-center gap-2">
                            <span className="text-[10.5px] font-semibold text-slate-500">Quick follow-up:</span>
                            <button
                              type="button"
                              onClick={() => handleSendQuestion('What evidence and proof do I need next for this?')}
                              className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-700 hover:border-teal-400 hover:bg-teal-50 transition-colors shadow-2xs cursor-pointer"
                            >
                              Evidence needed next
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSendQuestion('What is the deadline to file this claim?')}
                              className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-700 hover:border-teal-400 hover:bg-teal-50 transition-colors shadow-2xs cursor-pointer"
                            >
                              Reporting deadline
                            </button>
                            {selectedPolicyId && selectedPolicyId !== ALL_POLICIES && (
                              <Link
                                href={`/coverage?policy_id=${selectedPolicyId}`}
                                className="inline-flex items-center gap-1 rounded-md border border-teal-300 bg-teal-50 px-2.5 py-1 text-[11px] font-semibold text-teal-800 hover:bg-teal-100 transition-colors"
                              >
                                <span>Analyze in Coverage</span>
                                <ArrowRight className="h-3 w-3" />
                              </Link>
                            )}
                          </div>}

                    </div>
                  )}
                </div>

                {msg.sender === 'user' && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-200 text-slate-700 mt-1">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))
          )}

          {isSubmitting && (
            <div role="status" className="space-y-2 text-xs text-teal-800 font-medium p-3 bg-teal-50/50 rounded-xl border border-teal-100 max-w-sm">
              <Skeleton className="h-3 w-4/5" /><Skeleton className="h-3 w-3/5" />
              <span>Checking your question against the policy context…</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Error Banner */}
        {errorMessage && (
          <div className="mx-5 mb-2 rounded-xl bg-rose-50 p-3 border border-rose-200 text-xs text-rose-700 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-500" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Chat Input Bar */}
        <div className="p-4 border-t border-slate-200 bg-white rounded-b-2xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendQuestion();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={question}
              aria-label="Your question for ClaimWise"
              onChange={(e) => { setQuestion(e.target.value); if (isWizard) remember({ questionDraft: e.target.value }); }}
              placeholder="Ask a question, what to do in a situation, or 'How does ClaimWise work?'..."
              disabled={isSubmitting || contextLoading || contextFailed}
              className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none disabled:opacity-50"
            />

            <button
              type="submit"
              disabled={isSubmitting || contextLoading || contextFailed || !question.trim()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-teal-700 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-teal-800 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {isSubmitting ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Send className="h-3.5 w-3.5" />
                  <span>Send</span>
                </>
              )}
            </button>
          </form>
        </div>
      </GlassPanel>
      </GlassModal>

      {/* Footer Disclaimer */}
      <footer className="workspace-page-footer border-t border-slate-200 pt-5 text-center text-xs text-slate-400">
        ClaimWise explains policy text and does not replace your insurer or give financial advice.
      </footer>
    </div>
  );
}
