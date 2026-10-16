# Backend test diagnosis and repair ? 2026-10-16

## Result and scope

The final independent run passed **308 tests, 0 failures, 0 errors**, with **42 PostgreSQL integrations deselected by explicit selection**, and 182 dependency deprecation warnings (23.87 seconds). Those 42 integrations are **blocked**, not passing or skipped automatically. No tests were removed or disabled. The complete suite was not executed because no verified disposable PostgreSQL database exists in this environment.

There is no configured `TEST_DATABASE_URL`, PostgreSQL server/client installation or service, or Docker/Podman command in the inspected environment. The historical 273/54/17 result is not a new baseline or a claim about the current complete suite.

Actual `.env` files, working databases, documents, Git history and unrelated edits were preserved. The test process replaces database/provider credentials before importing application settings. PDF output goes to pytest temporary storage. No real provider requests or database mutations were performed.

## Failure groups and changes

| Group | Diagnosis | Files changed in this pass | Regression coverage / result |
|---|---|---|---|
| Integration infrastructure | PostgreSQL persistence and account/audit fixtures cannot operate without a database. Earlier placeholder runs produced setup/teardown errors. | `tests/_database_safety.py`, `tests/conftest.py`, `pytest.ini`; database markers in affected API/persistence modules | 20 new safety cases cover explicit opt-in, database/role naming, confirmation, protected application targets, pooled aliases, DSN overrides, credential-safe rejection and sync/async connection denial. All pass. 42 real integrations remain blocked. |
| Unit fixture persistence coupling | Comparison/appeal unit fixtures wrote to persistent dictionaries, with teardown forcing database hydration. Portfolio/guidance units depended on implicit sample hydration. | `tests/conftest.py`, `test_comparison.py`, `test_appeal_generator.py`, `test_milestone6_security_audit_pdf.py`, `test_portfolio_analysis.py`, `test_claims_guidance.py` | Explicit memory-backed service inputs and parsed fictional PDFs. Real integration fixtures retain real persistence. All selected service tests pass. |
| Search/benchmark isolation | Search indexes survived between tests; resetting indexes alone left the benchmark singleton incorrectly marked hydrated. | `tests/conftest.py` | Fresh BM25/dense/hash indexes and benchmark hydration flag per test. Existing deterministic benchmark service and authenticated API assertions pass unchanged. |
| Schema initialization timeout | An old test mocked direct psycopg calls after initialization moved to the connection pool. The pooled path also lacked its transaction-local schema timeout. | `app/db/local_store.py`, `tests/test_database_connection.py` | Restored `SET LOCAL statement_timeout = '15s'`; test mocks the pool connection boundary and checks first SQL plus successful initialization. Passes without a database. Live Neon behavior remains unverified. |
| Authorized portfolio lookup | A missing key in an explicit authorized map fell back to global lookup. | `app/services/portfolio_service.py`, `tests/test_portfolio_analysis.py` | Two new tests assert missing keys fail closed without global access and authorized records resolve. Both pass. No insurance calculations changed. |
| Obsolete API fixture assumptions | Some integration clients lacked authentication; fixtures seeded ownerless/foreign-owner policies or only indexed clauses without persisting a policy. Anonymous sample access is no longer an intended workflow. | `test_comparison.py`, `test_appeal_generator.py`, `test_coverage_gap.py`, `test_milestone6_security_audit_pdf.py`, `test_claims_api_and_sandbox.py`, `test_claims_guidance.py`, `test_portfolio_analysis.py`, `tests/conftest.py` | Explicit synthetic bearer credentials/ownership, real seeded policies on the attested database, and authenticated sample upload. Collection succeeds; these database-backed workflow changes are **not execution-verified**. |
| Provider error expectation | An older integration asserted that raw provider quota details appeared in the answer, conflicting with deliberate error sanitization. | `tests/test_qa_api.py` | Assert provider details are absent, while retaining failure/abstention assertions; assert upload success before using IDs. Database API cases remain blocked; existing independent QA/security regressions pass. |
| Persistence documentation | Restart test described obsolete SQLite storage. | `tests/test_persistence.py` | Corrected to disposable PostgreSQL; no behavior changed. |

## Actual verification

Commands ran from `backend/`, using `venv/Scripts/python.exe`. Evidence logs are ignored local files under `temp/backend-test-repair/`.

| Check | Command | Actual result |
|---|---|---|
| Initial safe focused baseline | `python -m pytest tests/test_production_security.py tests/test_claim_workflow.py tests/test_rules_engine.py tests/test_bill_parser.py tests/test_qa_service.py tests/test_overlap_analysis.py tests/test_qa_procedure_retrieval.py tests/test_security_compliance.py -q --tb=short -p no:cacheprovider` | Exit 0: 152 passed, 11 warnings, 41.51s |
| First independent diagnosis | `python -m pytest tests -m "not database" -q --tb=short -p no:cacheprovider` | Exit 1: 284 passed, 2 failed, 42 deselected, 173 warnings, 68.78s. Failures: schema timeout and benchmark hydration. |
| Focused repairs | `python -m pytest tests/test_database_safety.py tests/test_database_connection.py tests/test_qa_40_benchmark.py tests/test_portfolio_analysis.py -m "not database" -q --tb=short -p no:cacheprovider` | Exit 0: 37 passed, 1 deselected, 20 warnings, 5.52s |
| Final independent verification | `python -m pytest tests -m "not database" -q --tb=short -p no:cacheprovider` | Exit 0: 308 passed, 42 deselected, 182 warnings, 23.87s |
| Exact blocked inventory | `python -m pytest tests -m database --collect-only -q -p no:cacheprovider` | Exit 0: 42 of 350 collected, 308 deselected; no tests executed |
| Working tree whitespace check | `git diff --check` | Exit 1: pre-existing/unrelated blank EOF in `app/api/router.py`, trailing whitespace in comparison test docstring. Left untouched. |

The 22 new cases comprise 20 database-safety cases and two authorized portfolio resolution cases. Passing independent security regressions include real JWT signing, anonymous-access rejection, cross-owner denial, cookie transport, CSRF, upload validation and audit failure handling with isolated external persistence/provider boundaries. This is not a substitute for PostgreSQL persistence, concurrency, full account restoration or production edge verification.

## Safely enabling the blocked tests

Provision a **new, disposable PostgreSQL database and dedicated role**, both named with the `claimwise_test_` prefix. Do not rename or repurpose the working database. The server must have pgvector available and allow the required test schema/extensions. The test role must have only the privileges needed on this disposable database.

On that disposable database only, an administrator must create and seed the attestation table:

```sql
CREATE TABLE public.claimwise_test_database_marker (purpose text NOT NULL);
INSERT INTO public.claimwise_test_database_marker VALUES ('disposable-claimwise-tests');
```

Set process-local `TEST_DATABASE_URL` to its private connection string and `CLAIMWISE_TEST_DB_CONFIRM` to its exact database name. Never print or commit the URL. The runner rejects known application database identities, mismatched naming/confirmation and connection-target overrides. Before fixtures may write, it verifies the actual connected database/role, the exact marker row and pgvector availability through SELECT statements. Later sync/async connection entry points reject other DSNs or target overrides. These are safeguards, not permission to point destructive fixtures at any existing database. No database teardown is provisioned or executed automatically.

After provisioning and confirming disposability, run the complete suite from `backend/`:

```powershell
.\venv\Scripts\python.exe -m pytest tests -q --tb=short -p no:cacheprovider
```

Do not interpret collection or the independent pass count as evidence that the blocked tests now pass. Persistence/cache behavior, account seeding, database concurrency and revised integration fixtures must be diagnosed on that disposable server if they fail.

## Preserved concurrent changes

The repository was already dirty. Snapshot comparisons also found changes outside this pass in `app/main.py`, `app/services/claims_guidance_service.py`, `app/api/v1/endpoints/auth.py`, `app/api/v1/endpoints/policies.py` and `tests/test_production_security.py`. Those files were not written by this pass and were preserved. Results describe the tested snapshot; no frontend files, environment files, authentication controls or insurance rules were changed by this pass.

## Exact blocked PostgreSQL test IDs

- `tests/test_appeal_generator.py::test_appeal_api_endpoints`
- `tests/test_audit_api_and_isolation.py::test_audit_tenant_isolation`
- `tests/test_audit_api_and_isolation.py::test_audit_filtering_and_pagination`
- `tests/test_audit_api_and_isolation.py::test_audit_chain_cryptographic_verification`
- `tests/test_audit_api_and_isolation.py::test_real_policy_upload_creates_audit_record_with_clauses`
- `tests/test_claims_api_and_sandbox.py::test_claims_end_to_end_workflow`
- `tests/test_claims_api_and_sandbox.py::test_sandbox_scenarios_deterministic`
- `tests/test_claims_api_and_sandbox.py::test_claim_create_with_edited_line_items`
- `tests/test_claims_api_and_sandbox.py::test_claim_not_found_errors`
- `tests/test_claims_guidance.py::test_guidance_for_existing_claim_endpoint`
- `tests/test_comparison.py::test_comparison_api_endpoints`
- `tests/test_cookie_auth_csrf.py::test_login_issues_secure_httponly_and_csrf_cookies`
- `tests/test_cookie_auth_csrf.py::test_demo_login_issues_auth_and_csrf_cookies`
- `tests/test_cookie_auth_csrf.py::test_session_restoration_via_cookie`
- `tests/test_coverage_gap.py::test_coverage_gap_analyze_api_endpoint`
- `tests/test_coverage_gap.py::test_coverage_api_reports_unavailable_for_incomplete_extraction`
- `tests/test_coverage_gap.py::test_policy_coverage_report_endpoint`
- `tests/test_coverage_gap.py::test_coverage_gap_sample_policy_hydration`
- `tests/test_milestone6_security_audit_pdf.py::test_production_mode_accepts_valid_token`
- `tests/test_milestone6_security_audit_pdf.py::test_tenant_isolation_cross_user_access_rejected`
- `tests/test_milestone6_security_audit_pdf.py::test_eob_pdf_export_success`
- `tests/test_milestone6_security_audit_pdf.py::test_appeal_pdf_reviewed_status_enforcement`
- `tests/test_milestone6_security_audit_pdf.py::test_comparison_pdf_export_success`
- `tests/test_milestone6_security_audit_pdf.py::test_audit_hash_chain_sequential_integrity`
- `tests/test_milestone6_security_audit_pdf.py::test_audit_api_verification_endpoint`
- `tests/test_persistence.py::test_policy_persistence_across_instances`
- `tests/test_persistence.py::test_claim_and_bill_persistence_across_instances`
- `tests/test_persistence.py::test_comparison_persistence_across_instances`
- `tests/test_persistence.py::test_audit_event_chain_continuity_across_instances`
- `tests/test_policy_upload_api.py::test_upload_valid_pdf`
- `tests/test_policy_upload_api.py::test_list_and_get_policy_endpoints`
- `tests/test_portfolio_analysis.py::test_portfolio_api_analyze_endpoint`
- `tests/test_qa_api.py::test_qa_ask_policy_not_found`
- `tests/test_qa_api.py::test_qa_ask_successful_workflow`
- `tests/test_qa_api.py::test_qa_ask_recovers_primary_care_clause_after_hybrid_miss`
- `tests/test_qa_api.py::test_qa_ask_silent_complete_policy_returns_not_specified`
- `tests/test_qa_api.py::test_qa_ask_gemini_unconfigured_safe_abstention`
- `tests/test_qa_api.py::test_qa_ask_provider_error_handled_safely`
- `tests/test_security_remediation.py::test_cross_user_policy_access_denied`
- `tests/test_security_remediation.py::test_claim_document_upload_rejects_unsupported_extensions`
- `tests/test_security_remediation.py::test_concurrent_audit_events_preserve_monotonic_hash_chain`
- `tests/test_security_remediation.py::test_cross_user_comparison_isolation`
