# Production security audit — 2026-10-16

This is a targeted local code audit, not a certification or production deployment verification. Existing uncommitted changes were inventoried before edits. No live database, cloud account, secrets, documents, or Git history will be altered. Test credentials are process-local placeholders; the complete backend suite must not run against the user's database because existing fixtures clear persistent stores.

## Read-only findings and remediation plan

| Finding | Actual evidence before remediation | Severity | Initial status | Proposed action | Administrator action |
|---|---|---|---|---|---|
| Incomplete JWT validation | `core/security.py`: expiry/audience optional, malformed claim types can cause 500; issuer omitted when minting | High | Partially fixed (signature/algorithm already checked) | Require correctly typed claims, validate time/audience/issuer; fail closed | Configure issuer consistently; existing sessions may require login |
| Demo account password login in production | `auth.py`: registry seeds known demo users regardless of environment; `/demo` alone is blocked | Critical | Unresolved | Block demo identities during loading, login, and verification in production | Inspect persisted demo accounts; do not delete automatically |
| Private record isolation bypasses | Shared-owner allowlist contains actual user/demo identities; claim access permits dev-user across owners; guidance evaluates arbitrary policy without owner check | High | Partially fixed | Strict owner checks at all sensitive endpoints, including PDF, bill, guidance, retrieval, portfolio, comparison | Reassign ownerless legacy data only after review |
| Cookie owner access rejected | Policy/comparison checks require literal Authorization header after successful cookie verification | Medium | Unresolved | Authorize the verified identity, independent of credential transport | None |
| Production origin/configuration gaps | Origin accepts Host-derived origin; wildcard headers; production config accepts DEBUG, insecure origins and weak repeated secrets | High | Partially fixed | Explicit origin allowlist and fail-closed configuration; safe CSRF byte comparison | Confirm production environment and edge Host/TLS settings |
| Weak password work factor and role selection | PBKDF2 100,000 iterations; signup accepts arbitrary role string | High | Partially fixed | Increase work factor with login upgrade; permit only public persona roles, tier remains server assigned | None |
| Sensitive provider errors | Gemini response bodies/exception strings logged and returned in QA failure; DB exceptions logged raw | High | Partially fixed | Generic external failures and secret/PII log filtering | Restrict existing log access and retention |
| Upload mismatch/path trust | Claim extension and signature checked independently; policy document hash used directly in local path | Medium | Partially fixed | Match extension/MIME/signature; validate SHA-256 path component | Malware scanning at deployment remains unverified |
| Public operational endpoint | QA status lists global policy index IDs; benchmark can trigger paid requests without auth | Medium | Unresolved | Scope status and disable benchmark in production | Separate authorized benchmark environment |
| Credentials and Git history | Secret-safe scan of reachable history and current files; evidence recorded without values | Critical if exposure confirmed | Under investigation | Remove any confirmed source exposure; never rewrite history | Rotation/revocation requires provider administrator |
| Storage/backups/TLS | Original PDFs use local `backend/data/policy_pdfs`; claim evidence uses PostgreSQL; deployment manifests absent | High | Unverified | Document durable volume/object-storage and restore requirements | Verify infrastructure, backups and restore test |
| Static compliance self-assessment | `/security/self-assessment` contains hardcoded 100% and historic test totals | Medium | Unresolved | Restrict production access; explicitly document that it is historical, not evidence | Independent assessment required; no certification claimed |

## Baseline

- Backend: `python -m pytest tests -q --tb=short -p no:cacheprovider`, with isolated placeholder DATABASE_URL/GEMINI_API_KEY and test JWT: **exit 1; 177 passed, 52 failed, 17 errors; 443 warnings**. Integration fixtures require PostgreSQL; do not interpret this as a passing full suite.
- Frontend: TypeScript `--noEmit --incremental false`: **exit 0**; configured ESLint: **exit 0**; Next production build: **exit 0**.
- Evidence logs and source hashes are in ignored `temp/security-audit/`; no real environment values were copied.

## Remediation implemented

- JWTs require typed subject, expiry, issued-at, audience and configured issuer; future/not-yet-valid tokens, invalid algorithms, malformed structures, signatures and tiers fail closed. New tokens include the issuer. Production rejects development/demo identities. No signing secret was rotated. Existing tokens without the issuer need a fresh sign-in.
- Production configuration rejects missing/default/repeated secrets, misspelled environments, debug mode, insecure/wildcard origins, placeholder database credentials and database URLs without required TLS. Validation errors suppress configuration input values. This does **not** prove the deployed environment has these settings, or prove that an arbitrary accepted secret was generated randomly.
- Production registry loading and password login both block demo identities; the demo endpoint remains blocked. Signup permits the three existing public personas only and assigns tier/ID on the server. PBKDF2-HMAC-SHA256 uses 600,000 iterations; valid legacy hashes upgrade at login. This follows the [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html). No password reset or database migration was performed.
- Sensitive endpoints require authenticated sessions. Policy, claim, bill, guidance, comparison, coverage, portfolio and QA operations check ownership, including cookie-based PDF access and deletion. The shared-owner bypass is removed; ownerless legacy documents must be assigned through a reviewed migration rather than being treated as public. Comparisons/portfolios receive explicitly authorized policy maps.
- Cookie authentication, HttpOnly/Secure/SameSite=Lax, existing CSRF bootstrap, and credentialed requests remain. CSRF compares UTF-8 bytes safely; production Origins come only from configured origins, not the Host header. CORS accepts explicit request headers. Private API responses use `Cache-Control: no-store`. Logout clears expired sessions and still clears cookies if supplemental audit persistence is unavailable.
- QA telemetry filters policy IDs by owner. Paid benchmark execution, sample portfolio analysis and the historical hardcoded self-assessment are blocked in production. The historical assessment remains demonstration data in development; its 100% score is not audit evidence.
- Claim evidence checks extension, matching signature and MIME, size and ownership. Original-PDF paths require SHA-256 identifiers. No documents were migrated or removed. PDF test storage is isolated in pytest temporary directories.
- Provider/parser failures return generic messages. Logging removes configured credentials, database URLs, common identifiers, JWTs and bearer tokens, with exception values withheld. Filenames are omitted from PDF processing logs. Request-validation responses no longer echo submitted passwords/document content. Pattern-based redaction cannot guarantee removal of every form of PII; operational access/retention controls remain necessary.
- Audit metadata recursively sanitizes lists/dictionaries and fails closed if PII sanitization fails. Failed audit writes no longer append uncommitted fallback events. Existing persisted chain hashes were not rewritten. Sandbox idempotency is scoped by owner and claim.

## Credential investigation

Pattern scanning and exact matching of current environment credentials found **no confirmed credential matches** in tracked/current unignored files or the **one reachable Git commit**. Actual `.env` files remain ignored; examples contain placeholders. Secret values were never included in evidence files. This scan does not cover unreachable history, other clones/remotes, provider logs, ignored historical output or previously shared screenshots. It does not establish revocation of previously exposed credentials.

**Manual administrator action required:** if these credentials were previously exposed, treat rotation as pending until the administrator confirms replacement configuration and old credential revocation. No provider accounts were accessed and no production secrets were changed.

### Neon rotation

In [Neon Console](https://console.neon.tech), select the project and correct branch, then **Postgres database → Roles → the application's role menu → Reset password → Reset**. Copy the replacement connection string from **Connect** directly into the deployment secret manager and the applicable ignored local environment files. Restart application workers/pools and verify a fresh connection. Repeat for each affected branch and review suspicious existing sessions. Reset applies immediately to new connections; plan the application update accordingly. These steps follow [Neon's role/password documentation](https://neon.com/docs/manage/roles).

### Gemini rotation

Open [Google AI Studio API Keys](https://aistudio.google.com/api-keys), select/import the correct project, and create a replacement API key. Configure `GEMINI_API_KEY` in the backend deployment secret manager, restart workers, and verify a request using synthetic evidence. Then select and disable/delete the old key in [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials). Check API usage and billing for unexpected access; apply the relevant Gemini-only and supported application restrictions. Never use a `NEXT_PUBLIC_` variable for this key. Follow [Google's leak-response and key-management instructions](https://ai.google.dev/gemini-api/docs/api-key) and [rotation guidance](https://docs.cloud.google.com/docs/authentication/api-keys-best-practices).

### JWT rotation and session impact

JWT rotation was **not** performed. Generate at least 32 random bytes locally using a cryptographic generator (for example, `openssl rand -hex 32`) and place the result directly in the secret manager. Coordinate all application workers to use the replacement, restart them, and require users to sign in again. The current single-key verifier invalidates old sessions immediately when the key changes; do not roll mixed signing keys across workers. Logout clears browser cookies but does not revoke a copied signed token before expiry; server-side revocation needs an explicitly reviewed persistence design.

## Deployment and manual verification checklist

All items below are **Manual administrator action required** until verified in the actual environment.

1. Confirm backend `ENVIRONMENT=production`, `DEBUG=false`, strong random `JWT_SECRET`, stable `JWT_ISSUER`/`JWT_AUDIENCE`, a valid TLS-required `DATABASE_URL`, and a functioning backend-only Gemini key. Configure exact HTTPS frontend Origins, including any intended API docs origin. Start with valid configuration; independently verify missing/default keys and insecure origins prevent startup. Never log environment values.
2. Verify HTTPS certificates and redirects at the edge, TLS termination and trusted proxy headers, allowed Host names, direct backend exposure, request/upload size limits and rate limits. HSTS alone is not evidence of TLS. Review frontend CSP: the current config still allows inline/eval scripts and broad HTTPS connections; tightening requires a Next.js nonce/CSP design and a separate browser regression pass. No frontend CSP rewrite was attempted here.
3. Through the actual Next.js proxy, sign in, reload `/auth/me`, inspect HttpOnly/Secure/Lax/Path cookie flags without copying token values, and confirm `Cookie`, `Set-Cookie`, `Authorization` and `X-CSRF-Token` reach the intended endpoints. Keep frontend/backend on the intended same-origin deployment path. Test logout, expired session rejection and expired-session cookie clearing.
4. Replay cookie-authenticated mutations with missing, wrong and mismatched CSRF tokens (403), then correct tokens (normal operation). Send a foreign Origin and forged Host (403); check credentialed CORS preflight allows only configured Origins/headers. Verify early rejection responses and the edge add the required security headers.
5. Create two disposable staging accounts and policies/claims. Attempt cross-user metadata, PDF downloads, uploads, deletion, comparison, coverage, QA, bill conversion, guidance, claim edits, appeals and audit queries using direct API calls. Check denied responses expose no foreign contents; run successful owner operations too. Never use real medical records for this test.
6. Test empty, oversized, renamed executable, MIME/signature mismatch and malformed PDF uploads on staging. Check private files have no public static route. Content signatures are not a malware scan; add a reviewed scanner/sandbox if the deployment requires it.
7. Original policy PDFs live in `backend/data/policy_pdfs`, while claim-document bytes and structured records live in PostgreSQL. Verify a durable, private shared volume for every backend replica and redeploy, or plan an authenticated object-storage migration with checksum verification, ownership mapping, backup and rollback before changing storage. Do not assume ephemeral local disk is durable. No migration was performed.
8. Inspect Neon restore-window/backup configuration, access controls and retention for the actual plan. Back up the PDF volume as well as PostgreSQL; include environment/secret recovery under separate restricted controls. Restore **copies** to an isolated branch and separate private directory, verify counts, content hashes, ownership and the audit chain, document recovery time, and never restore over live data during a drill. Cloud backups and restore capability were not accessible or tested here.
9. Restrict and review historical application/provider logs, configure retention and alerting, and confirm no sensitive request bodies are captured by proxy/APM logging. Verify database least-privilege roles; the application's automatic schema initialization currently needs privileges that should be reviewed separately from runtime access.

## Remaining limitations

- **Unresolved:** complete PostgreSQL integration verification requires a disposable database, fixtures and seeded accounts. The existing suite includes persistent-store clear operations and must not run against the working database. No test or security control was disabled to claim a passing full suite.
- **Unresolved:** advertised permission-tier definitions are not uniformly enforced by route dependencies (`require_min_tier` exists but claim routes do not consistently use it). Existing claim/draft workflows and persona entitlements were preserved. A product-approved entitlement mapping is needed before imposing new gates; signed tiers and server-assigned signup tiers alone do not prove complete RBAC.
- **Unresolved:** stateless token revocation, deployment rate limiting, parser resource/malware isolation, frontend nonce-based CSP, and durable cloud storage/backup verification remain follow-up work. These require explicit operational/design decisions, not a claim of compliance.
- **Fixed in code; deployment verification required:** configuration, cookies/CSRF/CORS and secret-safe logging protections above must be exercised through the actual production edge.

## Final verification

Backend commands ran from `backend/` with process-local disabled database/AI credentials, development mode and a synthetic signing key. Environment files were not edited. Temporary pytest-directory access required an elevated tool run; the initial sandbox denial was not a code failure. New tests replace only persistence/provider boundaries, using real token signing, middleware, endpoint authorization and schema validation.

| Check | Actual command/result | Exit |
|---|---|---|
| Complete backend | `.\venv\Scripts\python.exe -m pytest tests -q --tb=short -p no:cacheprovider`: **273 passed, 54 failed, 17 errors, 479 warnings**, 35.68 seconds | 1 |
| Focused security/business/upload regressions | Command below: **158 passed, 2 deselected, 65 warnings**, 24.60 seconds | 0 |
| New direct security tests | `test_production_security.py`: **92 cases**, all included in passing focused run; no new-module failures in complete run. `--collect-only -q` confirms 92 | 0 |
| Frontend TypeScript | `node node_modules/typescript/bin/tsc --noEmit --incremental false` | 0 |
| Frontend configured lint | `node node_modules/eslint/bin/eslint.js . --format json`: **1 error, 14 warnings**; `src/app/activity/page.tsx:201`, `react-hooks/set-state-in-effect` | 1 |
| Frontend production build | `node node_modules/next/dist/bin/next build`: all 14 routes generated | 0 |
| Frontend unit tests | `node --experimental-strip-types --test tests/unit/*.test.js tests/unit/*.test.mjs`: **18 passed, 0 failed** | 0 |
| Production startup | Synthetic valid production configuration imports application, root returns 200, protected policies returns 401; no database connection attempted | 0 |
| Production missing secret | Same process-local configuration with blank JWT secret refuses import/startup | 1 (expected) |
| Bundle credential scan | **33** built frontend JavaScript files checked for exact current DB/API/JWT environment values: **0 matches** | 0 |
| Git/unchanged-source inventory | Working-tree status saved before/after; protected insurance services match audit-start hashes; no baseline source files removed | 0 |

Focused command, run from `backend/`:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_production_security.py tests/test_claim_workflow.py tests/test_rules_engine.py tests/test_bill_parser.py tests/test_qa_service.py tests/test_overlap_analysis.py tests/test_qa_procedure_retrieval.py tests/test_security_compliance.py tests/test_policy_upload_api.py -k 'not test_upload_valid_pdf and not test_list_and_get_policy_endpoints' -q --tb=short -p no:cacheprovider
```

The two deselected cases are upload **persistence** integrations, not validation tests; both ran and failed in the complete run. No tests were deleted. The full suite is **not green**: database-backed persistence/audit/account tests cannot complete with disabled PostgreSQL; sample-policy hydration and older integration fixtures also remain unresolved, including legacy anonymous-access expectations. The 17 setup/teardown errors occur in appeal (6) and comparison (11) fixtures. No `TEST_DATABASE_URL`, local PostgreSQL server/client or Docker command was available in the inspected environment. A disposable PostgreSQL test environment is required before interpreting the integration results. Test pass counts do not establish complete security or compliance.

The latest frontend lint error arose in files changed concurrently outside this remediation pass. `Navigation.tsx`, `Topbar.tsx`, `lib/api.ts`, dashboard `ActivityList.tsx`, and `app/activity/page.tsx` differ from the audit-start hashes despite no frontend writes by this pass. Those edits were preserved; their lint error was not hidden or auto-fixed. The audit endpoint also changed concurrently; its current owner-scoped behavior was tested. Frontend build/types/unit results describe the tested snapshot, not a claim that the working tree stayed static throughout the audit.

SHA-256 comparison confirms no changes to the rules engine, claim adjudication, coverage evaluation, claims guidance, comparison, overlap analysis, portfolio, appeal generation or PDF export service files. The document and bill parsers changed only their failure logging/messages; sandbox changes isolate retry keys, and QA changes sanitize provider errors. Claim workflow and calculation regressions passed. UI/styling files were not edited by this remediation pass. Actual environment files, database schemas, original policy fixtures, saved claims/documents, existing Git history and unrelated working-tree changes were preserved.

Evidence is in ignored `temp/security-audit/`: baseline/final test logs, frontend check logs, synthetic startup checks, safe secret-scan metadata and source/status manifests. Do not commit these machine-local logs automatically.

## Final disposition

| Status | Scope |
|---|---|
| **Fixed and tested** | JWT claim/issuer validation, demo password/token guard, strict owner checks and cookie access, CSRF/Origin rejection including security headers, password hashing/upgrade, upload signature/MIME matching, validation/provider error sanitization, recursive audit redaction, uncommitted audit-event prevention and sandbox retry isolation. |
| **Fixed in code; deployment verification required** | Production fail-closed settings, cookie flags and proxy forwarding, CORS configuration, HSTS/security headers, log protection and private storage access through the real edge. |
| **Manual administrator action required** | Confirm credential revocation/replacement if exposed; production environment/HTTPS/proxy setup; durable PDF storage; cloud database permissions, backups, restore and log retention verification. |
| **Unresolved** | Full PostgreSQL integration suite, current concurrent frontend lint error, complete permission-tier entitlement mapping, stateless token revocation, frontend CSP hardening, operational rate/malware/resource controls. |

Production security verification remains incomplete until these unresolved and administrator items are addressed.
