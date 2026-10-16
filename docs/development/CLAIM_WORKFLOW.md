# Coverage, questions, and claim preparation

Routes remain `/coverage`, `/workspace` (Ask ClaimWise), and `/claims`.

Incident evaluations from `POST /api/v1/coverage/analyze` are saved in PostgreSQL. `GET /coverage/analyses?policy_id=...` restores saved results; `GET /coverage/analyses/{id}` restores one result and its conversation. Links carry an analysis ID rather than trusting browser-provided coverage findings. `POST /coverage/analyses/{id}/ask` retrieves the owned analysis and previous messages, calls the existing grounded Q&A pipeline, and appends the real answer and verified citations. Analysis citations are checked against the selected uploaded policy before persistence.

Prepare a Claim opens the existing intake form with the incident and policy already populated, and displays the source analysis for review. Saving resolves `analysis_id` server-side, checks ownership and matching policy, and stores a snapshot inside the existing claim JSON. Incident date, location, and loss are supplied by the member rather than inferred. Returning through the same analysis link opens an existing linked claim. My Claims retains document upload/download, adds removal, applies generated guidance to the saved checklist, and provides generation, editing, and saving of an assisted description. Generating a description never overwrites saved incident facts. Review the description before using it.

Claims and analysis records require a Bearer token in all environments. The existing required-auth dependency now rejects missing headers even in development. All claim reads and changes enforce ownership. Claim writes propagate database errors instead of reporting memory-only success. Uploaded evidence and analysis conversations can contain sensitive information and use the existing database access controls.

## Configuration and deployment

- Use the existing backend `DATABASE_URL` and authentication signing/token configuration. No new secret or provider is introduced.
- Apply `backend/app/db/migrations/005_coverage_workflow.sql`, or allow the existing database role to create the table/index lazily on first workflow access. Claims continue to use the existing JSONB data column, so added claim fields require no ALTER TABLE.
- Configure the existing Gemini credentials/model for generative assistance. Existing retrieval and honest evidence-unavailable/degraded responses remain in effect when AI or policy evidence is unavailable. No outcome or evidence is fabricated as a fallback.
- There is no live insurer integration. Preparation and local sandbox simulation are separate; this workflow never transmits to an insurer. A future live integration must provide explicit confirmation, a submission receipt, and authenticated insurer updates before showing submitted/approved statuses.
- Previously browser-only analyses remain a local cache; rerun them to create a durable backend analysis and enable contextual claim transfer.

## Verification

`backend/tests/test_claim_workflow.py` checks authentication, ownership, server-resolved transfer, policy mismatch rejection, typed checklist updates, and grounded follow-up history with external database/AI boundaries mocked. Run from the repository root with `backend/venv/Scripts/python.exe -m pytest backend/tests/test_claim_workflow.py -q`. Frontend checks: `tsc --noEmit` and ESLint on the touched UI modules. Live AI/database and browser journey checks require the configured services.

## Files changed for this integration

Existing files updated (preserving the pre-existing working-tree changes):

- `backend/app/api/v1/endpoints/coverage.py`: save/restore owned analyses, contextual follow-ups, citation checks, report access.
- `backend/app/api/v1/endpoints/claims.py`: authenticated intake and access, analysis linking, typed checklist updates, description generation, evidence removal.
- `backend/app/api/v1/endpoints/qa.py`: retain incident context in retrieval queries.
- `backend/app/core/security.py`: required authentication rejects absent tokens in development.
- `backend/app/db/claim_repo.py`: propagate failed claim persistence.
- `backend/app/schemas/claim.py`: validated analysis link, saved snapshot, editable description draft.
- `backend/app/services/qa_service.py`: abstain after exhausted citation verification retries.
- `frontend/src/app/coverage/page.tsx`: restore server records, analysis details, claim/chat actions, scenario prefill.
- `frontend/src/app/claims/page.tsx`: prefilled review, linked analysis, description editor, generated checklist persistence, evidence removal.
- `frontend/src/app/workspace/page.tsx`: restore conversation and claim context, contextual navigation, loading/error guards, safe message formatting.
- `frontend/src/lib/api.ts`: editable description payload.
- `frontend/src/types/api.ts`: workflow claim fields.

New files:

- `backend/app/db/workflow_repo.py`
- `backend/app/db/migrations/005_coverage_workflow.sql`
- `backend/tests/test_claim_workflow.py`
- `frontend/src/lib/claimWorkflow.ts`
- `frontend/src/components/ui/AnalysisContext.tsx`
- `docs/development/CLAIM_WORKFLOW.md`


## Connected scenario experience

The dashboard now starts a real incident evaluation using the existing coverage API, or opens policy Q&A with the entered question and selected policy. A shared journey across Policies, Coverage, Ask ClaimWise, and My Claims carries the active policy, analysis, and claim identifiers through navigation. Account-specific browser storage remembers the last journey; the analysis, conversation, and claim records remain in PostgreSQL. Start another scenario clears the navigation context without deleting saved records. Query changes remount the task view so moving to another analysis on the same page loads the correct evidence and conversation. Analysis details are collapsible, keeping the current task visible.

Additional frontend files: `src/context/ScenarioContext.tsx`, `src/components/features/dashboard/ScenarioLauncher.tsx`; updates in `AppLayout.tsx`, `Topbar.tsx`, dashboard, policies, coverage, workspace, claims, and `AnalysisContext.tsx`. No new backend service, AI provider, or configuration is required for these navigation improvements.


## Overview and automatic handoffs

Overview is now a focused incident launcher with portfolio totals and recent saved claim drafts. The page-directory cards and duplicated journey navigation have been removed. Task pages use a compact progress rail with a highlighted current step and saved-work indicators rather than another set of page cards.

Successful readable policy extraction advances to Coverage after four seconds; completed incident analysis advances to Ask ClaimWise after six seconds; a contextual follow-up answer advances to claim preparation after twelve seconds. The dashboard's completed analysis opens Coverage & Gap Analysis with its saved findings visible immediately below the header. The analysis ID and selected policy are retained. Opening this saved result does not trigger a redirect; users can review it and continue to Ask ClaimWise using the contextual action. These are local navigation actions only, never insurer submissions. Every timed handoff has Stay here and Continue now controls. Starting another task or typing another question cancels the pending handoff. Failed uploads, missing evidence extraction, partial analysis failures, and failed Q&A calls do not trigger navigation. Historical records never trigger handoffs simply because they were reopened. Saving a claim draft opens `/claims?claim_id=...&stage=review` only after the backend confirms a saved claim.

Files for this refinement: dashboard, ScenarioLauncher, ScenarioContext, AnalysisContext, AutoAdvance (new), policies, coverage, workspace, claims, and globals.css. No new service configuration is required.

## Coverage request reliability

Coverage analysis now saves validated results before supplemental audit logging. Audit failures are logged without preventing a member from opening an already-saved analysis; failed database persistence returns a retryable 503 instead of a false success. Workflow schema setup runs once per repository instance, with a local lock and PostgreSQL advisory lock protecting first-use initialization across workers. Unexpected errors are logged with a reference that is also displayed by the frontend, without returning stack traces or request bodies.

Verification: the exact `my luggage was stolen` incident was sent through the authenticated FastAPI route against stored AP travel-policy records; analysis creation and reopening each returned HTTP 200. The original screenshot's 500 was not reproduced during this check. Eleven workflow regression tests passed, including audit failure, database failure, schema-initialization concurrency/retry, and error-reference coverage. Frontend TypeScript and the touched API helpers' lint checks passed.


## Shared glass interface

The app uses `frontend/src/app/workspace.css` for common frosted surfaces, input states, buttons, typography, responsive navigation, dialog depth, and reduced-motion behavior. Existing neutral cards carry `cw-glass`; evidence/status colors and user-selected states remain distinct. Backdrop-filter fallbacks keep text readable on browsers without blur support, and nested panels avoid stacking expensive filters.

The main navbar contains Overview, My policies, Coverage, Ask ClaimWise, and My claims. Compare policies and Account settings live in the account disclosure. The mobile navigation and account disclosures close on outside interaction or Escape, with keyboard focus returned to their triggers. The brand returns signed-in users to Overview. The public header has fewer section links, and the primary public entry begins at Overview after authentication. In-page authentication returns to the current task. An account change remounts the page content to avoid showing the previous account's workspace.

Route-entry fades, dropdown transitions, interactive-card hover feedback, expanded-evidence transitions, and the handoff progress indicator are small CSS effects. Reduced-motion preferences disable visual motion. Page transitions do not transform the page container, so fixed dialogs remain attached to the viewport. No animation dependency or backend integration was added.

The preserved journey is Overview → Coverage & Gap Analysis → Ask ClaimWise → claim preparation and review. Coverage findings stay visible on the Coverage page, and their contextual primary action identifies the next stage. Loading historical findings never initiates a redirect. Automatic handoffs after explicit completion remain pausable.


## Development startup

FastAPI no longer loads the full users/policies/claims/bills/appeals/comparisons/audit registry or rebuilds every embedding index during imports and application startup. Persistent dictionary stores hydrate on their first read; failed reads stay retryable rather than caching an empty snapshot. Policies are still indexed before QA and coverage retrieval; adjudication and appeal retrieval also initialize their selected policy on demand. Database schema initialization has bounded connection and statement timeouts, and unavailable storage returns a controlled service error on access. Liveness stays reachable without a database connection.

The unified runner prefers the backend virtual environment over unrelated parent environments (while respecting an explicitly activated environment), fails promptly on a spawn error, and no longer terminates arbitrary processes occupying ports 8000/3000. Existing healthy backends are reused. The normal command remains `npm run dev` from ClaimWise.

Verification: cold-start test blocks all PostgreSQL connections and startup index loading, then asserts `/api/v1/health` is healthy. Lazy-store tests cover each record type, concurrent reads, retry after failure, and cache preservation. A real backend also served HTTP 200 with an unreachable database configuration. The full dev runner started Next.js, and both `/` and the proxied `/api/v1/health` returned HTTP 200 on port 3000. Tests are in `backend/tests/test_startup.py` and `frontend/tests/unit/dev.test.js`.

## Brand and hero restoration

The shared `LogoMark` uses `public/claimwise-mark.svg`: a policy document with a guidance bubble, in navy and teal. The homepage, assistant preview, app header, authentication pages, and authentication dialog use this mark; browser icon metadata points to the same asset.

The original policy and coverage hero artwork is visible again. Shared glass styling no longer hides their background layers or replaces their editorial headings. Overview reuses the existing illustrated document banner styles, with a working anchor to the scenario form. The public homepage hero, saved analyses, and navigation handoffs remain available. TypeScript and targeted ESLint checks pass; the affected page routes and logo asset return HTTP 200. No additional configuration or dependencies are required.
