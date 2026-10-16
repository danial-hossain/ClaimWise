# Remaining screens — Part 4

Applied the existing teal/blue/white theme and glass primitives to the remaining screens. This is a frontend presentation change: backend code, API contracts, retrieval, evidence validation, status calculations, and submission rules were preserved.

## What changed

- **Overview:** actual account greeting, divider-separated portfolio figures, one Needs attention list, and simple quick-action links. Counts use existing policy/claim/checklist records; unavailable claims show a dash rather than a fabricated zero. Attention items come from unsuccessful extraction and incomplete saved checklist items, with actual linked clause references and quotes where present. No policy wording is reinterpreted into new coverage findings. The illustrated hero and existing scenario launcher remain. An account with no policies gets an upload prompt.
- **My policies:** reusable glass policy cards, visible drag-over treatment, shared skeletons and staggered card entrance. The clause count can animate once to the exact returned count after upload. Upload progress lists Uploading, Reading pages, Extracting clauses, and Indexing, using only the actual response. The endpoint is non-streaming: internal steps do **not** pretend to complete at timed intervals. Search and page filters operate on existing clauses without changing their IDs, wording, grouping, or citation logic. Filtering keeps the source groups stable and does not request fresh AI heading rewrites. The reader has a viewport-sized layout, one backdrop, keyboard focus containment, Escape, and focus restoration.
- **Coverage:** each returned need has its own opaque glass row with the existing StatusBadge, explanation, conditions, limits, and expanded CitationChips. Excluded has a muted red edge; Not specified stays slate gray. Insurer questions use an existing category or clause heading as their short need label, with a neutral numbered fallback. Full incident text remains visible separately. The input has an accessible live character counter and a friendlier explanation of what to enter. Existing validation and scenario decomposition were preserved.
- **Ask ClaimWise:** opaque glass chat canvas, policy selector and existing starter questions, expanded policy quotes, shared request skeletons, and a distinct slate AbstainNotice labelled “Not specified in your policy.” Answer generation and abstention decisions are unchanged.
- **My claims:** glass list and existing detail surfaces, readable status chips, shared loading skeletons, and clearer signed-out presentation. Internal and simulation status rules are unchanged. Claims unavailable because of authentication show unknown counts rather than zero.
- **Shared UI:** a small Motion module supplies timing tokens, the reduced-motion hook, StaggerGroup/Item, Skeleton, and CountUp. Existing wizard transition/dialog presentation uses the same tokens. A common evidence/approval disclaimer now renders through AppLayout on all pages. Small secondary text and focus rings were strengthened.
- **UI bug fixed:** the confirmation dialog previously created a client portal absent from the server HTML, causing hydration failure on a direct visit to My claims. Portal mounting now waits until hydration completes. Confirmation and submission behavior are unchanged.

## Changed files

| Files | Change |
| --- | --- |
| `frontend/src/app/dashboard/page.tsx` | Overview composition and presentation of existing records |
| `frontend/src/components/features/dashboard/AttentionList.tsx`, `SummaryStrip.tsx` | Glass attention list and divider-separated figures |
| `frontend/src/app/policies/page.tsx` | Glass upload/library, real response progress, reader filters and accessible modal |
| `frontend/src/components/ui/PolicyCard.tsx`, `PolicyUploadProgress.tsx` | Reusable cards, true count animation, progress presentation |
| `frontend/src/app/coverage/page.tsx`, `frontend/src/components/ui/CoverageNeedRow.tsx` | Separate need rows, evidence and per-need questions |
| `frontend/src/lib/coverage-presentation.ts` | Short labels from existing category/heading fields only |
| `frontend/src/app/workspace/page.tsx`, `frontend/src/components/ui/AbstainNotice.tsx` | Opaque chat, visible quotes, abstention styling |
| `frontend/src/app/claims/page.tsx` | Glass list/detail styling, skeletons and honest unavailable counts |
| `frontend/src/components/ui/Motion.tsx` | Shared motion, reduced-motion export, skeleton and count presentation |
| `frontend/src/components/features/wizard/StepTransition.tsx`, `AnalysisProgress.tsx` | Reuse shared presentation utilities; step behavior preserved |
| `frontend/src/components/ui/ConfirmDialog.tsx` | Hydration-safe portal and shared timing |
| `frontend/src/components/Footer.tsx`, `AppLayout.tsx` | Universal disclaimer |
| `frontend/src/app/surfaces.css`, `layout.tsx` | Shared glass/readability/responsive styles and stylesheet import |
| `frontend/tests/browser/verify-surfaces.mjs` | Existing-record browser checks and captures |
| `docs/development/reports/UI_SURFACES_PART_4.md`, `docs/screenshots/part4/*` | Change report, screenshots, actual verification output |

## Screenshots

These are actual browser captures using existing local records. There was no response interception, test-data upload, new claim, generated analysis, or insurer submission. The existing demo account supplies genuine empty states. Its name comes from the backend account response.

| Screen | Existing data / available context | Actual empty account | Mobile |
| --- | --- | --- | --- |
| Overview | [29 existing policies; claims unavailable](../../screenshots/part4/overview-existing.png) | [Empty portfolio](../../screenshots/part4/overview-demo.png) | [Mobile](../../screenshots/part4/overview-mobile.png) |
| My policies | [Existing policy library](../../screenshots/part4/policies-existing.png) | [Empty library](../../screenshots/part4/policies-demo.png) | [Mobile](../../screenshots/part4/policies-mobile.png) |
| Coverage | [Existing policy context; no accessible saved analysis](../../screenshots/part4/coverage-existing.png) | [No policies or findings](../../screenshots/part4/coverage-demo.png) | [Mobile](../../screenshots/part4/coverage-mobile.png) |
| Ask ClaimWise | [Policy selector/context; no saved answers](../../screenshots/part4/ask-existing.png) | [No-policy starter state](../../screenshots/part4/ask-demo.png) | [Mobile](../../screenshots/part4/ask-mobile.png) |
| My claims | [Signed-out access notice](../../screenshots/part4/claims-existing.png) | [Authenticated empty claims](../../screenshots/part4/claims-demo.png) | [Mobile](../../screenshots/part4/claims-mobile.png) |

Clause viewer: [desktop](../../screenshots/part4/policies-clause-viewer.png) · [mobile with real page filter](../../screenshots/part4/policies-clause-viewer-mobile.png).

The policy-library capture includes the first 2,100px because the existing database returns 29 policies. All other captures include their complete screen/page as recorded in the verification manifest.

## Validation

[Actual browser output](../../screenshots/part4/verification.json) · [Existing wizard regression output](../../screenshots/part4/wizard-regression.txt).

The browser verifier checks all five screens at 1440px and 390px, footer presence, actual-account greeting, empty upload prompt, character counter, labelled input, drag-over state, clause search, page filter, unchanged AI heading request count during filtering, modal keyboard containment, Escape, mobile reader bounds, visible keyboard focus, status contrast, and absence of new business-record requests. Captures use an isolated headless Chrome profile and the real running local API.

The four status text/background token pairs measure **6.78:1 Covered, 5.87:1 Conditional, 6.04:1 Excluded, and 6.92:1 Not specified**; each exceeds WCAG AA for normal text. This is a measured token check, not a claim of a full accessibility audit. Reduced-motion captures use the browser's actual reduced-motion preference. Reader areas and skeletons reserve space, and only opacity/transform are used for new entrance motion; no whole-site CLS performance audit was performed.

Targeted TypeScript and ESLint checks were run against the changed frontend code. The existing wizard gate/state regression suite was also run; its full TAP output is linked above.

## Unverified / existing constraints

- The user requested **only existing records**. The available preconfigured demo account has zero policies and zero claims. The development policy context exposes 29 existing policies, but protected saved-analysis and claim requests return 401 when signed out. These are recorded as expected API access failures, separately from application console errors and runtime exceptions.
- A fully populated Coverage-results screenshot, chat-answer/abstention screenshot, attention row with a real pending claim checklist, and populated claim-detail screenshot could not be produced from accessible existing records. The corresponding presentation was implemented and type-checked; these states were not fabricated or represented as verified captures.
- Upload completion, count-up, and new-card entrance were not exercised because that would require a new upload. Their UI is connected to the existing upload response; there are no fake progress percentages or timed internal stages.
- No independent live reading/extraction/indexing events are exposed by the existing upload endpoint. Confirmed stages can check off together when the final response arrives. No backend or event API was added.
- Existing citation `page_number` values are preserved. Separate printed-page labels are not exposed by the current model.
- No insurer integration was added, and no claim was submitted.

To reproduce, launch a fresh isolated localhost Chrome profile with debugging on port 9235, open the frontend, and run `node tests/browser/verify-surfaces.mjs` from `frontend`. The verifier uses existing policy records and the supported demo login only. It does not upload, run coverage analysis, create a claim, or call sandbox submission.
