# Security implementation notes

These notes describe the current files; they do not claim a completed production security audit.
The earlier [self-assessment](SECURITY_AND_COMPLIANCE_SELF_ASSESSMENT.md) is retained as historical evidence.

The newer [production security audit and verification report](PRODUCTION_AUDIT_2026-10-16.md)
supersedes the refactor-era implementation inventory below. It lists actual test results,
remaining integration/deployment limitations, and administrator actions.

- `backend/app/core/security.py` owns token verification, authenticated-user dependencies,
  cookie/session helpers, CSRF validation, and Origin checks. These controls were not merged or moved.
- `frontend/src/lib/api.ts` owns the existing cookie-aware API client, CSRF bootstrap, and
  legacy localStorage-token cleanup. Its behavior was not changed by the repository refactor.
- `backend/app/api/v1/endpoints/auth.py` owns the current login, session-restoration, and account endpoints.
- Ownership and permission checks remain explicit in the API/repository paths where they already exist.
- `backend/app/services/audit_service.py`, `db/audit_repo.py`, and the persistent store maintain the
  existing audit chain. Their formulas, transaction handling, and storage behavior are unchanged.
- PII handling, file validation, evidence verification, and insurance arithmetic remain in their
  existing domain services. No prompt, retrieval algorithm, or coverage rule was rewritten.

Production settings validate a non-default JWT secret and a configured database URL. HTTPS,
cookie forwarding, trusted frontend origins, secret management, database permissions, and
operational monitoring still require deployment-specific verification. Existing development
and legacy compatibility paths are preserved; this refactor does not certify them for production.

No real environment files, uploads, databases, sample PDFs, or saved user records were deleted.
The full backend validation used disabled database/AI credentials, so its integration failures
must not be presented as a successful security or persistence certification.
