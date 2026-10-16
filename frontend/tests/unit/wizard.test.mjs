import test from 'node:test';
import assert from 'node:assert/strict';
import { canVisitStep, completedSteps, wizardStep, wizardUrl } from '../../src/lib/wizard.ts';

test('future steps cannot be opened by the stepper in a new scenario', () => {
  assert.equal(canVisitStep('policy', {}), true);
  for (const step of ['analysis', 'guidance', 'draft']) assert.equal(canVisitStep(step, {}), false);
});
test('URL identifiers alone never mark a record as completed', () => {
  assert.deepEqual(completedSteps({ policyId: 'unverified', analysisId: 'unverified', claimId: 'unverified' }), { policy: false, analysis: false, guidance: false, draft: false });
});
test('previously reached steps survive a persistence round trip without unlocking others', () => {
  const state = JSON.parse(JSON.stringify({ visited: ['policy', 'analysis'] }));
  assert.equal(canVisitStep('analysis', state), true);
  assert.equal(canVisitStep('guidance', state), false);
  assert.equal(canVisitStep('draft', state), false);
});
test('step URLs encode IDs and carry the supported references', () => {
  const references = { policyId: 'id & /?', analysisId: 'analysis & /?', claimId: 'claim & /?' };
  const url = new URL(wizardUrl('draft', references), 'http://localhost');
  assert.equal(url.pathname, '/claims/new');
  assert.equal(url.searchParams.get('step'), 'draft');
  assert.equal(url.searchParams.get('policy_id'), references.policyId);
  assert.equal(url.searchParams.get('analysis_id'), references.analysisId);
  assert.equal(url.searchParams.get('claim_id'), references.claimId);
  assert.equal(new URL(wizardUrl('policy', references), 'http://localhost').searchParams.has('analysis_id'), false);
});
test('invalid or missing step parameters fall back to policy', () => {
  assert.equal(wizardStep('guidance'), 'guidance');
  assert.equal(wizardStep('submission'), 'policy');
  assert.equal(wizardStep(null), 'policy');
});
test('guided flow labels follow the primary navigation pages', async () => {
  const { WIZARD_STEPS } = await import('../../src/lib/wizard.ts');
  assert.deepEqual(WIZARD_STEPS.map(step => step.label), ['My policies', 'Coverage', 'Ask ClaimWise', 'My claims']);
  assert.deepEqual(WIZARD_STEPS.map(step => step.page), ['/policies', '/coverage', '/workspace', '/claims']);
});
