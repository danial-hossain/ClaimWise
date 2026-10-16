# Claim preparation wizard — Part 2

The existing Policy, Coverage, Ask ClaimWise, and My Claims screens are reused inside a dedicated wizard. The independent navigation pages remain available. This is a frontend change: backend logic, API contracts, evidence validation, calculations, database schemas, and insurer integrations are unchanged.

## Plan and implementation

1. Reuse the current screen components and APIs behind a stable wizard route.
2. Add a sticky glass stepper, shared glass panels and footers, and directional transitions.
3. Restore user input from the existing browser persistence pattern and reload saved results from existing backend records.
4. Verify history, refresh, locked future steps, keyboard controls, reduced motion, and responsive layout; capture each step without fabricated results.

| Step | URL state | Existing screen reused |
| --- | --- | --- |
| Policy | `/claims/new?step=policy` | `src/app/policies/page.tsx` |
| Analysis | `/claims/new?step=analysis` | `src/app/coverage/page.tsx` |
| Guidance | `/claims/new?step=guidance` | `src/app/workspace/page.tsx` |
| Claim draft | `/claims/new?step=draft` | `src/app/claims/page.tsx` |

The URLs carry `policy_id`, `analysis_id`, and `claim_id` where relevant. Each manual navigation pushes a real history entry. Footer Back always opens the preceding step, including direct-entry sessions; browser Back follows normal history. My Claims' Create a claim action starts a new wizard. Continue preparation and Overview resume the last visited step. Overview can begin at Analysis when the user has already selected a policy and described an incident; analysis runs only after the explicit Analyze scenario action.

## Components

- `components/features/wizard/Stepper.tsx`: sticky `GlassBar` under the existing top bar. The top bar's measured height sets the sticky offset. Completed steps display checks; the active step is teal; unreached steps are disabled native buttons without links. Previously reached steps remain navigable. Lines fill with a 400ms `scaleX` transition. Mobile shows the step counter and progress track. Scenario title and New scenario remain visible.
- `components/features/wizard/StepTransition.tsx`: one keyed motion panel within `AnimatePresence mode="wait"`. Forward exits left and enters from the right; backward reverses it. Distance 12px, duration 350ms, ease `[0.22, 1, 0.36, 1]`. Only opacity and transform animate. Reduced motion uses a short opacity transition without displacement. Top bar and stepper remain mounted. This follows the [Motion AnimatePresence documentation](https://motion.dev/docs/react-animate-presence).
- `components/features/wizard/WizardFlow.tsx`: reuses the existing route screens through dynamic imports. A `GlassPanel` supplies a concise heading, description, content, Back, and one dark teal primary footer action. Waiting for state restoration before mounting a screen prevents refresh races.
- `components/features/wizard/WizardAction.tsx`: connects each existing screen's action to the footer. Analysis and claim intake retain their original form handlers and native validation through `form` attributes; no duplicate API implementation was introduced.
- `lib/wizard.ts`: step definitions, encoded URLs, completion flags, and navigation eligibility. An arbitrary record ID in a URL is insufficient to display completion. Flags are set after existing API results or a validated readable policy are available. Direct URLs may show empty steps; they do not fabricate earlier completion or enable a claim outcome.

Step changes have polite live announcements and `aria-current="step"`. Navigation remains keyboard accessible. Focus can move to the new heading after entry, and sticky-header scroll margins keep focused controls visible. Clause ID, page, and quote remain available; wizard citations begin expanded, and the policy reader now includes the exact clause ID alongside the page. Not specified remains a separate honest state.

## Persistence and manual progression

`ScenarioContext` retains the existing `claimwise_journey:<owner>` key pattern. Signed-in users use local storage scoped to the supplied account ID; anonymous preparation uses session storage scoped to the current tab. It stores selected policy, incident text, last/reached steps, pending question, unsaved claim fields/checklist/guidance, and pending edits to a saved draft. Immediate writes protect the last keystroke before refresh or Back. Failed browser storage writes do not alter durable server records.

Saved analysis IDs and claim IDs continue to refer to actual database records. Linked conversation history is loaded from the existing analysis endpoint. Unlinked policy Q&A in the wizard checkpoints the actual conversation in the same account-scoped browser store. A new incident does not automatically attach another historical analysis for the same policy. Changing policy invalidates downstream preparation context.

New scenario resets the draft and visited/completed flags, returns to Policy, and remounts the step content so pending form/file selections do not leak into a new run. Reset is coordinated with the URL change to prevent the outgoing screen from being re-added as visited. Existing policy/analysis/claim database records are preserved.

There is no automatic step advancement in this part. The compatibility component named `AutoAdvance` now renders only a manual Continue notice outside the wizard and is suppressed inside it. Its countdown/navigation timers were removed. Saving a claim opens that saved record's review state within the same Claim draft step; it does not submit to an insurer.

## Validation and screenshots

Run `npm run test:wizard` from `frontend` for the five navigation-model tests. Node 22 emits its standard experimental type-stripping warning. `npm run verify:wizard` runs the UI smoke test against a fresh isolated headless Chrome instance on localhost port 9235. It requires an existing readable policy from the configured development backend; it does not seed policy/claim records, mock evidence, generate an analysis, send a question, or save/submit a claim.

To launch the isolated preview in PowerShell from `frontend` while `npm run dev` is running:

```powershell
$wizardProfile = Join-Path (Get-Location) '.next/wizard-verification-profile'
Start-Process -FilePath 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList '--headless=new','--disable-extensions','--no-first-run','--no-default-browser-check','--disable-sync','--remote-debugging-port=9235','--remote-debugging-address=127.0.0.1',("--user-data-dir=" + $wizardProfile),'http://localhost:3000/claims/new?step=policy' -WindowStyle Hidden
npm run verify:wizard
```

The test closes its isolated browser. It records results in `docs/screenshots/wizard-verification.json` and captures:

- `wizard-1-policy.png`
- `wizard-2-analysis.png`
- `wizard-3-guidance.png`
- `wizard-4-draft.png`
- `wizard-mobile.png`

Checks include future-step locks, native form association/validation, footer Back, browser Back, selected policy and incident persistence, pending question/draft restoration, resume from My Claims, both transition directions with only one panel present, unchanged top bar/stepper elements, no horizontal overflow, mobile collapse/stickiness, reduced motion, New scenario reset, and runtime exceptions. TypeScript and targeted ESLint checks also pass.

## Issues found and limits

Fixed UI/state issues: refresh previously mounted screens before restoring draft state; URL references could suppress saved state restoration; New scenario could record the outgoing step as visited; historical analyses could be attached to a new wizard incident; an unknown/unavailable policy could retain a cached ready flag. Untouched reader memoization/lifecycle code also had lint errors; those were corrected without changing evidence or API payloads.

The screenshots and browser checks use an isolated signed-out session and existing development policy records. The incident input uses the example supplied in the brief; it is never submitted. Guidance and Claim draft show real empty/authorization states. Authenticated saved-analysis/conversation restoration, AI responses, and successful claim saving were not exercised in this session. Their existing API paths remain in use. Native file inputs require reselecting a file if refreshed before upload; already uploaded policies/documents remain backed by the existing persistence.

The existing cached-profile/token-verification issue described in Part 1 remains outside this UI-only change. The package install reported five high-severity audit findings; dependency security remediation was not included in this UI task. The only added runtime dependency is `motion`; no backend configuration or migration was introduced.

Changed source areas: the new wizard route, wizard components, `lib/wizard.ts`, `app/wizard.css`, `ScenarioContext`, `AppLayout`, top-bar height measurement, Overview scenario entry, and presentation/state bridges in the four existing screens. Shared `AnalysisContext`, `CitationChip`, and the former automatic-handoff presentation were adjusted for the wizard. Package manifests, test scripts, screenshots, and this report are included.
