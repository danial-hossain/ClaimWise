'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import { coverageRequestGate, evaluateNeeds, type NeedEvaluation } from '@/lib/coverageUpdate';
import {
  AlertTriangle,
  ArrowRight,
  Plus,
  RefreshCw,
  Copy,
  Check,
  Search,
  MessageSquare,
  ShieldCheck,
  Clock,
  Info,
  FolderOpen,
  HeartPulse,
  Car,
  Home,
  Plane,
  Sparkles,
  CheckCircle2,
  X,
} from 'lucide-react';
import {
  fetchUploadedPolicies,
  fetchPolicyCoverageReport,
  analyzeCoverageScenario,
} from '@/lib/api';
import {
  PolicyExtractionResult,
  CoverageGapReportResponse,
  CoverageGapAnalysisResult,
} from '@/types/api';
import { workflowRequest, type AnalysisConversation } from '@/lib/claimWorkflow';
import { useScenario } from '@/context/ScenarioContext';
import { useWizardAction } from '@/components/features/wizard/WizardAction';
import AnalysisProgress, { type AnalysisPhase } from '@/components/features/wizard/AnalysisProgress';
import { useRouter } from 'next/navigation';
import AnalysisContext from '@/components/ui/AnalysisContext';
import GuidanceSummary from '@/components/features/wizard/GuidanceSummary';
import CoverageNeedRow from '@/components/ui/CoverageNeedRow';
import { GlassPanel } from '@/components/ui/Glass';
import HeroSection from '@/components/ui/HeroSection';
import HeroIllustration from '@/components/ui/HeroIllustration';
import { Skeleton, StaggerGroup, StaggerItem } from '@/components/ui/Motion';
import { coverageNeedName } from '@/lib/coverage-presentation';

const MAX_NEED_INPUT_LENGTH = 2000;
const COVERAGE_STATE_PREFIX = 'claimwise_coverage_state_v1';

type SavedCoverageState = {
  selectedPolicyId?: string;
  userScenarios?: CoverageGapAnalysisResult[];
  searchQuery?: string;
  customNeedText?: string;
};

function getCoverageStateKey(): string {
  try {
    const profile = JSON.parse(localStorage.getItem('claimwise_user_profile') || '{}');
    const account = String(profile.id || profile.email || 'guest');
    return `${COVERAGE_STATE_PREFIX}:${account}`;
  } catch {
    return `${COVERAGE_STATE_PREFIX}:guest`;
  }
}

export interface QuickCategoryQuestion {
  category: string;
  label: string;
  situation: string;
  icon: React.ElementType;
  badgeClass: string;
  borderClass: string;
  hoverClass: string;
}

export const FOUR_CATEGORY_QUICK_QUESTIONS: QuickCategoryQuestion[] = [
  {
    category: 'Health & Medical',
    label: 'Health & Medical',
    situation: 'Emergency room visit and diagnostic MRI after sudden acute injury or illness',
    icon: HeartPulse,
    badgeClass: 'bg-white/65 text-slate-700 border-white/80',
    borderClass: 'border-white/80',
    hoverClass: 'hover:border-slate-300 hover:bg-white/80',
  },
  {
    category: 'Auto & Vehicle',
    label: 'Auto & Vehicle',
    situation: 'Vehicle collision repair, roadside towing, and rental car reimbursement after an accident',
    icon: Car,
    badgeClass: 'bg-white/65 text-slate-700 border-white/80',
    borderClass: 'border-white/80',
    hoverClass: 'hover:border-slate-300 hover:bg-white/80',
  },
  {
    category: 'Home & Property',
    label: 'Home & Property',
    situation: 'Interior water damage restoration and repair costs caused by a sudden burst plumbing pipe',
    icon: Home,
    badgeClass: 'bg-white/65 text-slate-700 border-white/80',
    borderClass: 'border-white/80',
    hoverClass: 'hover:border-slate-300 hover:bg-white/80',
  },
  {
    category: 'Travel & Disruption',
    label: 'Travel & Disruption',
    situation: 'Non-refundable trip cancellation, severe flight delay compensation, and lost transit luggage',
    icon: Plane,
    badgeClass: 'bg-white/65 text-slate-700 border-white/80',
    borderClass: 'border-white/80',
    hoverClass: 'hover:border-slate-300 hover:bg-white/80',
  },
];

export interface QuickOption {
  label: string;
  value: string;
}

export function getQuestionQuickOptions(question: string): QuickOption[] {
  const q = question.toLowerCase();

  // 1. Rental Car / Vehicle Accident
  if (q.includes('hired rental car') || q.includes('rental car') || q.includes('private vehicle')) {
    return [
      { label: 'Hired Rental Car (Licensed Agency)', value: 'Hired rental car from a licensed commercial rental agency' },
      { label: 'Private / Owned Vehicle', value: 'Private personally owned motor vehicle' },
    ];
  }
  if (q.includes('nominated driver') || q.includes('comprehensive')) {
    return [
      { label: 'Yes: Nominated Driver with Comprehensive Insurance', value: 'Listed as nominated driver on rental agreement with comprehensive hire insurance' },
      { label: 'No: Not Nominated or No Comprehensive Cover', value: 'Not listed as nominated driver or lacking comprehensive hire insurance' },
    ];
  }
  if (q.includes('unsealed') || q.includes('violation')) {
    return [
      { label: 'Sealed Public Roads (Full Compliance)', value: 'Driven strictly on paved sealed public roads in full compliance with rental terms' },
      { label: 'Unsealed Road or Agreement Breach', value: 'Driven on unsealed road or operated in violation of rental agreement terms' },
    ];
  }
  if (q.includes('third parties') || q.includes('third party') || q.includes('property damage') || q.includes('bodily injury')) {
    return [
      { label: 'No Third-Party Damage or Injury', value: 'No property damage or bodily injury caused to third parties' },
      { label: 'Involved Third-Party Property/Injury', value: 'Caused property damage or bodily injury to third parties' },
    ];
  }
  if (q.includes('towing') || q.includes('mechanical repair')) {
    return [
      { label: 'No Towing or Private Repairs', value: 'No roadside towing or mechanical repair expenses claimed' },
      { label: 'Incurred Roadside Towing & Repairs', value: 'Incurred roadside towing and mechanical repair expenses' },
    ];
  }
  if (q.includes('disrupt') || q.includes('accommodation') || q.includes('replacement transport')) {
    return [
      { label: 'Journey Disrupted (Extra Room & Transport)', value: 'Collision disrupted journey requiring additional accommodation and replacement transport' },
      { label: 'No Disruption Expenses', value: 'No extra accommodation or travel disruption expenses incurred' },
    ];
  }
  if (q.includes('other policies') || q.includes('policies included') || q.includes('cdw')) {
    return [
      { label: 'No Other Insurance Held', value: 'No separate motor vehicle, CDW, or credit card insurance held' },
      { label: 'Additional Policies Held (Auto / CDW / Card)', value: 'Additional policies held under domestic auto insurance, rental agency CDW, or credit card coverage' },
    ];
  }

  // 2. Luggage / Theft / Loss / Damage
  if (q.includes('police') || q.includes('pir') || q.includes('24 hours') || q.includes('written report')) {
    return [
      { label: 'Reported within 24h with Police/PIR Report', value: 'Reported to police or transport carrier within 24 hours with written PIR report' },
      { label: 'Not Reported or No Written Report', value: 'Not reported within 24 hours or lacking written official report' },
    ];
  }
  if (q.includes('unattended') || q.includes('public area') || q.includes('unlocked')) {
    return [
      { label: 'Kept Supervised / Locked in Hotel Safe', value: 'Kept securely attended or locked inside a locked hotel safe' },
      { label: 'Left Unattended in Public / Vehicle', value: 'Left unattended in a public area or unattended motor vehicle' },
    ];
  }
  if (q.includes('receipt') || q.includes('proof of ownership') || q.includes('valuation')) {
    return [
      { label: 'Original Purchase Receipts Available', value: 'Original purchase receipts and proof of ownership are available' },
      { label: 'No Purchase Receipts / Proof Available', value: 'No original purchase receipts or proof of ownership available' },
    ];
  }
  if (q.includes('high-value') || q.includes('laptop') || q.includes('jewelry') || q.includes('cameras') || q.includes('cash')) {
    return [
      { label: 'Includes Laptop / Camera / Valuables', value: 'Claim includes high-value laptop, electronics, or valuables' },
      { label: 'Standard Luggage & Clothes Only', value: 'Only standard clothing and personal luggage items claimed' },
    ];
  }

  // 3. Medical / Hospitalization / Surgery
  if (q.includes('emergency') || q.includes('elective') || q.includes('scheduled')) {
    return [
      { label: 'Emergency Hospital Admission', value: 'Emergency hospital admission for acute life-threatening medical need' },
      { label: 'Scheduled / Elective Procedure', value: 'Scheduled elective non-emergency procedure' },
    ];
  }
  if (q.includes('in-network') || q.includes('network') || q.includes('participating')) {
    return [
      { label: 'In-Network Hospital & Doctor', value: 'Treated strictly at an in-network hospital with participating physicians' },
      { label: 'Out-of-Network Facility or Provider', value: 'Treated at an out-of-network facility or by non-participating providers' },
    ];
  }
  if (q.includes('prior auth') || q.includes('precertification') || q.includes('prior approval')) {
    return [
      { label: 'Prior Authorization Approved in Advance', value: 'Prior authorization obtained and approved in advance of treatment' },
      { label: 'No Prior Authorization Obtained', value: 'No prior authorization or precertification obtained before care' },
    ];
  }
  if (q.includes('pre-existing') || q.includes('prior to your policy') || q.includes('prior date')) {
    return [
      { label: 'New Acute Condition (No Prior History)', value: 'New acute medical illness with no prior diagnosis or symptoms' },
      { label: 'Related to Pre-Existing Condition', value: 'Related to an existing medical condition diagnosed or treated previously' },
    ];
  }

  // 4. Trip Delay / Cancellation
  if (q.includes('cause of the delay') || q.includes('cause of cancellation') || q.includes('severe weather') || q.includes('strike')) {
    return [
      { label: 'Carrier Breakdown / Severe Weather / Sickness', value: 'Cancelled due to verified carrier mechanical failure, severe weather, or unforeseen sickness' },
      { label: 'Voluntary / Personal Schedule Change', value: 'Cancelled due to personal decision, work conflict, or voluntary change of mind' },
    ];
  }
  if (q.includes('written confirmation') || q.includes('delay duration') || q.includes('carrier provide')) {
    return [
      { label: 'Written Delay Certificate Provided by Airline', value: 'Written certificate from transport carrier confirming delay and reason' },
      { label: 'No Written Carrier Confirmation', value: 'No written delay or cancellation verification provided by carrier' },
    ];
  }

  // 5. Dental
  if (q.includes('sound natural teeth') || q.includes('accidental physical injury') || q.includes('relief of pain')) {
    return [
      { label: 'Accidental Injury to Sound Natural Teeth', value: 'Emergency treatment for sudden accidental injury to sound natural teeth' },
      { label: 'Routine Cleaning, Crown, or Cosmetic Care', value: 'Routine dental checkup, cosmetic work, or preventative treatment' },
    ];
  }

  // 6. Pharmacy / Medication
  if (q.includes('formulary') || q.includes('tier') || q.includes('preferred retail')) {
    return [
      { label: 'Tier 1 / Generic Formulary Medication', value: 'Tier 1 generic medication listed on plan prescription formulary' },
      { label: 'Non-Formulary / Specialty Brand Drug', value: 'Non-formulary brand or specialty medication' },
    ];
  }

  return [
    { label: 'Yes / Confirmed', value: 'Yes, this condition applies' },
    { label: 'No / Does Not Apply', value: 'No, this condition does not apply' },
  ];
}

function parseNeedInput(input: string): { needs: string[]; context: string; error?: string } {
  const text = input.trim();
  if (!text) return { needs: [], context: '', error: 'Enter a scenario to evaluate.' };
  if (text.length > MAX_NEED_INPUT_LENGTH) {
    return { needs: [], context: '', error: `Keep the description under ${MAX_NEED_INPUT_LENGTH.toLocaleString()} characters.` };
  }

  // A scenario is one incident, including paragraphs and structured facts.
  // Do not replace it with preset questions or split its supporting context.
  return { needs: [text], context: '' };
}

export default function CoverageAnalysisPage() {
  const requests = useRef(coverageRequestGate());
  const [lastSuccessfulSubmission, setLastSuccessfulSubmission] = useState<{ id: string; input: string } | null>(null);
  const { remember, scenario: journey, isWizard, wizardHref } = useScenario();
  const [initialJourney] = useState(() => isWizard ? journey : null);
  const router = useRouter();
  const mounted = useRef(false);
  useEffect(() => { const gate = requests.current; mounted.current = true; return () => { mounted.current = false; gate.invalidate(); }; }, []);
  const [focusedAnalysisId, setFocusedAnalysisId] = useState('');
  const [policies, setPolicies] = useState<PolicyExtractionResult[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string>('');
  const [report, setReport] = useState<CoverageGapReportResponse | null>(null);
  const [userScenarios, setUserScenarios] = useState<CoverageGapAnalysisResult[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [customNeedText, setCustomNeedText] = useState(isWizard ? journey.incidentDraft || '' : '');
  const [needInputMessage, setNeedInputMessage] = useState<string | null>(null);
  const [isLoadingPolicies, setIsLoadingPolicies] = useState(true);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [analysisPhase, setAnalysisPhase] = useState<AnalysisPhase>('idle');
  const [evaluatingSituation, setEvaluatingSituation] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedQuestionIdx, setCopiedQuestionIdx] = useState<number | null>(null);
  const [activeClarifyId, setActiveClarifyId] = useState<string | null>(null);
  const [showInsurerQuestionsModal, setShowInsurerQuestionsModal] = useState(false);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [isClarifying, setIsClarifying] = useState(false);
  const [hasRestoredState, setHasRestoredState] = useState(false);

  // Restore this account's prior workspace before loading its saved policy report.
  useEffect(() => {
    let isMounted = true;
    async function loadInitialData() {
      try {
        let savedState: SavedCoverageState = {};
        try {
          savedState = JSON.parse(localStorage.getItem(getCoverageStateKey()) || '{}') as SavedCoverageState;
        } catch {
          savedState = {};
        }

        const scenario = new URLSearchParams(window.location.search).get('scenario');
        if (scenario) setCustomNeedText(scenario.slice(0, MAX_NEED_INPUT_LENGTH));
        const policiesRes = await fetchUploadedPolicies();
        if (!isMounted) return;
        const linkedId = new URLSearchParams(window.location.search).get('analysis_id') || initialJourney?.analysisId;
        const linked = linkedId ? await workflowRequest<AnalysisConversation>(`coverage/analyses/${encodeURIComponent(linkedId)}`) : null;
        if (!isMounted) return;
        if (linked) { savedState = { ...savedState, selectedPolicyId: linked.analysis.policy_id }; setFocusedAnalysisId(linked.analysis.id); setUserScenarios([linked.analysis]); }

        if (!isMounted) return;

        if (policiesRes.data && policiesRes.data.length > 0) {
          setPolicies(policiesRes.data);
          let initialId = '';
          if (typeof window !== 'undefined') {
            const params = new URLSearchParams(window.location.search);
            const qPolicyId = params.get('policy_id') || initialJourney?.policyId;
            const containsPolicy = (id?: string | null) => Boolean(id && policiesRes.data?.some((p) => p.policy_id === id));
            if (qPolicyId && containsPolicy(qPolicyId)) initialId = qPolicyId;
            else if (savedState.selectedPolicyId && containsPolicy(savedState.selectedPolicyId)) initialId = savedState.selectedPolicyId;
            else initialId = policiesRes.data[0]?.policy_id || '';
          }
          setSelectedPolicyId(initialId);

          if (savedState.selectedPolicyId === initialId) {
            if (!isWizard && Array.isArray(savedState.userScenarios)) setUserScenarios(savedState.userScenarios);
            if (typeof savedState.searchQuery === 'string') setSearchQuery(savedState.searchQuery);
            if (!isWizard && !scenario && typeof savedState.customNeedText === 'string') setCustomNeedText(savedState.customNeedText);
          }

          const savedAnalyses = await workflowRequest<CoverageGapAnalysisResult[]>(`coverage/analyses?policy_id=${encodeURIComponent(initialId)}`);
          const relevantAnalyses = isWizard ? savedAnalyses.filter(item => item.id === linkedId) : savedAnalyses;
          if (isMounted) setUserScenarios(linked && !relevantAnalyses.some(sc => sc.id === linked.analysis.id) ? [linked.analysis, ...relevantAnalyses] : relevantAnalyses);

          // Reports can contain large policy citations and exceed browser storage quotas.
          // Keep the user's work locally, and refresh the policy report from the API.
          if (initialId) {
            setIsLoadingReport(true);
            const repRes = await fetchPolicyCoverageReport(initialId);
            if (isMounted) {
              setIsLoadingReport(false);
              if (repRes.data) {
                setReport(repRes.data);
              } else if (repRes.error) {
                setErrorMessage(repRes.error);
              }
            }
          }
        } else if (policiesRes.error) {
          setErrorMessage(policiesRes.error);
        } else {
          setPolicies([]);
          setSelectedPolicyId('');
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : 'Failed to initialize coverage page.';
        setErrorMessage(msg);
      } finally {
        if (isMounted) {
          setIsLoadingPolicies(false);
          setHasRestoredState(true);
        }
      }
    }
    loadInitialData();
    return () => {
      isMounted = false;
    };
  }, [isWizard, initialJourney]);

  // Keep the current analysis available when navigating to another page and back.
  useEffect(() => {
    if (!hasRestoredState) return;
    try {
      const state: SavedCoverageState = {
        selectedPolicyId,
        userScenarios,
        searchQuery,
        customNeedText,
      };
      localStorage.setItem(getCoverageStateKey(), JSON.stringify(state));
    } catch (err) {
      // Preserve the selected policy and typed input even if citations fill the quota.
      try {
        localStorage.setItem(getCoverageStateKey(), JSON.stringify({
          selectedPolicyId,
          searchQuery,
          customNeedText,
        } satisfies SavedCoverageState));
      } catch {
        console.warn('Could not save coverage workspace state:', err);
      }
    }
  }, [hasRestoredState, selectedPolicyId, report, userScenarios, searchQuery, customNeedText]);

  // Fetch report on policy selection change
  const handlePolicyChange = useCallback(async (newPolicyId: string) => {

    const scopeTicket = requests.current.invalidate();
    setIsEvaluating(false);
    setAnalysisPhase('idle');
    setFocusedAnalysisId('');
    setLastSuccessfulSubmission(null);
    remember({ policyId: newPolicyId });
    setSelectedPolicyId(newPolicyId);
    setUserScenarios([]);
    setReport(null);
    setIsLoadingReport(Boolean(newPolicyId));
    setErrorMessage(null);
    try {
      const saved = await workflowRequest<CoverageGapAnalysisResult[]>(`coverage/analyses?policy_id=${encodeURIComponent(newPolicyId)}`);
      if (!mounted.current || !requests.current.isCurrent(scopeTicket)) return;
      setUserScenarios(isWizard ? saved.filter(item => newPolicyId === journey.policyId && item.id === journey.analysisId) : saved);
    } catch (error) { if (!mounted.current || !requests.current.isCurrent(scopeTicket)) return; setErrorMessage(error instanceof Error ? error.message : 'Could not load saved analyses.'); }
    setActiveClarifyId(null);
    setClarificationAnswers({});
    setReport(null);
    if (!isWizard) setCustomNeedText('');
    setNeedInputMessage(null);
    if (!newPolicyId) {
      setReport(null);
      return;
    }
    setIsLoadingReport(true);
    setErrorMessage(null);
    const repRes = await fetchPolicyCoverageReport(newPolicyId);
    if (!mounted.current || !requests.current.isCurrent(scopeTicket)) return;
    setIsLoadingReport(false);
    if (repRes.data) {
      setReport(repRes.data);
    } else if (repRes.error) {
      setErrorMessage(repRes.error);
      setReport(null);
    }
  }, [remember, isWizard, journey.policyId, journey.analysisId]);

  const activePolicy = policies.find((p) => p.policy_id === selectedPolicyId) || null;
  useEffect(() => {
    if (isWizard && activePolicy) remember({ policyId: activePolicy.policy_id || undefined, policyReady: Boolean(activePolicy.status === 'success' && activePolicy.has_extractable_text && activePolicy.clauses.length) });
  }, [isWizard, activePolicy, remember]);
  const currentAnalysis = userScenarios.find(item => item.id === (focusedAnalysisId || (analysisPhase === 'idle' ? journey.analysisId : undefined)));
  const reviewedAnalysis = analysisPhase !== 'error' && !isEvaluating && currentAnalysis && (!customNeedText.trim() || customNeedText.trim() === currentAnalysis.situation.trim() || (lastSuccessfulSubmission?.id === currentAnalysis.id && lastSuccessfulSubmission.input === customNeedText.trim())) ? currentAnalysis : undefined;
  useWizardAction({
    label: analysisPhase === 'error' ? 'Retry analysis' : reviewedAnalysis ? 'Continue to Ask ClaimWise' : 'Analyze scenario',
    disabled: isLoadingPolicies || isLoadingReport || !selectedPolicyId || (!reviewedAnalysis && !customNeedText.trim()),
    busy: isEvaluating,
    autoAdvanceReady: false,
    form: reviewedAnalysis && analysisPhase !== 'error' ? undefined : 'wizard-analysis-form',
    onClick: () => { if (!reviewedAnalysis) return; remember({ analysisAdvancedId: reviewedAnalysis?.id, analysisAdvancePending: undefined }); router.push(wizardHref('guidance', { analysisId: reviewedAnalysis?.id }), { scroll: false }); },
  });

  // Evaluate situation (from preset chips or free-text input)
  const handleEvaluateSituation = async (situationText: string, categoryOverride?: string, openFollowUpQuestions = true) => {
    const trimmed = situationText.trim();
    if (!trimmed || !selectedPolicyId || isEvaluating) return;

    const parsedInput = parseNeedInput(trimmed);
    if (parsedInput.error) {
      setNeedInputMessage(parsedInput.error);
      return;
    }
    setNeedInputMessage(null);

    const ticket = requests.current.begin();
    if (ticket === null) return;
    const requestedPolicyId = selectedPolicyId;
    setFocusedAnalysisId('');
    setAnalysisPhase('requesting');
    if (isWizard) remember({ analysisAdvancePending: undefined });
    setIsEvaluating(true);
    setEvaluatingSituation(trimmed);
    setErrorMessage(null);
    try {
      const evaluations: NeedEvaluation[] = await evaluateNeeds(
        analyzeCoverageScenario, requestedPolicyId, parsedInput.needs, parsedInput.context, categoryOverride || 'Member need',
      );
      if (!mounted.current || !requests.current.isCurrent(ticket)) return;

      const successfulResults = evaluations
        .filter((evaluation): evaluation is Extract<NeedEvaluation, { result: CoverageGapAnalysisResult }> => 'result' in evaluation)
        .map((evaluation) => evaluation.result);
      const failedNeeds = evaluations
        .filter((evaluation): evaluation is Extract<NeedEvaluation, { error: string }> => 'error' in evaluation)
        .map((evaluation) => `${evaluation.need}: ${evaluation.error}`);
      if (successfulResults.length) {
        setFocusedAnalysisId(successfulResults[0].id);
        setLastSuccessfulSubmission({ id: successfulResults[0].id, input: trimmed });
        remember({ policyId: selectedPolicyId, analysisId: successfulResults[0].id, analysisReady: true, title: successfulResults[0].situation });
        setUserScenarios((prev) => {
          const newNeedNames = new Set(successfulResults.map((scenario) => scenario.situation.toLowerCase()));
          const withoutDupes = prev.filter((scenario) => !newNeedNames.has(String(scenario.situation || '').toLowerCase()));
          return [...successfulResults, ...withoutDupes];
        });
        const withQuestions = openFollowUpQuestions && failedNeeds.length > 0
          ? successfulResults.find((r) => r.insurer_questions && r.insurer_questions.length > 0)
          : null;
        if (withQuestions) {
          setActiveClarifyId(withQuestions.id);
          setClarificationAnswers({});
        } else {
          setActiveClarifyId(null);
        }
      }
      if (failedNeeds.length) {
        setAnalysisPhase('error');
        setErrorMessage(`Evaluated ${successfulResults.length} of ${parsedInput.needs.length} needs. Could not evaluate: ${failedNeeds.join(' | ')}`);
      } else {
        setAnalysisPhase('complete');
      }
    } catch (err: unknown) {
      if (!mounted.current || !requests.current.isCurrent(ticket)) return;
      setAnalysisPhase('error');
      const message = err instanceof Error ? err.message : 'Unexpected error while evaluating this scenario.';
      setErrorMessage(`Could not evaluate situation: ${message}`);
    } finally {
      if (mounted.current && requests.current.isCurrent(ticket)) {
        requests.current.finish(ticket);
        setIsEvaluating(false);
        setEvaluatingSituation(null);
      }
    }
  };

  // Find the scenario currently selected for interactive clause clarification
  const clarifyingScenario = useMemo(() => {
    return activeClarifyId
      ? userScenarios.find((s) => s.id === activeClarifyId) || null
      : null;
  }, [activeClarifyId, userScenarios]);

  useEffect(() => {
    if (!clarifyingScenario && !showInsurerQuestionsModal) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActiveClarifyId(null);
        setShowInsurerQuestionsModal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [clarifyingScenario, showInsurerQuestionsModal]);

  // Handle submitting clarified scenario answers to uncover or rule out clauses
  const handleApplyClarifications = async () => {
    if (!clarifyingScenario || !selectedPolicyId || isEvaluating) return;

    const answersList = Object.entries(clarificationAnswers)
      .filter(([, ans]) => Boolean(ans && ans.trim()))
      .map(([q, ans]) => `${q.replace(/\s*\(.*?\)$/, '')}: ${ans}`);

    if (answersList.length === 0) return;

    const refinedSituation = `${clarifyingScenario.situation} [Clarified details: ${answersList.join('; ')}]`;
    setIsClarifying(true);
    setActiveClarifyId(null);
    await handleEvaluateSituation(refinedSituation, clarifyingScenario.category, false);
    setIsClarifying(false);
  };

  const visibleScenarios = userScenarios;

  // Filtered scenarios for table view
  const filteredScenarios = useMemo(() => {
    return visibleScenarios.filter((sc) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        sc.situation.toLowerCase().includes(q) ||
        sc.description.toLowerCase().includes(q) ||
        sc.category.toLowerCase().includes(q) ||
        sc.explanation.toLowerCase().includes(q)
      );
    });
  }, [visibleScenarios, searchQuery]);

  // Consolidate insurer clarifying questions - limited to 3 or 4 top questions
  const consolidatedInsurerQuestions = useMemo(() => {
    const list: Array<{ situation: string; category: string; question: string; needName: string }> = [];
    visibleScenarios
      .filter((sc) => sc.verdict === 'conditional' || sc.verdict === 'uncertain')
      .forEach((sc, index) => {
        if (sc.insurer_questions && sc.insurer_questions.length > 0) {
          sc.insurer_questions.forEach((q) => {
            if (!list.some((item) => item.question === q)) {
              list.push({
                situation: sc.situation,
                needName: coverageNeedName(sc, index),
                category: sc.category,
                question: q,
              });
            }
          });
        }
      });
    return list.slice(0, 4); // Keep limited to at most 3-4
  }, [visibleScenarios]);

  // Copy question text to clipboard
  const handleCopyQuestion = (text: string, idx: number) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedQuestionIdx(idx);
      setTimeout(() => setCopiedQuestionIdx(null), 2000);
    }
  };


  return (
    <div className={`app-page coverage-page mx-auto max-w-6xl px-4 sm:px-7 lg:px-10 py-8 sm:py-10 space-y-8 ${!activePolicy ? 'coverage-page-empty' : ''}`}>
      <HeroSection
        eyebrow="Coverage, grounded in your policy"
        title={{ firstLine: 'See where your', secondLine: 'coverage stands.' }}
        description="Choose a saved policy, describe your care scenario, and check the answer against its clauses."
        primaryAction={<Link href="/policies" className="hero-section-primary">Manage policies <ArrowRight className="h-4 w-4" /></Link>}
        variant="coverage"
        className="coverage-page-header"
      >
        <HeroIllustration variant="coverage" />
      </HeroSection>

      <GlassPanel id="coverage-policy-picker" className="coverage-policy-controls space-y-4 p-5 sm:p-6">
        {policies.length > 0 && (
          <div className="coverage-policy-toolbar flex flex-wrap items-center gap-2">
            <label htmlFor="coverage-policy-select" className="text-xs font-medium text-slate-600">
              Policy from My Policies:
            </label>
            <select
              id="coverage-policy-select"
              value={selectedPolicyId}
              onChange={(e) => handlePolicyChange(e.target.value)}
              disabled={isLoadingReport || isEvaluating}
              className="coverage-policy-select rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 shadow-xs focus:border-teal-500 focus:outline-none disabled:cursor-wait disabled:opacity-60"
            >
              <option value="">Choose a saved policy…</option>
              {policies.map((p) => (
                <option key={p.policy_id || p.document_hash} value={p.policy_id || ''} disabled={!p.policy_id}>
                  {p.document_name.replace(/\.pdf$/i, '')} ({p.total_clauses} clauses)
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => handlePolicyChange(selectedPolicyId)}
              disabled={isLoadingReport}
              title="Refresh policy coverage report"
              className="coverage-refresh-button inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white p-2 text-slate-600 shadow-2xs transition-colors hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoadingReport ? 'animate-spin text-teal-600' : ''}`} />
            </button>
          </div>
        )}

        {!activePolicy && (
          <GlassPanel as="div" className="coverage-empty-state flex flex-col items-center text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/80 bg-white/75 text-slate-500 shadow-sm">
              <FolderOpen className="h-7 w-7" />
            </div>
            <h2 className="text-base font-semibold text-slate-800">
              {isLoadingPolicies
                ? 'Loading your saved policies…'
                : policies.length
                  ? 'Choose a policy to begin'
                  : 'No policies in your profile'}
            </h2>
            <p className="mt-1 max-w-md text-sm leading-relaxed text-slate-600">
              {isLoadingPolicies
                ? 'Your profile policies will appear here when they are ready.'
                : policies.length
                  ? 'Select one of your saved policies above. Your scenario will be checked only against that policy’s clauses.'
                  : 'Add an insurance contract in My Policies first. You can then select it here and check your scenario against its clauses.'}
            </p>
          </GlassPanel>
        )}
      </GlassPanel>

      <AnalysisProgress phase={analysisPhase} policyReady={Boolean(activePolicy)}>{(currentAnalysis || (analysisPhase === 'idle' ? userScenarios[0] : undefined)) ? <section aria-label="Updated coverage analysis" aria-live="polite"><AnalysisContext analysis={currentAnalysis || userScenarios[0]} /></section> : null}</AnalysisProgress>

      {/* Error Banner */}
      {errorMessage && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 flex items-start justify-between gap-3 shadow-2xs">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Analysis notice:</span> {isWizard && /401|unauthorized|authentication required|bearer token/i.test(errorMessage) ? 'Sign in to load your saved analyses and check this scenario.' : errorMessage}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="text-rose-500 hover:text-rose-700 font-bold text-xs"
          >
            Dismiss
          </button>
        </div>
      )}

      {activePolicy && (
        <>
          {/* KPI Summary Banner - Shown when user has evaluated scenarios */}
          {userScenarios.length > 0 && (
            <section className="coverage-summary-grid grid grid-cols-1 sm:grid-cols-4 gap-3.5">
              <div className="rounded-2xl border border-teal-200 bg-teal-50/50 p-4 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-teal-800">Evaluated Scenarios</span>
                  <Clock className="h-4 w-4 text-teal-600" />
                </div>
                <div className="text-2xl font-bold text-teal-950 font-mono mt-1">
                  {userScenarios.length}
                </div>
                <p className="text-[11px] text-teal-700/90 mt-0.5">
                  Care needs evaluated against policy
                </p>
              </div>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-emerald-800">Covered Benefits</span>
                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                </div>
                <div className="text-2xl font-bold text-emerald-950 font-mono mt-1">
                  {userScenarios.filter((s) => s.verdict === 'covered').length}
                </div>
                <p className="text-[11px] text-emerald-700/90 mt-0.5">
                  Confirmed benefit coverage
                </p>
              </div>
              <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-4 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-amber-800">Conditional / Review</span>
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                </div>
                <div className="text-2xl font-bold text-amber-950 font-mono mt-1">
                  {userScenarios.filter((s) => s.verdict === 'conditional').length}
                </div>
                <p className="text-[11px] text-amber-700/90 mt-0.5">
                  Prior auth or limits apply
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-slate-700">Excluded / Uncertain</span>
                  <Info className="h-4 w-4 text-slate-500" />
                </div>
                <div className="text-2xl font-bold text-slate-900 font-mono mt-1">
                  {userScenarios.filter((s) => s.verdict === 'excluded' || s.verdict === 'uncertain').length}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Not covered or not specified
                </p>
              </div>
            </section>
          )}

          {/* 1. Input: Care Needs or Medical Situations */}
          <section className="coverage-input-panel rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4 cw-glass">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h2 className="coverage-section-title text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-teal-700" />
                  Evaluate an insurance scenario
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Describe what happened or what you need. ClaimWise checks the selected policy’s clauses and shows matching evidence.
                </p>
              </div>
              <div className="inline-flex items-center gap-1 text-[11px] text-slate-400 bg-slate-50 px-2.5 py-1 rounded-full border border-slate-200/80">
                <ShieldCheck className="h-3 w-3 text-teal-600" />
                Based on selected policy
              </div>
            </div>

            {/* Quick Questions (4 Real-Life Categories) */}
            <div data-wizard-decorative className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                  Quick Questions (4 Real-Life Categories):
                </span>
                <span className="text-[11px] text-slate-400 hidden sm:inline">
                  Click any category to evaluate against this policy
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                {FOUR_CATEGORY_QUICK_QUESTIONS.map((item) => {
                  const Icon = item.icon;
                  const isChipEvaluating = isEvaluating && evaluatingSituation === item.situation;
                  return (
                    <button
                      key={item.category}
                      type="button"
                      disabled={isEvaluating}
                      onClick={() => handleEvaluateSituation(item.situation, item.category)}
                      className={`coverage-quick-card text-left p-3.5 rounded-xl border bg-white shadow-2xs transition-all duration-150 cursor-pointer flex flex-col justify-between gap-2.5 disabled:opacity-50 ${item.borderClass} ${item.hoverClass} group`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${item.badgeClass}`}>
                          <Icon className="h-3.5 w-3.5" />
                          {item.label}
                        </span>
                        {isChipEvaluating ? (
                          <RefreshCw className="h-3.5 w-3.5 text-teal-600 animate-spin" />
                        ) : (
                          <Plus className="h-3.5 w-3.5 text-slate-400 group-hover:text-teal-700 group-hover:scale-110 transition-transform" />
                        )}
                      </div>
                      <p className="text-xs font-medium text-slate-700 group-hover:text-slate-900 leading-snug">
                        {item.situation}
                      </p>
                      <span className="text-[10px] text-slate-400 group-hover:text-teal-700 font-medium flex items-center gap-1 pt-0.5">
                        {isChipEvaluating ? 'Evaluating...' : 'Evaluate coverage \u2192'}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Free Text Input */}
            <form id="wizard-analysis-form"
              onSubmit={(e) => {
                e.preventDefault();
                handleEvaluateSituation(customNeedText);
              }}
              className="flex items-end gap-2 pt-1"
            >
              <div className="relative flex-1">
                <Search className="absolute left-3.5 top-3 h-3.5 w-3.5 text-slate-400" />
                <textarea
                  rows={3}
                  maxLength={MAX_NEED_INPUT_LENGTH}
                  value={customNeedText}
                  aria-label="Describe your insurance scenario"
                  aria-invalid={Boolean(needInputMessage)}
                  aria-describedby="coverage-need-hint"
                  onChange={(e) => {
                
                    setCustomNeedText(e.target.value);
                    if (isWizard) remember({ incidentDraft: e.target.value, ...(!journey.analysisId ? { title: e.target.value } : {}) });
                    setNeedInputMessage(null);
                  }}
                  placeholder="Describe your scenario, damage, loss, or care need (up to 2,000 characters)..."
                  className="coverage-scenario-input w-full resize-y rounded-xl border border-slate-300 py-3 pl-9 pr-4 text-xs leading-relaxed text-slate-900 placeholder-slate-400 focus:border-teal-500 focus:outline-none"
                  disabled={isEvaluating || isLoadingReport}
                />
                <div id="coverage-need-hint" className="mt-1 flex justify-between gap-3 text-[11px]">
                  <span role={needInputMessage ? 'alert' : undefined} className={needInputMessage ? 'text-rose-700' : 'text-slate-600'}>
                    {needInputMessage || 'Describe what happened in your own words. Include the details you know.'}
                  </span>
                  <span aria-live="polite" aria-atomic="true" className="shrink-0 tabular-nums text-slate-600">
                    {customNeedText.length}/{MAX_NEED_INPUT_LENGTH}
                  </span>
                </div>
              </div>
              <button
                data-wizard-inline-primary
                type="submit"
                disabled={!customNeedText.trim() || isEvaluating || isLoadingReport || !selectedPolicyId}
                className="coverage-run-button inline-flex items-center gap-1.5 rounded-xl bg-teal-700 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-teal-800 disabled:opacity-50 transition-colors shrink-0"
              >
                {isEvaluating && evaluatingSituation === customNeedText.trim() ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    Evaluating...
                  </>
                ) : (
                  <>
                    <span>{analysisPhase === 'error' ? 'Retry analysis' : 'Evaluate Scenario'}</span>
                  </>
                )}
              </button>
            </form>
          </section>

          {/* Interactive AI Clause Clarification Panel for Vague Scenarios */}
          {clarifyingScenario && clarifyingScenario.insurer_questions && clarifyingScenario.insurer_questions.length > 0 && typeof document !== 'undefined' && createPortal((
            <div
              className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto overscroll-contain bg-slate-900/20 p-4 backdrop-blur-[2px] sm:items-center"
              onClick={() => setActiveClarifyId(null)}
            >
            <section
              id="coverage-clarification-panel"
              role="dialog"
              aria-modal="true"
              aria-labelledby="coverage-clarification-title"
              onClick={(event) => event.stopPropagation()}
              className="coverage-clarification-panel my-auto max-h-[calc(100dvh-2rem)] w-full max-w-2xl overflow-y-auto overscroll-contain rounded-2xl border-2 border-teal-500/30 bg-white/95 shadow-2xl"
            >
              <div className="space-y-4 p-5 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-teal-100 pb-3.5">
                <div className="flex items-start sm:items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-teal-700 text-white shadow-2xs">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 id="coverage-clarification-title" className="text-sm font-bold text-slate-900">
                        Interactive Clause Clarification Assistant
                      </h3>
                      <span className="rounded-full bg-teal-100 text-teal-800 font-semibold px-2 py-0.5 text-[10px]">
                        Vague Scenario Details Needed
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">
                      Your scenario leaves key conditions open. Select answers below to evaluate exactly which policy clauses cover or exclude your claim:
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveClarifyId(null)}
                  aria-label="Close clarification questions"
                  className="self-end rounded-full border border-slate-200 bg-white p-2 text-slate-500 transition-colors hover:border-slate-300 hover:text-slate-800 sm:self-auto"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Target Scenario Pill */}
              <div className="flex items-center gap-2 text-xs text-slate-700 bg-white/90 border border-teal-200/60 rounded-xl px-3 py-2">
                <span className="font-semibold text-teal-900 shrink-0">Scenario being clarified:</span>
                <span className="truncate italic text-slate-800 font-medium">{clarifyingScenario.situation}</span>
              </div>

              {/* Questions with Interactive Quick Answer Pills */}
              <div className="space-y-3 pt-1">
                {clarifyingScenario.insurer_questions.map((question, qIdx) => {
                  const quickOptions = getQuestionQuickOptions(question);
                  const currentAnswer = clarificationAnswers[question] || '';

                  return (
                    <div
                      key={qIdx}
                      className="rounded-xl border border-slate-200/90 bg-white p-3.5 space-y-2.5 shadow-2xs hover:border-teal-300 transition-colors"
                    >
                      <div className="flex items-start gap-2">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-100 text-[11px] font-bold text-teal-800">
                          {qIdx + 1}
                        </span>
                        <p className="text-xs font-semibold text-slate-900 leading-snug">
                          {question}
                        </p>
                      </div>

                      {/* Quick Answer Options */}
                      <div className="pl-7 flex flex-wrap gap-2 pt-0.5">
                        {quickOptions.map((opt, optIdx) => {
                          const isSelected = currentAnswer === opt.value;
                          return (
                            <button
                              key={optIdx}
                              type="button"
                              onClick={() => {
                                setClarificationAnswers((prev) => ({
                                  ...prev,
                                  [question]: isSelected ? '' : opt.value,
                                }));
                              }}
                              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all cursor-pointer ${
                                isSelected
                                  ? 'border-teal-700 bg-teal-700 text-white shadow-2xs'
                                  : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-teal-400 hover:bg-teal-50/50'
                              }`}
                            >
                              {isSelected && <CheckCircle2 className="h-3 w-3" />}
                              <span>{opt.label}</span>
                            </button>
                          );
                        })}
                      </div>

                      {/* Custom Detail Input */}
                      <div className="pl-7 pt-2">
                        <input
                          type="text"
                          placeholder="Or type custom details for this question..."
                          value={currentAnswer}
                          onChange={(e) => {
                            const val = e.target.value;
                            setClarificationAnswers((prev) => ({
                              ...prev,
                              [question]: val,
                            }));
                          }}
                          className="w-full text-xs rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-1.5 placeholder-slate-400 focus:bg-white focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition-all"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Action Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-teal-100">
                <div className="text-[11px] text-slate-500">
                  {Object.values(clarificationAnswers).filter(Boolean).length} of{' '}
                  {clarifyingScenario.insurer_questions.length} questions answered
                </div>
                <button
                  type="button"
                  disabled={Object.values(clarificationAnswers).filter(Boolean).length === 0 || isEvaluating || isClarifying}
                  onClick={handleApplyClarifications}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-teal-700 hover:bg-teal-800 px-5 py-2.5 text-xs font-semibold text-white shadow-xs disabled:opacity-50 transition-all cursor-pointer"
                >
                  {isClarifying || isEvaluating ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      <span>Re-evaluating Clauses...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3.5 w-3.5" />
                      <span>Apply Clarifications & Re-evaluate Clauses</span>
                    </>
                  )}
                </button>
              </div>
              </div>
            </section>
            </div>
          ), document.body)}

          {/* 2. Output: Filter Tabs & Analysis Table */}
          <GlassPanel hidden={isEvaluating || (analysisPhase === 'error' && !currentAnalysis)} className="coverage-results-panel rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden space-y-0 cw-glass">
            {/* Filter Tabs + Search */}
            <div className="coverage-filter-bar flex flex-wrap items-center justify-between border-b border-slate-200 p-4 bg-slate-50/70 gap-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full border border-teal-200 bg-teal-50 px-3 py-1 font-semibold text-teal-800">
                  Evaluated Scenarios · {userScenarios.length}
                </span>
              </div>

              {/* Table Search Filter */}
              <div className="relative">
                <Search className="absolute left-2.5 top-2 h-3 w-3 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search coverage findings..."
                  className="rounded-lg border border-slate-300 pl-7 pr-2.5 py-1 text-xs text-slate-800 placeholder-slate-400 focus:border-teal-500 focus:outline-none w-48"
                />
              </div>
            </div>

            {/* Table or Loading State */}
            {isLoadingReport ? (
              <div role="status" aria-label="Loading coverage findings" className="p-6 space-y-4">
                <Skeleton className="h-40" /><Skeleton className="h-40" />
                <p className="text-xs text-slate-600">Loading policy coverage findings…</p>
              </div>
            ) : filteredScenarios.length === 0 ? (
              <div className="p-10 text-center space-y-2">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-700 border border-teal-100">
                  <ShieldCheck className="h-6 w-6" />
                </div>
                <p className="text-sm font-semibold text-slate-800">
                  {searchQuery.trim()
                    ? 'No coverage findings match your search.'
                    : 'No scenarios evaluated yet'}
                </p>
                <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                  {searchQuery.trim()
                    ? 'Try adjusting your search query.'
                    : 'Choose one of the quick questions above or describe your care scenario to check coverage against this policy’s clauses.'}
                </p>
              </div>
            ) : (
              <div className="coverage-table-scroll overflow-x-auto">
                {filteredScenarios.some((scenario) => !scenario.clauses?.length) && (
                  <p className="border-b border-slate-100 px-4 py-2 text-[11px] text-slate-500">
                    Rows without citations have no clause evidence to display; missing evidence does not mean the service is excluded.
                  </p>
                )}
                <StaggerGroup className="cw-need-list" role="list" aria-label="Coverage findings by need">
                  {filteredScenarios.map((sc, index) => <StaggerItem key={sc.id} role="listitem"><CoverageNeedRow analysis={sc} index={index} isUserCustom={userScenarios.some(item => item.id === sc.id)} onClarify={() => { setActiveClarifyId(sc.id); }} /></StaggerItem>)}
                </StaggerGroup>
              </div>
            )}
          </GlassPanel>

          {/* Keep the insurer question list available without adding a long section below the results. */}
          {consolidatedInsurerQuestions.length > 0 && (
            <>
              <button
                type="button"
                onClick={() => setShowInsurerQuestionsModal(true)}
                className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-xs font-semibold text-amber-950 shadow-sm transition-colors hover:bg-amber-100"
              >
                <MessageSquare className="h-4 w-4" />
                Questions to ask your insurer
                <span className="rounded-full bg-amber-200/70 px-2 py-0.5 text-[10px]">
                  {consolidatedInsurerQuestions.length}
                </span>
              </button>

              {showInsurerQuestionsModal && typeof document !== 'undefined' && createPortal((
                <div
                  className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto overscroll-contain bg-slate-900/20 p-4 backdrop-blur-[2px] sm:items-center"
                  onClick={() => setShowInsurerQuestionsModal(false)}
                >
                  <section
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="coverage-insurer-questions-title"
                    onClick={(event) => event.stopPropagation()}
                    className="coverage-questions-panel my-auto flex max-h-[calc(100dvh-2rem)] w-full max-w-2xl flex-col gap-4 overflow-hidden rounded-2xl border border-amber-200 bg-white/95 p-5 shadow-2xl sm:p-6"
                  >
                    <div className="flex items-start justify-between gap-4 border-b border-amber-200/70 pb-3">
                      <div className="flex items-start gap-2.5">
                        <span className="rounded-xl bg-amber-100 p-2 text-amber-800">
                          <MessageSquare className="h-4 w-4" />
                        </span>
                        <div>
                          <h2 id="coverage-insurer-questions-title" className="text-base font-semibold text-amber-950">
                            Questions to ask your insurer
                          </h2>
                          <p className="mt-1 text-xs leading-relaxed text-amber-900/75">
                            Use these prompts to clarify conditions or missing details before receiving care.
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        aria-label="Close insurer questions"
                        onClick={() => setShowInsurerQuestionsModal(false)}
                        className="rounded-full border border-amber-200 bg-white p-2 text-slate-500 transition-colors hover:text-slate-800"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>

                    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain pr-1">
                      {consolidatedInsurerQuestions.map((item, idx) => (
                        <div key={`${item.situation}-${idx}`} className="rounded-xl border border-amber-200 bg-white/90 p-3.5 text-xs shadow-sm">
                          <div className="mb-2 flex items-center justify-between gap-3 text-[11px]">
                            <span className="font-semibold text-slate-800">{item.needName}</span>
                            <span className="shrink-0 rounded border border-teal-200 bg-teal-50 px-1.5 py-0.5 text-[10px] font-medium text-teal-800">
                              {item.category || 'Benefit detail'}
                            </span>
                          </div>
                          <p className="rounded-lg border border-slate-100 bg-slate-50/70 p-2 font-medium italic leading-relaxed text-slate-800">
                            &ldquo;{item.question}&rdquo;
                          </p>
                          <div className="flex justify-end pt-2">
                            <button
                              type="button"
                              onClick={() => handleCopyQuestion(item.question, idx)}
                              className="inline-flex items-center gap-1 text-[11px] text-slate-500 transition-colors hover:text-teal-700"
                            >
                              {copiedQuestionIdx === idx ? (
                                <><Check className="h-3 w-3 text-emerald-600" /><span className="font-semibold text-emerald-700">Copied</span></>
                              ) : (
                                <><Copy className="h-3 w-3" /><span>Copy question</span></>
                              )}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              ), document.body)}
            </>
          )}
        </>
      )}

      {/* Strict Grounding & Anti-Hallucination Disclaimer Footer */}
      <footer className="coverage-page-footer border-t border-slate-200 pt-5 text-center text-xs text-slate-400 space-y-1">
        <p>
          Coverage explanations are based on the uploaded policy text and link to relevant clauses when available.
        </p>
        <p>
          Explanations are informational only and do not guarantee insurance claim approval or replace formal insurer predetermination.
        </p>
      </footer>
    </div>
  );
}
