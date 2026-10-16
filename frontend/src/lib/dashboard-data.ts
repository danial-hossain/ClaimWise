import { PolicyExtractionResult, ClaimRecord, ExtractedClause } from '@/types/api';
import { SummaryMetric } from '@/components/features/dashboard/SummaryStrip';
import { AttentionItem } from '@/components/features/dashboard/AttentionList';

/**
 * Extract integer dollar value from text using regex.
 */
function extractDollarAmount(text: string, keywordPattern: RegExp): number | null {
  for (const sentence of text.split(/[.;\n]/)) {
    if (keywordPattern.test(sentence)) {
      const match = sentence.match(/\$([0-9,]+)/);
      if (match) {
        const val = parseInt(match[1].replace(/,/g, ''), 10);
        if (!isNaN(val) && val > 0) return val;
      }
    }
  }
  return null;
}

/**
 * Derive summary KPI metrics from real loaded policies and claims data.
 * KPI row includes:
 * 1. Policies on file
 * 2. Open claims
 * 3. Claims needing review
 */
export function deriveSummaryMetrics(
  policies: PolicyExtractionResult[],
  claims: ClaimRecord[] = []
): SummaryMetric[] {
  const policiesCount = policies?.length || 0;
  const openClaimsCount = claims.filter((c) => c.status !== 'closed').length;
  
  // Claims needing review: denied, draft awaiting adjudication, or items flagged with potential exclusion or review requirements
  const claimsNeedingReview = claims.filter(
    (c) =>
      c.status === 'denied' ||
      c.status === 'draft' ||
      c.adjudicated_items?.some(
        (i) => i.decision_status === 'potentially_excluded' || i.decision_status === 'requires_review' || i.decision_status === 'insufficient_evidence'
      )
  ).length;

  return [
    {
      id: 'policies-count',
      label: 'Policies on file',
      value: policiesCount,
      subtext: policiesCount === 0 ? 'No policies uploaded' : policiesCount === 1 ? '1 active policy schedule' : `${policiesCount} active policy schedules`,
    },
    {
      id: 'open-claims',
      label: 'Open claims',
      value: openClaimsCount,
      subtext: openClaimsCount === 0 ? 'No open claims' : openClaimsCount === 1 ? '1 claim in progress' : `${openClaimsCount} claims in progress`,
    },
    {
      id: 'claims-needing-review',
      label: 'Claims needing review',
      value: claimsNeedingReview,
      subtext: claimsNeedingReview === 0 ? 'All claims up to date' : claimsNeedingReview === 1 ? '1 claim requires action' : `${claimsNeedingReview} claims require action`,
      highlight: claimsNeedingReview > 0,
    },
  ];
}

export interface PolicyFinancialTerms {
  hasData: boolean;
  deductible: string | null;
  deductibleRaw: number | null;
  oopMax: string | null;
  oopMaxRaw: number | null;
  appliedDeductible: number;
  sourceClauseRef?: string;
  sourcePolicyName?: string;
}

/**
 * Derive policy financial terms (Deductible and Out-of-pocket maximum)
 * only when verified policy evidence exists in uploaded contracts.
 */
export function derivePolicyFinancialTerms(
  policies: PolicyExtractionResult[],
  claims: ClaimRecord[] = []
): PolicyFinancialTerms | null {
  if (!policies || policies.length === 0) return null;

  const primary = policies[0];
  const allClauses = primary.clauses || [];

  let deductibleVal: number | null = null;
  let deductibleClause: ExtractedClause | null = null;
  for (const c of allClauses) {
    const val = extractDollarAmount(c.text, /\bdeductible\b/i);
    if (val !== null) {
      deductibleVal = val;
      deductibleClause = c;
      break;
    }
  }

  let oopVal: number | null = null;
  let oopClause: ExtractedClause | null = null;
  for (const c of allClauses) {
    const val = extractDollarAmount(c.text, /(?:out-of-pocket|oop\s*max|maximum\s*out-of-pocket)/i);
    if (val !== null) {
      oopVal = val;
      oopClause = c;
      break;
    }
  }

  if (deductibleVal === null && oopVal === null) {
    return {
      hasData: false,
      deductible: null,
      deductibleRaw: null,
      oopMax: null,
      oopMaxRaw: null,
      appliedDeductible: 0,
    };
  }

  let appliedDed = 0;
  const adjudicatedClaim = claims.find((c) => c.eob);
  if (adjudicatedClaim?.eob && deductibleVal !== null) {
    appliedDed = (adjudicatedClaim.eob.total_deductible_applied_cents || 0) / 100;
  }

  const remainingDed = deductibleVal !== null ? Math.max(0, deductibleVal - appliedDed) : null;
  const dedStr = remainingDed !== null ? `$${remainingDed.toLocaleString()}` : null;
  const oopStr = oopVal !== null ? `$${oopVal.toLocaleString()}` : null;
  const refClause = deductibleClause || oopClause;

  return {
    hasData: true,
    deductible: dedStr,
    deductibleRaw: deductibleVal,
    oopMax: oopStr,
    oopMaxRaw: oopVal,
    appliedDeductible: appliedDed,
    sourceClauseRef: refClause ? `Clause ${refClause.clause_id}, p. ${refClause.page_number}` : undefined,
    sourcePolicyName: primary.document_name,
  };
}

/**
 * Derive needs attention items from real loaded policies, clauses, and claims.
 * Returns empty array if no policies are uploaded. Maximum 4 prioritized items.
 */
export function deriveAttentionItems(
  policies: PolicyExtractionResult[],
  claims: ClaimRecord[] = []
): AttentionItem[] {
  if (!policies || policies.length === 0) {
    return [];
  }

  const items: AttentionItem[] = [];
  const primary = policies[0];
  const allClauses: ExtractedClause[] = [];
  policies.forEach((p) => {
    if (p.clauses) allClauses.push(...p.clauses);
  });

  // 1. Check for adverse determinations / denied claims (Highest priority)
  for (const claim of claims) {
    const flaggedItem = claim.adjudicated_items?.find((i) => i.decision_status === 'potentially_excluded' || i.decision_status === 'requires_review' || i.decision_status === 'insufficient_evidence');
    const isDenied =
      claim.status?.toLowerCase() === 'denied' ||
      Boolean(flaggedItem);

    if (isDenied) {
      const citation = flaggedItem?.evidence_citations?.find((c) => c.verified);
      items.push({
        id: `claim-denial-${claim.id}`,
        title: `Claim ${claim.claim_reference || claim.id.slice(0, 8)} needs review`,
        explanation: flaggedItem?.decision_rationale || `Claim status is ${claim.status}. Review the claim record and supporting evidence.`,
        clauseRef: citation ? `Clause ${citation.clause_id}, p. ${citation.page_number}` : undefined,
        status: flaggedItem?.decision_status === 'potentially_excluded' ? 'excluded' : 'uncertain',
        statusLabel: 'Action required',
        actionLabel: 'Review claim',
        actionHref: '/claims',
        importance: 1,
      });
      break;
    } else if (claim.status?.toLowerCase() === 'draft' || !claim.eob) {
      items.push({
        id: `claim-draft-${claim.id}`,
        title: `Claim ${claim.claim_reference || claim.id.slice(0, 8)} pending adjudication`,
        explanation: `Claim status is ${claim.status}. Billed amount: $${(claim.total_billed_cents / 100).toFixed(2)}.`,
        clauseRef: claim.bill_document_name ? `Bill: ${claim.bill_document_name}` : undefined,
        status: 'conditional',
        statusLabel: 'Pending review',
        actionLabel: 'Adjudicate claim',
        actionHref: '/claims',
        importance: 2,
      });
      break;
    }
  }

  // 2. Dual coverage overlap notice (if 2+ policies)
  if (policies.length >= 2) {
    const p1 = policies[0].document_name.replace(/\.pdf$/i, '').replace(/_/g, ' ');
    const p2 = policies[1].document_name.replace(/\.pdf$/i, '').replace(/_/g, ' ');
    items.push({
      id: 'dual-coverage-overlap',
      title: 'Dual coverage overlap identified',
      explanation: `Two uploaded policies are on file: ${p1} and ${p2}. Review coordination of benefits to establish how they work together.`,
      status: 'conditional',
      statusLabel: 'Dual coverage',
      actionLabel: 'Compare plans',
      actionHref: '/compare',
      importance: 2,
    });
  }

  // 3. Prior authorization requirement in clauses
  const priorAuthClause = allClauses.find((c) =>
    /(?:prior\s*authorization|precertification)\s*(?:from\s+the\s+plan\s*)?is\s*required/i.test(c.text)
  ) || allClauses.find((c) =>
    /requires?\s*(?:prior\s*authorization|precertification)/i.test(c.text)
  );

  if (priorAuthClause) {
    items.push({
      id: `prior-auth-${priorAuthClause.clause_id}`,
      title: 'Advance prior authorization requirement',
      explanation: `Review the policy language: “${priorAuthClause.text.slice(0, 180).trim()}${priorAuthClause.text.length > 180 ? '…' : ''}”`,
      clauseRef: `Clause ${priorAuthClause.clause_id}, p. ${priorAuthClause.page_number}`,
      status: 'conditional',
      statusLabel: 'Pre-certification',
      actionLabel: 'Ask rules',
      actionHref: '/workspace',
      importance: 3,
    });
  }

  // 4. Exclusions / Coverage Gaps in clauses
  const gapClause = allClauses.find(
    (c) =>
      /dental\s+and\s+vision.*?not\s+specified/i.test(c.text) ||
      /routine\s+dental.*?not\s+specified/i.test(c.text)
  );

  const cosmeticExclusion = allClauses.find(
    (c) => /cosmetic.*?not\s+covered/i.test(c.text) || /cosmetic.*?excluded/i.test(c.text)
  );

  if (gapClause) {
    items.push({
      id: `gap-${gapClause.clause_id}`,
      title: 'Coverage gap: Adult dental & vision',
      explanation: `The extracted clause says: “${gapClause.text.slice(0, 180).trim()}${gapClause.text.length > 180 ? '…' : ''}”`,
      clauseRef: `Clause ${gapClause.clause_id}, p. ${gapClause.page_number}`,
      status: 'uncertain',
      statusLabel: 'Not specified',
      actionLabel: 'Inspect gaps',
      actionHref: '/coverage',
      importance: 3,
    });
  } else if (cosmeticExclusion) {
    items.push({
      id: `exclusion-${cosmeticExclusion.clause_id}`,
      title: 'Coverage exclusion: Cosmetic procedures',
      explanation: `The extracted clause says: “${cosmeticExclusion.text.slice(0, 180).trim()}${cosmeticExclusion.text.length > 180 ? '…' : ''}”`,
      clauseRef: `Clause ${cosmeticExclusion.clause_id}, p. ${cosmeticExclusion.page_number}`,
      status: 'excluded',
      statusLabel: 'Excluded',
      actionLabel: 'Inspect terms',
      actionHref: '/coverage',
      importance: 4,
    });
  }

  // 5. Waiting period clause check
  const waitingClause = allClauses.find((c) =>
    /waiting\s*period/i.test(c.text)
  );
  if (waitingClause && items.length < 4) {
    items.push({
      id: `waiting-${waitingClause.clause_id}`,
      title: 'Waiting period terms documented',
      explanation: `The extracted clause says: “${waitingClause.text.slice(0, 180).trim()}${waitingClause.text.length > 180 ? '…' : ''}”`,
      clauseRef: `Clause ${waitingClause.clause_id}, p. ${waitingClause.page_number}`,
      status: 'conditional',
      statusLabel: 'Waiting period',
      actionLabel: 'View policy',
      actionHref: '/policies',
      importance: 4,
    });
  }

  return items.slice(0, 4);
}
