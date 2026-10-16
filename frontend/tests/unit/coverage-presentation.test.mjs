import test from 'node:test';
import assert from 'node:assert/strict';
import { coverageOutcomeCounts } from '../../src/lib/coverage-presentation.ts';

test('coverage summary counts scenarios by covered, partial, excluded, and uncertain outcomes', () => {
  const scenarios = [
    { verdict: 'covered' },
    { verdict: 'uncertain', overall_assessment: 'potentially_covered' },
    { verdict: 'partially_covered' },
    { verdict: 'conditional', overall_assessment: 'conditional_or_limited' },
    { verdict: 'excluded' },
    { verdict: 'uncertain' },
  ];

  assert.deepEqual(coverageOutcomeCounts(scenarios), {
    total: 6,
    covered: 2,
    partiallyCovered: 2,
    notCovered: 1,
    uncertain: 1,
  });
});

test('coverage summary prefers the displayed assessment when it differs from the verdict', () => {
  const scenarios = [
    { verdict: 'covered', overall_assessment: 'potentially_excluded' },
    { verdict: 'excluded', overall_assessment: 'partially_covered' },
    { verdict: 'uncertain', overall_assessment: 'insufficient_evidence' },
  ];

  assert.deepEqual(coverageOutcomeCounts(scenarios), {
    total: 3,
    covered: 0,
    partiallyCovered: 1,
    notCovered: 1,
    uncertain: 1,
  });
});

test('coverage summary derives an outcome from insured-loss findings when the overall result is uncertain', () => {
  const scenarios = [
    {
      verdict: 'uncertain',
      overall_assessment: 'insufficient_evidence',
      components: [{ verdict: 'covered' }],
    },
    {
      verdict: 'uncertain',
      overall_assessment: 'insufficient_evidence',
      components: [{ verdict: 'covered' }, { verdict: 'excluded' }],
    },
  ];

  assert.deepEqual(coverageOutcomeCounts(scenarios), {
    total: 2,
    covered: 1,
    partiallyCovered: 1,
    notCovered: 0,
    uncertain: 0,
  });
});

test('empty scenario results produce zero for each summary count', () => {
  assert.deepEqual(coverageOutcomeCounts([]), {
    total: 0,
    covered: 0,
    partiallyCovered: 0,
    notCovered: 0,
    uncertain: 0,
  });
});
