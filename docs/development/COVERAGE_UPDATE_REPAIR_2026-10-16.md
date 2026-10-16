# Coverage scenario update workflow repair - 2026-10-16

## Root cause

`frontend/src/app/coverage/page.tsx` had two success-triggered navigation paths:

1. `handleEvaluateSituation` created a six-second `handoff` to `analysisLink('workspace', analysis.id)`. Rendering `AutoAdvance` scheduled navigation to Ask ClaimWise on the standalone coverage route.
2. In the claim wizard, the handler saved `analysisAdvancePending` and enabled `useWizardAction.autoAdvanceReady`. `WizardFlow.StepPanel` passed that flag to `AutoAdvanceNotice`, whose `autoAdvanceDelay('analysis', scenario)` scheduled navigation to Guidance after 900 ms. Old persisted pending receipts could also rearm that behavior.

The handler also cleared the input after success, replaced the wizard URL, and overwrote the returned situation with the submitted need rather than validating their association. Only a mount/path check protected async results, so a changed policy could still receive a late response from an earlier request.

## Implemented behavior

- Scenario submission invokes the existing `analyzeCoverageScenario` adapter, which posts to `/api/v1/coverage/analyze`; no second analysis API or coverage engine was created.
- The page no longer creates a timed handoff, arms analysis auto-advance or changes routes after success. `autoAdvanceDelay` always returns `null` for Analysis, including old pending receipts. Existing Policy auto-advance remains unchanged.
- The wizard's Continue to Guidance action remains an explicit user click. Authentication, authorization and route-guard code were not changed.
- Request generations prevent duplicate same-request submissions and reject late commits after policy changes or unmount. Policy-report loads also check their scope before committing results.
- The response must identify the requested policy and scenario and contain a valid result ID, verdict, explanation and citation/question containers. Citation policy, page and verification metadata are checked before it becomes a successful page update. Incorrect or stale response content produces a retryable error rather than being relabeled as the new scenario.
- On success, the returned analysis ID becomes the focused result. Both standalone and wizard screens render `AnalysisProgress`, `AnalysisContext` and the separate `GuidanceSummary` on the current page. The actual response supplies interpretation, conditions/limits, source quotations/pages, uncertainty and supported actions.
- Entered scenario text remains available after success and failure. The last successful submission is associated with its original input, including multi-need inputs, so manual continuation does not require clearing the form.
- During loading, the previous analysis is not shown as the pending result. On a wholly failed update, no earlier result is presented as its replacement. A partial batch displays its newly returned findings alongside failed-item details and keeps the original multi-need input for retry.
- Errors leave the form usable and provide Retry analysis. Success is not marked until the real response has passed validation.

## Files changed

| File | Change |
|---|---|
| `frontend/src/app/coverage/page.tsx` | Remove handoffs and success navigation; focus validated results; keep input; guard asynchronous commits; render same-page interpretation/guidance and retry/partial states |
| `frontend/src/lib/coverageUpdate.ts` | Shared batch submission, response association/validation, request generation and duplicate-request gate |
| `frontend/src/lib/wizard-behavior.ts` | Disable automatic progression from Analysis only |
| `frontend/src/components/features/wizard/AutoAdvanceNotice.tsx` | Correct first-run text so it explains manual review/continuation |
| `frontend/tests/unit/coverage-update.test.mjs` | Ten regression cases executing the real page submission handler/manual callback and production parser/request helpers with controlled API/React-setter boundaries |
| `frontend/tests/unit/wizard-behavior.test.mjs` | Replace the obsolete 900 ms analysis-auto-advance expectation with the explicitly requested manual-review behavior; policy timing and eligibility assertions remain |

No backend source, retrieval logic, insurance rules, source documents, environment files or working database were changed in this pass. Existing unrelated uncommitted changes were preserved.

## Actual verification

| Directory | Command | Result |
|---|---|---|
| `frontend` | `node --experimental-strip-types --test tests/unit/coverage-update.test.mjs tests/unit/wizard-behavior.test.mjs` | Initial focused run: 15 passed, exit 0; further partial-batch/manual-navigation regressions added afterward |
| `frontend` | `node --experimental-strip-types --test tests/unit/*.test.js tests/unit/*.test.mjs` | Final: **37 passed, 0 failed**, exit 0 |
| `frontend` | `node node_modules/eslint/bin/eslint.js . --format json` | **0 errors, 15 warnings**, exit 0; final new manual-callback test also passed its targeted lint check |
| `frontend` | `node node_modules/typescript/bin/tsc --noEmit --incremental false` | Exit 0 |
| `frontend` | `node node_modules/next/dist/bin/next build` | Exit 0, all 14 routes generated |
| `backend` | `.\venv\Scripts\python.exe -m pytest tests/test_production_security.py tests/test_coverage_gap.py tests/test_source_integrity.py -m 'not database' -q --tb=short -p no:cacheprovider` | **148 passed, 4 deselected, 20 warnings**, 30.95 seconds, exit 0 |
| root | `git diff --check` | Existing unrelated whitespace findings remain in `backend/app/api/router.py` and `backend/tests/test_comparison.py`; left untouched |

The handler tests execute the actual TypeScript AST-extracted submission function, rather than a duplicate test implementation. They verify updated payloads, successful returned findings/citations, no submission navigation, immediate loading and duplicate prevention, input preservation, failure/retry, mismatched responses, older/slower requests, unmount, pending receipt behavior, partial batches and the actual manual Continue callback. Existing frontend component-render tests verify interpretation/citation and guidance field rendering. Existing backend security regressions verify private access/ownership and cookie/CSRF behavior through isolated persistence boundaries.

The redirect was diagnosed directly from the concrete timer paths before editing. A failing pre-edit test run was not recorded; no such run is claimed. Final tests demonstrate that the submission handler stays on the current route, focuses the returned analysis, and does not arm either redirect mechanism.

Evidence logs are ignored machine-local files under `temp/backend-test-repair/coverage-update-*`. Build/test worker and pytest temporary-directory access used approved tool execution.

## Remaining limits

- No live authenticated browser journey or live paid-model request was executed. Handler, rendering, build and isolated endpoint verification do not establish end-to-end behavior through a deployed proxy/database.
- Four PostgreSQL integrations in the focused selection remain excluded because a verified disposable database is unavailable. No development or production database was used for tests.
- Existing persisted analyses and insurance decisions were not rewritten. This repair changes scenario submission, presentation and navigation behavior only; it introduces no hardcoded policy answers.
