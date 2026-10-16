# Policy retrieval, analysis and guidance repair - 2026-10-16

## Verified outcome

- Independent backend suite: **337 passed, 42 deselected, 182 warnings**, exit 0, 26.47 seconds. The 42 PostgreSQL integrations remain blocked by unavailable disposable infrastructure, as recorded in the backend test repair report. They were not run against the working database.
- New source-integrity module: **29 passed**, exit 0, 2.07 seconds. It uses generated PDFs, actual extraction and BM25/hybrid retrieval, and synthetic model-output boundaries. It does not mock retrieval or call a paid model.
- Frontend unit suite: **27 passed, 0 failed**, exit 0. Nine new cases cover presentation, actual component markup and stale request generations.
- Frontend TypeScript: exit 0. Configured ESLint: exit 0, **0 errors, 15 warnings**. Production build: exit 0, all 14 routes generated.
- No actual environment files, private documents, working database, authentication/ownership controls or insurance calculations were modified. Existing unrelated working-tree edits were preserved.

## Request-to-response map

**My Policies:** authenticated upload -> `document_service.process_pdf` -> page/block extraction, normalization, headings and clause IDs -> policy JSON persistence and private original-PDF storage -> hybrid indexing. The policy reader parses the full clause text. Its heading-rewrite context is a display summary, not the source evidence.

**Coverage Analysis:** authenticated `/coverage/analyze` -> owned `get_policy_record` -> `coverage_gap_service.analyze_scenario` -> hybrid retrieval plus coverage-specific search/filtering and supporting context -> deterministic evaluator or configured grounded model -> source validation -> `CoverageGapAnalysisResult` -> owner-scoped workflow JSON persistence -> `AnalysisContext`.

**Ask ClaimWise:** authenticated `/qa/ask` -> verify every selected policy belongs to the caller -> index the authorized records -> shared hybrid retrieval with conversational/procedural search -> `qa_service.generate_grounded_answer` -> structured-output and citation checks -> `QAResponse` -> `GroundedAnswer`.

**Linked Guidance:** `/coverage/analyses/{id}/ask` loads the caller's saved analysis, preserves its incident/policy/history and delegates to the same authorized QA endpoint. Structured next steps on an analysis are saved in its `guidance` field. Claim-draft checklists/deadlines remain the separate incident-guidance workflow; they are not silently borrowed for another analysis on the same policy.

Ask and Analysis share the hybrid index, BM25/dense engines and citation validator. They retain distinct search/context and response responsibilities. They were not merged into one endpoint.

## Reproduced causes

1. **Destructive quote windows:** coverage report and several deterministic branches cut source text at 1,200 characters. Additional deterministic helpers selected a window around a regex match and cut it to 240 characters. The UI displayed these substrings as verified quotations without showing that conditions or exceptions had been omitted.
2. **Segmentation and identity:** exclusion grouping recognized only single-letter list markers, not multi-character Roman numerals. It did not stop at every explicit new section. Repeated section numbers could yield duplicate clause IDs. Hybrid deduplication also omitted the page from its key.
3. **Stale indexing:** hybrid cache reuse depended only on the original document hash. Revised extraction of identical PDF bytes could leave old search text indexed.
4. **Insufficient source validation:** QA accepted a fabricated quote when its first 30 characters matched. Clause-ID fallback could also resolve a citation that named a different source document. Coverage's endpoint had equivalent prefix/superstring acceptance.
5. **Analysis/Guidance mapping:** `GuidanceSummary` displayed `analysis.explanation` under a Why section and reused analysis conditions/limits. It also read `scenario.claimDraft.guidance` by policy ID alone, allowing checklist/obstacle data from a different incident on the same policy.
6. **Hidden qualified answers:** Workspace rendered an abstention notice *instead of* the model's answer and citations whenever evidence was insufficient. This suppressed useful supported findings in qualified answers.
7. **Request races:** asynchronous context/answer loading lacked invalidation on scope changes and unmount. The initial journey snapshot could also outlive the current scenario.

The first three added reproduction tests were run before fixes: **3 failed**, demonstrating the 1,200-character cutoff, fabricated-tail acceptance and wrong-document citation acceptance. A further regression explicitly checks the 240-character cutoff.

## Design and changes

### Source integrity and retrieval

- Quote helpers now return the entire extracted source clause. Matching chooses a source record, not a character window. Display titles/descriptions and explicitly flagged retrieval-trace previews remain summaries.
- Roman, lettered and numeric exclusion items retain their wrapped text and introductory section wording. Explicit high-confidence headings stop section grouping. Duplicate extracted IDs receive a stable page/block suffix.
- PDF page indexes remain one-based. Explicit PDF page labels are retained separately as `printed_page_label`; labels are not inferred from arbitrary footer numbers or invented for old records.
- Hybrid indexing fingerprints the extracted records, so changed extraction refreshes the same original PDF hash. Deduplication uses policy, clause and page.
- Source expansion follows contiguous unfinished blocks across pages and supplies each fragment with its original ID, page and text. It never stitches cross-page words into a single falsely located quotation. This is conservative continuation recovery, not a promise to reconstruct every possible PDF layout.
- Symmetric lexical vocabulary normalization bridges common vehicle/repair/maintenance terms when optional embeddings are unavailable. These are search terms only, never keyword-to-answer templates. Dense retrieval remains optional and reports degraded BM25 mode when unavailable. No fake semantic embeddings or additional reranker were introduced.
- Removed page/section/amount-specific vehicle retrieval shortcuts and fixed policy assertions in the shared model prompt. Supporting context now searches the actual corpus for conditions/exclusions/claims and filters unrelated topics. Existing deterministic insurance rules were not rewritten.
- A shared **40,000-character evidence budget**, including per-record metadata allowance, selects whole source records. Whole omitted records are identified in `evidence_limitations`; their text is not silently sliced. A limited evidence set cannot become a definitive model answer. This is an application context budget, not a model-tokenizer measurement.
- Citation validation requires the named authorized policy and actual page, and the entire normalized quote must occur in that source. Printed-ID compatibility is allowed only for a unique literal identifier in that same policy/page. Prefix-only and source-inside-invented-superstring acceptance were removed.

### Stable response and UI contract

- Existing analysis fields remain compatible: `explanation`, `conditions_summary`, `cost_sharing_summary`, `clauses`, `insurer_questions`.
- Additive `guidance: [{text, citations}]` represents distinct practical actions. Each action requires its own verified citations; exact duplication of the interpretation is rejected. Old saved analyses default to an empty action list. Missing actions are shown as unavailable rather than copied from interpretation.
- Additive `evidence_limitations` is available on QA and analysis results. JSON persistence already serializes complete Pydantic results, so no database schema migration is needed.
- Structured model output is checked for correct container/string/boolean/list types. Malformed guidance or fabricated citations produce a qualified, non-definitive result with actual retrieved wording available. Invalid model output is not promoted into a positive fallback decision.
- Substantive model uncertainty stays uncertain. A narrow correction remains for a falsifiable statement that *no clause was retrieved* when the existing deterministic rules have source-validated affirmative evidence. Missing-Schedule uncertainty is not treated as that absence error.
- Model-generated insufficient answers use `evidence_unavailable`; retrieval excerpts alone do not establish whole-policy silence. The pre-existing explicit full-policy primary-care absence scan retains its established `not_specified` behavior.
- `AnalysisContext` renders only interpretation and its source claims. `GuidanceSummary` renders only saved actions and insurer questions; it does not consume policy-matched draft guidance.
- `GroundedAnswer` renders qualified answers and verified citations alongside the abstention notice. It does not hide material policy findings because the final coverage position remains uncertain.
- Presentation adapters tolerate missing/malformed legacy fields. Request generations reject late responses after a policy/scenario change, refresh or unmount. Context loaders check their generation before committing asynchronous results and respond to current scenario references instead of stale initial IDs.

### Files changed

| Files | Purpose |
|---|---|
| `backend/app/services/document_service.py`, `backend/app/schemas/policy.py` | Roman list segmentation, section boundaries, unique source IDs and explicit PDF labels |
| `backend/app/services/retrieval/bm25_service.py`, `hybrid_service.py`, new `evidence_context.py` | Lexical normalization, content-aware cache refresh, source continuation and whole-record budget |
| `backend/app/services/qa_service.py`, `backend/app/schemas/qa.py` | Exact source validation, typed output, authorized evidence filtering and qualified context limits |
| `backend/app/services/coverage_gap_service.py`, `backend/app/schemas/coverage.py`, `backend/app/api/v1/endpoints/coverage.py` | Full quotations, generic supporting retrieval, separate grounded actions, output validation and strict source checks |
| `backend/tests/conftest.py`, new `backend/tests/test_source_integrity.py` | Isolate new source-context cache and add deterministic extraction/retrieval/contract regressions |
| `frontend/src/lib/evidencePresentation.ts`, `frontend/src/types/api.ts` | Safe backward-compatible mappings and request generation helper |
| `frontend/src/components/ui/AnalysisContext.tsx`, new `GroundedAnswer.tsx`, `frontend/src/components/features/wizard/GuidanceSummary.tsx` | Separate interpretation/actions and retain qualified explanations/citations |
| `frontend/src/app/workspace/page.tsx` | Integrate evidence rendering and prevent stale asynchronous context/answers |
| `frontend/tests/unit/evidence-presentation.test.mjs` | Nine data, request generation and real component markup regressions |

## Verification commands and actual results

Commands below ran from the indicated project directory. Backend tests use the existing fail-closed test configuration and synthetic credentials. Logs are ignored under `temp/backend-test-repair/`; actual environment values were not copied into them.

| Directory | Exact command | Result |
|---|---|---|
| `backend` | `.\venv\Scripts\python.exe -m pytest tests/test_source_integrity.py -q --tb=short -p no:cacheprovider` | Before fixes: 3 failed. Final focused module: 29 passed, 1 warning, exit 0 |
| `backend` | `.\venv\Scripts\python.exe -m pytest tests/test_source_integrity.py tests/test_qa_service.py tests/test_coverage_gap.py tests/test_qa_40_benchmark.py tests/test_production_security.py -m 'not database' -q --tb=short -p no:cacheprovider` | First implementation run: 128 passed, 14 failed, 4 deselected. Exposed overly broad punctuation completeness checks and existing error-message expectations. Fixed without changing those tests. |
| `backend` | `.\venv\Scripts\python.exe -m pytest tests/test_source_integrity.py tests/test_coverage_gap.py -m 'not database' -q --tb=short -p no:cacheprovider` | Final combined focused run before last single regression addition: 54 passed, 4 deselected, exit 0 |
| `backend` | `.\venv\Scripts\python.exe -m pytest tests -m 'not database' -q --tb=short -p no:cacheprovider` | Final: 337 passed, 42 deselected, 182 warnings, 26.47s, exit 0 |
| `frontend` | `node --experimental-strip-types --test tests/unit/*.test.js tests/unit/*.test.mjs` | Final: 27 passed, 0 failed, exit 0. An earlier new-component test harness had 2 failures; module interop in the harness was corrected. |
| `frontend` | `node node_modules/typescript/bin/tsc --noEmit --incremental false` | Exit 0 |
| `frontend` | `node node_modules/eslint/bin/eslint.js . --format json` | Exit 0: 0 errors, 15 warnings. Initial new-test variable-name lint error was fixed; no rule disabled. |
| `frontend` | `node node_modules/next/dist/bin/next build` | Exit 0: all 14 routes generated |
| root | `git diff --check` | Exit 1: unchanged pre-existing whitespace findings in `backend/app/api/router.py` and `backend/tests/test_comparison.py`; unrelated edits preserved |

Sandbox runs initially rejected Node worker spawning with EPERM. Required test/build commands were rerun with approved worker access; this was an environment restriction, not a passing check. The backend module also uses approved pytest temporary-directory access.

The synthetic motor document covers workshop/garage paraphrases, custody exclusions and Schedule exceptions, unattended/abandoned vehicles, original versus further damage, maintenance/unroadworthy wording, Roman x-xvii, cross-page continuation, explicit labels, mixed affirmative/exclusion evidence, no-match queries and scope isolation. Additional cases cover another differently worded synthetic policy, same-PDF reindexing, budget omissions, fabricated tails, wrong-document citations, malformed booleans/guidance, qualified model output and JSON contract round trips. Existing security tests continue covering authenticated endpoint ownership/cookies/CSRF with isolated persistence boundaries.

## Limits and follow-up

- The actual reported insurer PDF was not attached in this request. The quoted failure shape was reproduced with synthetic PDFs and source text; no claim is made that the original upload was inspected. Existing saved analyses are not rewritten automatically; regenerate an analysis to replace its old truncated quotations. Older extracted records retain their original PDF indexes and IDs, and printed labels remain unknown when unavailable.
- No live Gemini or embedding-model quality evaluation was run. Deterministic retrieval, real extraction and output-validation tests do not prove every paraphrase or a model's legal interpretation. The optional dense engine remains dependent on installed packages/model weights; source evidence is never replaced by test embeddings.
- Page-spanning reconstruction is conservative. Complex columns, tables, OCR/scanned documents, unusual numbering and standalone continuation headings still need source review. No fragment is labeled the complete operative section merely because it was retrieved.
- The full PostgreSQL suite, saved-record persistence under the real database and browser workflows with an authenticated account remain unverified here. No working database was used to make them appear green.
- **No insurer-specific answer, fixed workshop clause, expected page/limit or question-to-answer shortcut was added.** The shared retrieval and prompt paths were made more general. Pre-existing document-specific travel branches remain in the legacy deterministic evaluator because this task also requires preserving established insurance business rules. This is not a claim that the entire legacy codebase is free of insurer-specific logic. Replacing those legacy rules would require a separately reviewed behavior change and corresponding source-based acceptance tests.
- The original source text is normalized for PDF line wrapping by the existing ingestion code. Citation comparisons use that normalized extraction, not a claim of byte-for-byte identity with PDF binary content or an OCR certification.
