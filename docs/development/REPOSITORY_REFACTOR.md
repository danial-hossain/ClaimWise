# Repository refactor audit and validation

This was a structural refactor of the existing working tree. Pre-existing uncommitted work
was preserved. No Git reset, checkout, history rewrite, dependency upgrade, or deployment occurred.

## Audit and scope

The initial audit inspected all application/source/test files, launch scripts, package manifests,
lockfiles, configuration, environment templates, ignore rules, docs, migrations, and fixture paths.
Generated/dependency directories were excluded from the source inventory. A baseline snapshot
of 267 source/document/fixture files and the initial Git status was recorded locally under
the ignored `temp/repository-refactor/` directory; environment secrets and local databases
were excluded from that snapshot.

The backend already has distinct API, core, schema, model, database/repository, and service
packages. Those paths were retained to avoid import, migration, and runtime-discovery churn.
Next.js route files, stylesheet order, public application icon paths, and service entry points
were retained. No empty placeholder directories were added merely to match a reference layout.

## File moves

The complete 30-file mapping is in [refactor-moves.json](refactor-moves.json).

| Previous location | Final location | Purpose |
| --- | --- | --- |
| `frontend/src/components/auth/` | `frontend/src/components/features/auth/` | Authentication UI feature |
| `frontend/src/components/dashboard/` | `frontend/src/components/features/dashboard/` | Overview UI feature |
| `frontend/src/components/wizard/` | `frontend/src/components/features/wizard/` | Claim preparation feature |
| `frontend/src/components/ui/HomeHero.tsx`, `home-hero.css` | `frontend/src/components/features/home/` | Homepage-only component and its unchanged stylesheet |
| `frontend/scripts/dev.test.js`, `wizard.test.mjs`, `wizard-behavior.test.mjs` | `frontend/tests/unit/` | Separate automated tests from service launchers |
| `frontend/scripts/verify-*.mjs` | `frontend/tests/browser/` | Separate manual browser checks; screenshot destinations unchanged |
| `docs/ARCHITECTURE.md`, `DATABASE_SCHEMA.md` | `docs/architecture/` | Architecture references |
| `docs/API_SPECIFICATION.md` | `docs/api/` | API reference |
| `docs/CLAIM_WORKFLOW.md` | `docs/development/` | Workflow documentation |
| `docs/UI_*.md` | `docs/development/reports/` | Preserved UI milestone evidence |
| `docs/SECURITY_AND_COMPLIANCE_SELF_ASSESSMENT.md` | `docs/security/` | Preserved security milestone evidence |

Imports, unit-test paths, browser-script roots, npm commands, documentation references, and
relative screenshot links were updated. Existing scripts and their outputs retain their purpose.

## Consolidation

- Both launcher implementations now use `frontend/scripts/find-python.js`. The development
  and standalone profiles retain their **different original candidate priorities**; this does
  not silently expand the standalone launcher's interpreter search. Two regression tests cover
  candidate order and the active-virtualenv override.
- Overlap request/response model definitions moved from the service to
  `backend/app/schemas/overlap.py`. The service imports/re-exports those same names for compatibility.
  Field definitions, response contracts, prompts, citation verification, and analysis logic were not changed.
- ESLint explicitly permits CommonJS imports in Node launcher/test `.js` files. TypeScript
  application rules remain active. No security lint rule or runtime security control was disabled.

No universal utility module, authentication abstraction, business-rule merge, or database
repository rename was introduced. Similar-looking domain implementations were left separate.

## Deletions

Reference searches covered source, tests, scripts, documentation, configuration, and existing
routes before removal. No CI/deployment files were present that referenced these assets.

| Deleted file | Reason |
| --- | --- |
| `frontend/src/components/ui/FloatingChatWidget.tsx` | Disconnected obsolete widget; no imports or callers. Its removal from the product had already been requested; the active workspace popup is separate and preserved. |
| `frontend/public/file.svg` | Unreferenced create-next-app starter asset |
| `frontend/public/globe.svg` | Unreferenced create-next-app starter asset |
| `frontend/public/next.svg` | Unreferenced create-next-app starter asset |
| `frontend/public/vercel.svg` | Unreferenced create-next-app starter asset |
| `frontend/public/window.svg` | Unreferenced create-next-app starter asset |

The duplicate root `src/` tree contained no files and was removed as empty directories.
Empty source directories left by moves and the now-empty starter `public/` directory were removed.
Active icons remain in `frontend/src/app/icon.svg` and `favicon.ico`.

No local environment, lockfile, migration, uploaded document, policy PDF, database, security
report, screenshot, recording, benchmark report, or milestone handoff was removed.
Active build caches were not recursively deleted. Existing caches are ignored; root ignore rules
now also cover TypeScript incremental state and frontend test output. Lockfile bytes are unchanged.

## Documentation/configuration

Replaced the stale milestone README and generic Next.js README with actual onboarding commands
and a directory map. Added backend onboarding, a documentation index, development/setup notes,
deployment notes, and current security implementation notes. Historical reports are identified
as such rather than treated as a fresh production certification.

Added `.editorconfig` without bulk reformatting existing files. Added `typecheck`, frontend-test,
and explicit browser-verification npm commands; preserved the existing dev/build/start commands.
Environment templates retain their variable names. The backend JWT template now leaves the
secret blank instead of supplying a reusable signing secret; actual `.env` files were untouched.
No new runtime dependency, SQL migration, container, CI pipeline, or hosting configuration was added.

## Validation results

| Check | Baseline | Final |
| --- | --- | --- |
| Complete backend suite, offline environment | 177 passed, 52 failed, 17 setup/teardown errors | Same: 177 passed, 52 failed, 17 errors; no new failed/error case IDs |
| Frontend TypeScript | Passed | Passed |
| Configured full frontend lint | 12 errors, 7 warnings | 0 errors, 7 warnings |
| Existing frontend tests | 16 passed | 16 passed, plus 2 new launcher tests passed |
| Next.js production build | Passed | Passed; same route set |
| Source preservation audit | Initial SHA-256 inventory | Active route/UI styles, state, core security, database modules and domain services match baseline bytes after reversing import-only replacements; overlap service changes limited to model relocation/imports |

Commands executed (from `backend/` or `frontend/` as appropriate):

```text
venv/Scripts/python.exe -m pytest tests -q --tb=short -p no:cacheprovider
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/eslint/bin/eslint.js . --format json --output-file ../temp/repository-refactor/final-lint.json
node --experimental-strip-types --test tests/unit/*.test.js tests/unit/*.test.mjs
node node_modules/next/dist/bin/next build
```

The baseline Node tests used their original `scripts/` paths. Build and Node test workers
required execution outside the sandbox after initial worker-spawn `EPERM` failures; the
successful reruns are the outcomes reported above.

The **complete backend suite does not pass** in this environment. It ran with process-local
`DATABASE_URL=placeholder`, `GEMINI_API_KEY=placeholder`, a test JWT secret, and development mode.
This prevents tests that persist or clear fixtures from touching the user's working database.
The original suite has database-coupled fixture setup/teardown, authentication assumptions,
and AI-related assertions that are not all satisfied offline. The identical failure set was
preserved rather than changing tests or weakening application behavior to make it green.

The full suite includes cookie/session, CSRF, Origin, ownership, upload, audit, PII, rules-engine,
and claim-workflow tests. Their unchanged offline outcomes do **not** certify all integrations
or a deployed security configuration. No live insurer, AI, database mutation, deployment,
or manual browser end-to-end workflow was run as part of this structural refactor.

Detailed local logs and the baseline/final failure-case comparison are under
`temp/repository-refactor/` (ignored, not submission artifacts).

## Remaining work and preserved candidates

- Provision a disposable PostgreSQL database and rerun integration/security tests there;
  investigate any remaining original failures separately from this structural change.
- Seven existing lint warnings remain (unused variables and redundant suppressions); no application behavior was changed to silence them.
- `Navigation`, `BackendHealthWidget`, `dashboard-data`, unused dashboard helpers, and some shared
  UI components remain candidates for a separate product-level review. Some are referenced by
  historical deliverables or encode domain calculations; they were preserved rather than guessed away.
- Historical schemas, benchmark artifacts, root `output.txt`/`output_backup_m5.txt`, sample PDF ZIP,
  and security/UI reports are retained as potentially valuable competition deliverables.
- Dependency upgrades, Python packaging changes, repository-wide API client redesign, and
  production deployment verification are outside this refactor. No distribution license was invented.

No intentional change was made to UI/layout, navigation, responsive behavior, AI prompts,
insurance formulas, workflows, API contracts, migrations, persistence, cookies, CSRF/Origin
handling, authorization, PII handling, or audit-chain behavior.
