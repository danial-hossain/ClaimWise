import test from 'node:test';
import assert from 'node:assert/strict';
import { autoAdvanceDelay, sandboxEligibility } from '../../src/lib/wizard-behavior.ts';

test('only a validated policy schedules the 700ms advance', () => {
  assert.equal(autoAdvanceDelay('policy', {}), null);
  assert.equal(autoAdvanceDelay('policy', { policyId: 'selected', policyReady: false }), null);
  assert.equal(autoAdvanceDelay('policy', { policyId: 'selected', policyReady: true }), 700);
});
test('returning to a completed policy does not schedule another advance', () => {
  assert.equal(autoAdvanceDelay('policy', { policyId: 'selected', policyReady: true, policyAdvancedId: 'selected' }), null);
});
test('successful analyses remain available for manual review, including old pending receipts', () => {
  assert.equal(autoAdvanceDelay('analysis', { analysisId: 'saved', analysisReady: true }), null);
  assert.equal(autoAdvanceDelay('analysis', { analysisId: 'saved', analysisReady: true, analysisAdvancePending: 'other' }), null);
  assert.equal(autoAdvanceDelay('analysis', { analysisId: 'saved', analysisReady: true, analysisAdvancePending: 'saved' }), null);
});
test('failed requests and partial failures have no completion receipt and never advance', () => {
  assert.equal(autoAdvanceDelay('analysis', { analysisReady: false }), null);
  assert.equal(autoAdvanceDelay('analysis', { analysisId: 'partial-success', analysisReady: true, analysisAdvancePending: undefined }), null);
});
test('Guidance and draft never auto-advance, including fully complete persisted state', () => {
  const state = JSON.parse(JSON.stringify({ policyId: 'selected', policyReady: true, analysisId: 'saved', analysisReady: true, analysisAdvancePending: 'saved' }));
  assert.equal(autoAdvanceDelay('guidance', state), null);
  assert.equal(autoAdvanceDelay('draft', state), null);
});
test('Back and refresh after analysis auto-advance do not schedule a repeat', () => {
  const state = JSON.parse(JSON.stringify({ analysisId: 'saved', analysisReady: true, analysisAdvancedId: 'saved', analysisAdvancePending: 'saved' }));
  assert.equal(autoAdvanceDelay('analysis', state), null);
});
test('sandbox eligibility mirrors the existing backend rather than internal readiness', () => {
  for (const status of [undefined, 'draft', 'preparing_documents', 'ready_to_submit', 'approved']) assert.equal(sandboxEligibility(status), false);
  assert.equal(sandboxEligibility('analyzed'), true);
  assert.equal(sandboxEligibility('sandbox_submitted'), true);
});
