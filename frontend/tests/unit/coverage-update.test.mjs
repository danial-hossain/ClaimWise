import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { coverageRequestGate, evaluateNeeds } from '../../src/lib/coverageUpdate.ts';
import { autoAdvanceDelay } from '../../src/lib/wizard-behavior.ts';

const page = readFileSync(new URL('../../src/app/coverage/page.tsx', import.meta.url), 'utf8');
const ast = ts.createSourceFile('coverage.tsx', page, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
function find(predicate) {
  let found;
  function visit(node) { if (predicate(node)) found = node; else ts.forEachChild(node, visit); }
  visit(ast);
  assert.ok(found);
  return found;
}
function compile(code, scope) {
  const js = ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(scope), js)(...Object.values(scope));
}
const parseNeedInput = compile(find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'parseNeedInput').getText(ast)
  + '\nreturn parseNeedInput;', { MAX_NEED_INPUT_LENGTH: 2000 });
const handlerSource = find(n => ts.isVariableDeclaration(n) && n.name.getText(ast) === 'handleEvaluateSituation').initializer.getText(ast);
const old = { id: 'old', policy_id: 'owned', situation: 'Previous scenario', explanation: 'Old findings', clauses: [], insurer_questions: [], verdict: 'uncertain' };
const proof = { clause_id: 'SEC-2', policy_id: 'owned', page_number: 5, exact_quote: 'Coverage is subject to the Schedule.', verified: true };
function response(situation, id = 'new') { return { ...old, id, situation, explanation: 'New findings for ' + situation, clauses: [proof], evidence_status: 'evidence_unavailable' }; }

// Execute the real page's submission handler with its real parsing/request
// helpers. Only React setters and the external API boundary are test doubles.
function harness(api, input = 'Updated incident details') {
  const state = { input, phase: 'idle', results: [old], focused: 'old', loading: false, error: null, navigations: [], remembered: [] };
  const requests = { current: coverageRequestGate() }, mounted = { current: true };
  const set = key => value => { state[key] = typeof value === 'function' ? value(state[key]) : value; };
  const scope = {
    selectedPolicyId: 'owned', isEvaluating: false, isWizard: true, parseNeedInput, requests, mounted,
    analyzeCoverageScenario: api, evaluateNeeds, remember: value => state.remembered.push(value),
    setNeedInputMessage: set('inputError'), setAnalysisPhase: set('phase'), setIsEvaluating: set('loading'),
    setEvaluatingSituation: set('evaluating'), setErrorMessage: set('error'), setFocusedAnalysisId: set('focused'),
    setLastSuccessfulSubmission: set('receipt'), setUserScenarios: set('results'), setActiveClarifyId: set('clarify'),
    setClarificationAnswers: set('answers'), setCustomNeedText: set('input'),
    router: { push: href => state.navigations.push(href), replace: href => state.navigations.push(href) },
    wizardHref: () => '/claims/new?step=guidance',
  };
  const submit = compile('const handler = ' + handlerSource + ';\nreturn handler;', scope);
  return { state, requests, mounted, submit: () => submit(state.input) };
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('actual update handler submits revised values, then focuses the returned analysis without navigation', async () => {
  const calls = [];
  const h = harness(async payload => { calls.push(payload); return { data: response(payload.situation), error: null }; });
  await h.submit();
  assert.deepEqual(calls, [{ policy_id: 'owned', situation: h.state.input, category: 'Member need', description: undefined }]);
  assert.equal(h.state.phase, 'complete');
  assert.equal(h.state.focused, 'new');
  assert.equal(h.state.results[0].explanation, 'New findings for ' + h.state.input);
  assert.deepEqual(h.state.results[0].clauses, [proof]);
  assert.deepEqual(h.state.navigations, []);
  assert.ok(!h.state.remembered.some(item => item.analysisAdvancePending));
  assert.equal(h.state.input, 'Updated incident details');
});

test('loading starts immediately and a duplicate click cannot submit twice', async () => {
  const pending = deferred(); let calls = 0;
  const h = harness(async () => { ++calls; return pending.promise; });
  const first = h.submit();
  assert.equal(h.state.loading, true); assert.equal(h.state.phase, 'requesting');
  await h.submit(); assert.equal(calls, 1);
  pending.resolve({ data: response(h.state.input), error: null }); await first;
  assert.equal(h.state.loading, false);
});

test('failed update keeps entered text, exposes error, never marks stale result successful, and retry succeeds', async () => {
  let fail = true;
  const h = harness(async payload => fail ? { data: null, error: 'Service unavailable' } : { data: response(payload.situation), error: null });
  await h.submit();
  assert.equal(h.state.phase, 'error'); assert.match(h.state.error, /Service unavailable/);
  assert.equal(h.state.input, 'Updated incident details'); assert.equal(h.state.results[0].id, 'old');
  assert.equal(h.state.loading, false); assert.deepEqual(h.state.navigations, []);
  fail = false; await h.submit();
  assert.equal(h.state.phase, 'complete'); assert.equal(h.state.results[0].id, 'new');
});

test('wrong-policy or stale-scenario response cannot become a successful analysis', async () => {
  for (const data of [{ ...response('Updated incident details'), policy_id: 'foreign' }, response('Previous scenario'), { ...response('Updated incident details'), explanation: null }]) {
    const h = harness(async () => ({ data, error: null })); await h.submit();
    assert.equal(h.state.phase, 'error'); assert.equal(h.state.results[0].id, 'old');
    assert.deepEqual(h.state.navigations, []);
  }
});

test('an older slow request cannot overwrite a newer successful update', async () => {
  const pending = deferred(); let calls = 0;
  const h = harness(async payload => ++calls === 1 ? pending.promise : { data: response(payload.situation, 'latest'), error: null });
  const first = h.submit(); h.requests.current.invalidate(); h.state.input = 'Newer incident details';
  await h.submit();
  pending.resolve({ data: response('Updated incident details', 'late'), error: null }); await first;
  assert.equal(h.state.focused, 'latest'); assert.equal(h.state.results[0].situation, 'Newer incident details');
});

test('unmount invalidates commits and navigation', async () => {
  const pending = deferred(); const h = harness(() => pending.promise); const first = h.submit();
  h.mounted.current = false; h.requests.current.invalidate();
  pending.resolve({ data: response(h.state.input), error: null }); await first;
  assert.equal(h.state.results[0].id, 'old'); assert.deepEqual(h.state.navigations, []);
});

test('both fresh and persisted analysis receipts never arm automatic guidance navigation', () => {
  for (const state of [{ analysisReady: true, analysisId: 'new', analysisAdvancePending: 'new' },
    JSON.parse(JSON.stringify({ analysisReady: true, analysisId: 'saved', analysisAdvancePending: 'saved' }))]) {
    assert.equal(autoAdvanceDelay('analysis', state), null);
  }
  assert.equal(autoAdvanceDelay('policy', { policyId: 'owned', policyReady: true }), 700);
});

test('page keeps a same-page result, hides stale output on failure, and preserves explicit manual guidance', () => {
  assert.ok(page.includes('<AnalysisProgress phase={analysisPhase}'));
  assert.ok(page.includes("analysisPhase !== 'error'"));
  assert.ok(page.includes("hidden={isEvaluating || (analysisPhase === 'error' && !currentAnalysis)}"));
  assert.ok(!page.includes('<AutoAdvance '));
  const action = find(n => ts.isCallExpression(n) && n.expression.getText(ast) === 'useWizardAction').getText(ast);
  assert.match(action, /autoAdvanceReady: false/);
  assert.match(action, /router.push\(wizardHref\('guidance'/);
  assert.ok(!handlerSource.includes('router.'));
});

test('the existing manual Continue action still opens guidance for the reviewed analysis', () => {
  const call = find(n => ts.isCallExpression(n) && n.expression.getText(ast) === 'useWizardAction');
  const navigations = [];
  const action = compile('return (' + call.arguments[0].getText(ast) + ');', {
    analysisPhase: 'complete', reviewedAnalysis: response('Updated incident details'),
    isLoadingPolicies: false, isLoadingReport: false, selectedPolicyId: 'owned', customNeedText: 'Updated incident details', isEvaluating: false,
    remember() {}, router: { push: href => navigations.push(href) },
    wizardHref: (step, refs) => `/claims/new?step=${step}&analysis_id=${refs.analysisId}`,
  });
  assert.deepEqual(navigations, []);
  action.onClick();
  assert.deepEqual(navigations, ['/claims/new?step=guidance&analysis_id=new']);
});


test('multiline incidents and vehicle scenarios are submitted intact, without fixed substitute needs', async () => {
  for (const input of ['First incident fact\nSecond supporting fact', 'Vehicle collision repair and towing after a car accident in a workshop']) {
    const calls = [];
    const h = harness(async payload => { calls.push(payload); return { data: response(payload.situation), error: null }; }, input);
    await h.submit();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].situation, input);
    assert.equal(h.state.results[0].situation, input);
    assert.equal(h.state.phase, 'complete');
    assert.deepEqual(h.state.navigations, []);
  }
});
