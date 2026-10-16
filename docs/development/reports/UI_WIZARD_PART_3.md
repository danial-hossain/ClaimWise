# Claim wizard behavior — Part 3

Implemented in the existing Next.js wizard and reused route screens. Backend code, API payloads, retrieval, citation validation, coverage decisions, and calculations were not changed.

## Plan and implementation

1. Inspect the four existing screens, owner-scoped scenario persistence, Motion transitions, coverage request, and sandbox endpoint.
2. Add readiness gates and cancellable 700ms/900ms timers. Keep Guidance and draft manual.
3. Present real request milestones and evidence, then require a native confirmation dialog for eligible sandbox submission.
4. Verify against the running local frontend/backend and capture the available states without fabricating analysis or claim records.

### Behavior

- **Policy:** the actual loaded policy must have successful extraction, readable text, and clauses. Readiness produces a drawn check and small scale transition, then navigates after 700ms. Persisted acknowledgement prevents a Back visit from immediately advancing again. Upload's old simulated percentage timer was removed; the UI now waits honestly for the real extraction response.
- **Analysis:** request start, response success, and returned saved analysis are the observable milestones. There are no invented retrieval stages or percentages. The server exposes one non-streaming request, not separate reading/retrieval/conditions events. Skeleton and result share a 360px preview area; the result fades in. Only complete success creates an auto-advance receipt; failures and partial failures stay on this step with Retry. Success schedules Guidance after 900ms. A restored record must be reloaded before its pending transition can run. Manual navigation acknowledges completion, and an outgoing request cannot redirect the user after Back.
- **Guidance:** no timer. The existing backend analysis supplies status, explanation, clauses, conditions, cost sharing, and insurer questions. The summary uses expanded CitationChips with unchanged clause IDs, page numbers, and quotes. Document/deadline/obstacle information uses existing incident guidance when available; absent information is explicitly **Not specified**. The user continues manually. Missing analysis has a useful empty state. Chat scrolling is contained within its canvas, so it no longer moves the whole page away from findings.
- **Draft:** existing editable intake, statement editor, document management, checklist, and evidence remain. Review and submit saves a new internal draft, then opens **Sandbox submission**. Existing saved drafts open the same review dialog. Only its explicit enabled confirmation invokes the existing sandbox API. Eligibility and unsaved edits are checked again in the handler. Auth headers now accompany that existing frontend API call. Success displays the real claim ID and backend outcome, labels it simulation, and links to My claims. Nothing is automatically submitted.
- A small dismissible first-run hint persists its dismissal. Step checks draw, the active ring pulses once, Guidance sections reveal 50ms apart, buttons press to .98, summary cards lift 2px, dialogs fade/scale over a static blurred backdrop, and the success notice enters by 8px. Reduced motion suppresses decorative movement and shimmer while retaining the auto-advance delays. No number interpolation or fabricated amounts were added.

## Files changed in Part 3

| File | Purpose |
| --- | --- |
| `frontend/src/lib/wizard-behavior.ts` | Pure auto-advance and existing sandbox status gates |
| `frontend/src/components/features/wizard/AutoAdvanceNotice.tsx` | Cancellable delays, success feedback, persisted hint |
| `frontend/src/components/features/wizard/AnalysisProgress.tsx` | Real request milestones and stable skeleton/result preview |
| `frontend/src/components/features/wizard/GuidanceSummary.tsx` | Evidence-based Guidance sections and honest missing states |
| `frontend/src/components/features/wizard/WizardFlow.tsx` | Connect readiness and manual completion to existing step panels |
| `frontend/src/components/features/wizard/WizardAction.tsx` | Publish screen readiness to the wizard |
| `frontend/src/components/features/wizard/Stepper.tsx` | Animated completion check |
| `frontend/src/components/ui/ConfirmDialog.tsx` | Native modal focus containment, Escape, eligibility, reduced motion |
| `frontend/src/context/ScenarioContext.tsx` | Persist transition receipts; preserve policy acknowledgement across analysis changes |
| `frontend/src/app/policies/page.tsx` | Validate loaded selection, expose readiness, remove simulated upload percentages |
| `frontend/src/app/coverage/page.tsx` | Request states, Retry, success receipt, URL update, stale-navigation guard |
| `frontend/src/app/workspace/page.tsx` | Structured Guidance, missing-analysis state, contained chat scrolling |
| `frontend/src/app/claims/page.tsx` | Explicit sandbox review, eligibility, real success display, save/navigation guards |
| `frontend/src/app/wizard.css` | Purposeful animation and reduced-motion rules |
| `frontend/src/lib/api.ts` | Existing authentication headers on sandbox POST; payload unchanged |
| `frontend/package.json` | Include behavior tests and current browser verifier |
| `frontend/tests/unit/wizard-behavior.test.mjs` | Seven additional gate/state regression tests |
| `frontend/tests/browser/verify-wizard-behavior.mjs` | Real local browser checks, screenshots, CDP screen recording frames |
| `docs/development/reports/UI_WIZARD_PART_3.md`, `docs/screenshots/wizard-part3-*` | Report, actual output, screenshots and recording |

## Actual validation

Commands ran from `frontend`:

```text
node --experimental-strip-types --test tests/unit/wizard.test.mjs tests/unit/wizard-behavior.test.mjs
# tests 12
# pass 12
# fail 0

npx tsc --noEmit
exit 0

npx eslint src/components/wizard src/components/ui/ConfirmDialog.tsx src/app/policies/page.tsx src/app/coverage/page.tsx src/app/workspace/page.tsx src/app/claims/page.tsx src/lib/wizard-behavior.ts src/context/ScenarioContext.tsx tests/browser/verify-wizard-behavior.mjs tests/unit/wizard-behavior.test.mjs
exit 0

node tests/browser/verify-wizard-behavior.mjs
16 checks passed; runtimeExceptions: []; passed: true
```

[Complete unit test output](../../screenshots/wizard-part3-unit-tests.txt) · [Complete browser output](../../screenshots/wizard-part3-verification.json).

The live browser checks cover locked future steps, visible policy success, policy auto-advance, no advance on a real failed analysis request, Back after auto-advance, policy/scenario and draft restoration after refresh, no Guidance timer, native modal focus, disabled ineligible confirmation, Escape returning to the draft, zero unconfirmed sandbox requests, mobile width, hint dismissal, reduced-motion styling, and retention of the reduced-motion auto-advance delay. Unit tests also cover successful analysis receipts, failure/partial-failure gates, repeat prevention after refresh/Back, and backend sandbox status eligibility.

## Captures

These are actual local browser captures. The selected policy was returned by the existing development database; the incident text is the user's example, entered as unsent input. No analysis response, citation, claim ID, document, or sandbox outcome was seeded or mocked.

- [Policy](../../screenshots/wizard-part3-1-policy.png)
- [Analysis input](../../screenshots/wizard-part3-2-analysis.png) and [real failure / Retry](../../screenshots/wizard-part3-2-analysis-error.png)
- [Guidance — analysis not available](../../screenshots/wizard-part3-3-guidance.png)
- [Claim draft](../../screenshots/wizard-part3-4-draft.png)
- [Sandbox confirmation — correctly blocked](../../screenshots/wizard-part3-5-confirmation.png)
- [Mobile draft](../../screenshots/wizard-part3-mobile.png)
- [Short screen recording](../../screenshots/wizard-part3-local-flow.mp4)

The recording shows the available signed-out local flow, including its real analysis failure and blocked confirmation. The later screens were inspected directly because analysis prerequisites could not be completed while signed out. **It is not a successful end-to-end submission recording.**

## Backend constraints and unverified paths

- No authenticated test session was supplied; the user chose to continue with available local data. Authenticated analysis success, actual evidence-filled Guidance, saving a new claim, eligible confirmation, and a successful sandbox response remain unverified in the browser. The 900ms success gate is unit-tested, not demonstrated with a real authenticated analysis.
- Existing sandbox POST accepts only `analyzed` or `sandbox_submitted` claims. Ordinary intake preparation produces other internal statuses. Coverage analysis is not claim adjudication. The UI blocks incompatible records instead of setting their status or inventing adjudication. Completing a new intake through sandbox success requires the existing adjudication path or a separate backend change, outside this UI-only task.
- Existing intake updates also move an `analyzed` claim back into a preparation status. The dialog therefore requires edits to be saved first and checks the server's current eligibility; it does not silently update an eligible claim immediately before submission.
- No live insurer submission integration was added. All sandbox outcomes are simulation only.
- Separate printed-page metadata is not exposed by the current citation model. Existing `page_number` values are displayed unchanged; no printed page labels were invented.
- The earlier cached-profile authentication issue remains outside this UI-only change: a cached frontend identity can outlive a failed backend token check. Server authorization remains authoritative.

## Reproducing browser verification

Use a **new isolated** headless Chrome profile with localhost debugging on port 9235, opening `http://localhost:3000/claims/new?step=policy`. Never attach the verifier to a normal user browser profile. The verifier clears only that isolated browser's guest scenario cache, reads available policies, and makes one genuine analysis request to exercise its error path. It does not submit a sandbox claim. Then run `npm run verify:wizard`.

The verifier writes real JPEG screencast frames and `frames.ffconcat` under `frontend/.next/wizard-part3-recording`. FFmpeg can encode those frames with their captured timestamps into the supplied MP4. No generated animation or synthetic walkthrough substitutes for the recorded application.
