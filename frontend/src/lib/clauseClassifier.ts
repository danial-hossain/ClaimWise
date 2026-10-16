import React from 'react';
import { ExtractedClause } from '@/types/api';

/**
 * Determines whether an extracted text block is an actual contractual policy clause
 * rather than a question (FAQ), page header/footer, TOC line, form field, or normal text.
 */
export function isPolicyClause(clause: Partial<ExtractedClause>): boolean {
  const rawText = (clause.text || '').trim();
  const rawHeading = (clause.clause_heading || '').trim();
  const lowerHeading = rawHeading.toLowerCase();
  const lowerText = rawText.toLowerCase();

  // Preserve a Q&A pair as one readable clause. The extractor joins adjacent
  // question and answer blocks with a blank line; allow these through even
  // though the heading itself is phrased as a question.
  const [questionLine, ...answerLines] = rawText.split(/\r?\n/);
  const hasAnswer = answerLines.join(' ').trim().length >= 25;
  const isQuestion = /^(?:what|how|why|when|where|who|which|can|could|would|should|do|does|did|is|are|was|were)\b/i.test(questionLine || '') && (questionLine || '').trim().endsWith('?');
  if (isQuestion && hasAnswer) return true;

  if (clause.is_clause === false) {
    return false;
  }

  // 1. FILTER OUT QUESTIONS / FAQS
  // A. Heading ends with a question mark
  if (rawHeading.endsWith('?')) return false;

  // B. Heading starts with interrogative question words
  const questionHeadingRegex = /^(?:what|how|why|when|where|who|which|can\s+(?:i|you|we|a)|do\s+(?:i|we|you)|does\s+|is\s+(?:it|there|this)|are\s+(?:there|we|you)|should\s+(?:i|we)|could\s+(?:i|we)|would\s+|how\s+do|how\s+can|how\s+much|how\s+often)\b/i;
  if (questionHeadingRegex.test(rawHeading)) return false;

  // C. Heading indicates FAQ / Q&A section
  const faqHeadingRegex = /^(?:faq|faqs|frequently\s+asked\s+questions?|common\s+questions?|questions?\s*&?\s*answers?|q\s*&\s*a|ask\s+a\s+question|questions\?)\b/i;
  if (faqHeadingRegex.test(lowerHeading)) return false;

  // D. First line of text is a question (and no explicit section number exists)
  const firstLine = rawText.split('\n')[0].trim();
  if (!clause.section_number && firstLine.endsWith('?') && questionHeadingRegex.test(firstLine)) {
    return false;
  }

  // 2. FILTER OUT HEADERS, FOOTERS, PAGE NUMBERS & TOC
  // A. Page number strings
  if (/^(?:page\s+\d+(\s+of\s+\d+)?|\d+\s+of\s+\d+|-\s*\d+\s*-|\[\s*\d+\s*\]|\d+)$/i.test(rawText)) {
    return false;
  }
  if (/^page\s+\d+$/i.test(rawHeading)) {
    return false;
  }

  // B. Table of Contents / Index markers
  if (/^(?:table\s+of\s+contents|contents|index|table\s+of\s+benefits)\b/i.test(lowerHeading)) {
    return false;
  }

  // C. Copyright, confidentiality, and form identifiers
  if (/^(?:all\s+rights\s+reserved|copyright\s*©?|confidential|printed\s+in\s+u\.?s\.?a\.?|cms-\d+|form\s+[a-z0-9\-]+)/i.test(lowerText)) {
    return false;
  }

  // D. Customer service / website contact blocks
  if (/^(?:for\s+customer\s+service|for\s+questions\s+call|call\s+customer\s+service|visit\s+our\s+website|tty\s*:?\s*\d+|call\s+1-\d{3}-\d{3}-\d{4})/i.test(lowerText) && rawText.length < 160) {
    return false;
  }

  // E. Signature and form fill blocks
  if (/^(?:signature|member\s+signature|authorized\s+signature|print\s+name|applicant\s+name|date)\s*[:_]/i.test(lowerText)) {
    return false;
  }

  // F. Document titles or standalone marketing labels
  if (/^(?:summary\s+of\s+benefits\s+and\s+coverage|uniform\s+glossary|welcome\s+to\s+your\s+plan|introduction\s+to\s+your\s+benefits)\b/i.test(lowerHeading) && rawText.length < 100 && !clause.section_number) {
    return false;
  }

  // 3. FILTER OUT TRIVIAL SNIPPETS
  // Very short snippets with no section number or heading
  if (rawText.length < 25 && !clause.section_number && !rawHeading) {
    return false;
  }

  // 4. IDENTIFY ACTUAL CLAUSES
  // A. Explicit Section Number (e.g. SEC-1.1, Article 4, 2.3)
  if (clause.section_number) {
    return true;
  }

  // B. Clause Heading keywords
  const policyKeywords = [
    'benefit', 'coverage', 'covered', 'exclusion', 'limitation', 'deductible',
    'copay', 'coinsurance', 'out-of-pocket', 'eligibility', 'termination',
    'inpatient', 'outpatient', 'emergency', 'prescription', 'claim',
    'authorization', 'pre-auth', 'appeal', 'grievance', 'coordination',
    'subrogation', 'definition', 'provision', 'condition', 'schedule',
    'allowance', 'reimbursement', 'liability', 'rider', 'endorsement',
    'dental', 'vision', 'mental health', 'maternity', 'preventive',
    'cost sharing', 'hospital', 'service', 'general provision', 'rights',
    'obligation', 'effective date', 'dependent', 'premium'
  ];
  if (rawHeading && policyKeywords.some((kw) => lowerHeading.includes(kw))) {
    return true;
  }

  // C. Contractual policy provisions in body text
  const contractualTerms = [
    /\b(?:shall|must|is\s+covered|are\s+covered|will\s+be\s+covered|not\s+covered|excluded|exclusion|subject\s+to|in\s+the\s+event\s+of|payable|benefits\s+will|deductible|coinsurance|copayment|pre-authorization|prior\s+authorization|medically\s+necessary|maximum\s+allowable|out-of-pocket\s+maximum|eligible\s+expenses|the\s+company\s+will|the\s+insured\s+shall|the\s+policyholder|coverage\s+terminates)\b/i
  ];
  if (contractualTerms.some((pat) => pat.test(lowerText))) {
    return true;
  }

  // D. Heuristic or high confidence heading with substantive text (not a question or metadata)
  if ((clause.heading_confidence === 'high' || clause.heading_confidence === 'heuristic') && rawText.length >= 35) {
    return true;
  }

  // E. Fallback: substantial paragraph (>60 chars) without question or metadata noise
  if (rawText.length >= 60 && !rawHeading.endsWith('?') && !lowerText.includes('frequently asked')) {
    return true;
  }

  return false;
}

export interface ClauseContentItem {
  type: 'paragraph' | 'bullet';
  text: string;
}

/**
 * Normalizes and formats raw clause text:
 * - Unwraps broken soft line-breaks so sentences flow naturally.
 * - Repairs hyphenated words split across lines.
 * - Detects and formats bullet lists and numbered items.
 * - Removes duplicate heading text from the first line when already displayed in header.
 */
export function parseClauseContent(rawText: string, heading?: string | null): ClauseContentItem[] {
  if (!rawText) return [];
  let text = rawText
    .replace(/[\uFFFD\u25A0-\u25A3\u2610-\u2612]/g, ' ')
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g, ' ')
    .trim();

  // If text starts with the exact heading or section number, remove that first line to prevent duplication
  if (heading) {
    const firstNewline = text.indexOf('\n');
    const firstLine = (firstNewline !== -1 ? text.substring(0, firstNewline) : text).trim();
    const cleanHeading = heading.replace(/^[A-Z0-9.\-:]+\s*/i, '').trim().toLowerCase();
    const cleanFirstLine = firstLine.replace(/^[A-Z0-9.\-:]+\s*/i, '').trim().toLowerCase();

    if (
      cleanFirstLine === cleanHeading ||
      firstLine.toLowerCase() === heading.toLowerCase() ||
      (cleanHeading.length > 5 && cleanFirstLine.includes(cleanHeading))
    ) {
      text = firstNewline !== -1 ? text.substring(firstNewline + 1).trim() : '';
    }
  }

  if (!text) {
    return [{ type: 'paragraph', text: 'Clause provision details specified under section heading above.' }];
  }

  // 1. Repair hyphenated word wrap: e.g. "pre-\nauthorization" -> "pre-authorization"
  text = text.replace(/(\b[A-Za-z]+)[-\u2010\u2013]\r?\n\s*([A-Za-z]+\b)/g, '$1$2');

  // 2. Split on double linebreaks into distinct paragraphs
  const rawParagraphs = text.split(/\r?\n\s*\r?\n/);
  const items: ClauseContentItem[] = [];

  for (const rawPara of rawParagraphs) {
    const rawLines = rawPara
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);

    if (rawLines.length === 0) continue;

    let currentFlow = '';

    for (const line of rawLines) {
      // Detect bullet or numbered items
      const isBullet = /^[•\-\*▪►]\s*(.+)/.exec(line);
      const isNumbered = /^(?:\(\d+\)|\(\w+\)|\d+[\.\)]|[a-zA-Z][\.\)])\s*(.+)/.exec(line);

      if (isBullet || isNumbered) {
        if (currentFlow) {
          items.push({ type: 'paragraph', text: currentFlow.trim() });
          currentFlow = '';
        }
        items.push({ type: 'bullet', text: (isBullet ? isBullet[1] : line).trim() });
      } else {
        if (line.endsWith(':')) {
          if (currentFlow) {
            currentFlow += ' ' + line;
            items.push({ type: 'paragraph', text: currentFlow.trim() });
            currentFlow = '';
          } else {
            items.push({ type: 'paragraph', text: line });
          }
        } else {
          currentFlow = currentFlow ? `${currentFlow} ${line}` : line;
        }
      }
    }

    if (currentFlow) {
      items.push({ type: 'paragraph', text: currentFlow.trim() });
    }
  }

  return items;
}

/**
 * Highlights search matches within text using an accessible <mark> element.
 */
export function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query || !query.trim()) return text;
  const trimmed = query.trim();
  const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escaped})`, 'gi');
  const parts = text.split(regex);
  if (parts.length <= 1) return text;
  return parts.map((part, i) =>
    part.toLowerCase() === trimmed.toLowerCase()
      ? React.createElement(
          'mark',
          {
            key: i,
            className: 'bg-amber-100 text-amber-950 font-semibold px-0.5 rounded-xs',
          },
          part
        )
      : part
  );
}
