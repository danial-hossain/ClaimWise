# ClaimWise documentation

Current onboarding and repository organization:

- [Setup and validation](development/SETUP.md)
- [Refactor audit, file moves, and results](development/REPOSITORY_REFACTOR.md)
- [Deployment](deployment/README.md)
- [Current security implementation and limitations](security/IMPLEMENTATION.md)

Architecture and API references, retained from the project milestones:

- [Architecture](architecture/ARCHITECTURE.md)
- [Database schema](architecture/DATABASE_SCHEMA.md)
- [API specification](api/API_SPECIFICATION.md)
- [Claim workflow](development/CLAIM_WORKFLOW.md)

Submission and historical evidence, preserved rather than regenerated:

- [Security self-assessment](security/SECURITY_AND_COMPLIANCE_SELF_ASSESSMENT.md)
- [QA benchmark report](QA_40_BENCHMARK_REPORT.md) and [recorded metrics](qa_benchmark_results.json)
- [UI theme report](development/reports/UI_THEME_PART_1.md)
- [Wizard report, part 2](development/reports/UI_WIZARD_PART_2.md)
- [Wizard report, part 3](development/reports/UI_WIZARD_PART_3.md)
- [UI surfaces report](development/reports/UI_SURFACES_PART_4.md)
- `screenshots/`: screenshots, recordings, and verification reports referenced by those documents
- `schema/initial_schema.sql`: historical database design; active migrations remain under `backend/app/db/migrations/`

Historical documents describe their original milestones. In particular, older Supabase/RLS,
milestone status, auth, and validation claims may differ from the current PostgreSQL and
cookie-auth implementation. Use the current setup/security notes for onboarding.
