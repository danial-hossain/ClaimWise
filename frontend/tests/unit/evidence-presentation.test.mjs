import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';
import { analysisPresentation, guidancePresentation, requestEpoch } from '../../src/lib/evidencePresentation.ts';

const proof = { clause_id: 'C7', page_number: 4, policy_id: 'owned', exact_quote: 'Notify the insurer and retain the repair invoice.', verified: true };
const saved = { id: 'analysis1', policy_id: 'owned', situation: 'Incident', verdict: 'conditional',
  explanation: 'Coverage depends on the cited condition.', clauses: [proof], insurer_questions: ['Which endorsement applies?'],
  guidance: [{ text: 'Retain the invoice for your insurer.', citations: [proof] }] };

test('analysis and guidance use their own API fields and keep their citations', () => {
  assert.equal(analysisPresentation(saved).explanation, saved.explanation);
  assert.deepEqual(analysisPresentation(saved).citations, [proof]);
  assert.equal(guidancePresentation(saved).actions[0].text, saved.guidance[0].text);
  assert.deepEqual(guidancePresentation(saved).actions[0].citations, [proof]);
});
test('legacy analysis never fills guidance from interpretation or a draft on the same policy', () => {
  assert.deepEqual(guidancePresentation({ ...saved, guidance: undefined }).actions, []);
});
test('missing and malformed fields render safe empty states', () => {
  for (const bad of [null, [], {}, { guidance: 'text', clauses: {}, explanation: 42, insurer_questions: null }]) {
    assert.equal(typeof analysisPresentation(bad).explanation, 'string');
    assert.deepEqual(guidancePresentation(bad).actions, []);
  }
});
test('duplicate interpretation and unsupported guidance are not rendered as next steps', () => {
  const result = guidancePresentation({ ...saved, guidance: [
    { text: saved.explanation, citations: [proof] }, { text: 'Unsupported action', citations: [] }, null,
  ] });
  assert.deepEqual(result.actions, []);
});
test('second question and changed scope invalidate pending answers', () => {
  const requests = requestEpoch(), first = requests.begin(), second = requests.begin();
  assert.equal(requests.isCurrent(first), false);
  assert.equal(requests.isCurrent(second), true);
  requests.invalidate();
  assert.equal(requests.isCurrent(second), false);
});
test('a new response cannot inherit the previous response guidance', () => {
  assert.equal(guidancePresentation(saved).actions.length, 1);
  assert.deepEqual(guidancePresentation({ ...saved, id: 'analysis2', guidance: [] }).actions, []);
});

// Render the real TSX components with only framework/router shells replaced.
// The data adapter and markup remain the production implementation.
function component(relative) {
  const file = new URL(relative, import.meta.url);
  const code = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, esModuleInterop: true,
  } }).outputText;
  const native = createRequire(file), compiled = { exports: {} };
  const require = name => {
    if (name === '@/lib/evidencePresentation') return { analysisPresentation, guidancePresentation };
    if (name === '@/components/ui/CitationChip' || name === './CitationChip') return { __esModule: true, default: ({ citation }) => React.createElement('blockquote', null, citation.exact_quote) };
    if (name === './AbstainNotice') return { __esModule: true, default: component('../../src/components/ui/AbstainNotice.tsx') };
    if (name === '@/context/ScenarioContext') return { useScenario: () => ({ remember() {}, isWizard: true, scenario: { claimDraft: { guidance: { policy_id: 'owned', obstacles: [{ description: 'OLD INCIDENT' }] } } } }) };
    if (name === 'next/navigation') return { usePathname: () => '/coverage' };
    if (name === 'next/link') return { __esModule: true, default: ({ children, href }) => React.createElement('a', { href }, children) };
    if (name === '@/lib/claimWorkflow') return { analysisLink: () => '/coverage' };
    if (name === '@/lib/wizard') return { wizardUrl: () => '/workspace' };
    return native(name);
  };
  new Function('require', 'module', 'exports', code)(require, compiled, compiled.exports);
  return compiled.exports.default;
}
test('real Guidance component displays steps, not the analysis or stale draft', () => {
  const View = component('../../src/components/features/wizard/GuidanceSummary.tsx');
  const html = renderToStaticMarkup(React.createElement(View, { analysis: saved }));
  assert.ok(html.includes(saved.guidance[0].text));
  assert.ok(html.includes(proof.exact_quote));
  assert.ok(!html.includes(saved.explanation));
  assert.ok(!html.includes('OLD INCIDENT'));
});
test('real Analysis component displays interpretation and source citations', () => {
  const View = component('../../src/components/ui/AnalysisContext.tsx');
  const html = renderToStaticMarkup(React.createElement(View, { analysis: saved }));
  assert.ok(html.includes(saved.explanation));
  assert.ok(html.includes(proof.exact_quote));
  assert.ok(!html.includes(saved.guidance[0].text));
});

test('qualified Ask ClaimWise answer retains its explanation and verified evidence', () => {
  const View = component('../../src/components/ui/GroundedAnswer.tsx');
  const html = renderToStaticMarkup(React.createElement(View, { response: {
    evidence_sufficient: false, evidence_status: 'evidence_unavailable',
    abstention_reason: 'Schedule missing', citations: [proof], evidence_limitations: ['Endorsement unavailable'],
  } }, React.createElement('p', null, 'Available wording establishes the custody condition.')));
  assert.ok(html.includes('Available wording establishes the custody condition.'));
  assert.ok(html.includes(proof.exact_quote));
  assert.ok(html.includes('Schedule missing'));
  assert.ok(html.includes('Endorsement unavailable'));
  assert.ok(!html.includes('Not specified in your policy'));
});
