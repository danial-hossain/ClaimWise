# ClaimWise Technical Architecture

## Core Philosophy: Evidence First
> **"Evidence first. If no proof, no answer."**

ClaimWise is designed to solve one of the most critical vulnerabilities in automated insurance assistance: **unsupported hallucinations**. When insurance coverage, deductibles, and claim disputes are evaluated, an incorrect guess can lead to severe financial consequences for users.

Therefore, ClaimWise operates under strict evidence-first guardrails:
1. **Verifiable Citations**: Every claim eligibility decision, coverage statement, or exclusion warning must cite an exact clause identifier, document page number, and quoted excerpt from policy documents.
2. **Deterministic Rules Engine for Calculations**: Out-of-pocket expenses, deductibles, co-pays, and remaining annual caps are calculated using a deterministic Python mathematical engine rather than relying on LLM arithmetic.
3. **Uncertainty & Gap Handling**: If policy language is ambiguous, missing, or contradictory, ClaimWise explicitly states that proof is absent and suggests specific clarifying questions for the insurer instead of speculating.

---

## Architecture Diagram

```
+---------------------------------------------------------------------------------+
|                                 USER CLIENT                                     |
|                       Next.js (App Router, TypeScript)                          |
|    - Dashboard          - AI Workspace        - Policy Explorer                 |
|    - Claims Hub         - Policy Comparator   - Security Settings               |
+---------------------------------------------------------------------------------+
                                       |
                                       | HTTPS (REST / SSE)
                                       v
+---------------------------------------------------------------------------------+
|                               FASTAPI BACKEND                                   |
|                                                                                 |
|  +---------------------------------------------------------------------------+  |
|  | Core & Security:                                                          |  |
|  | - Config (pydantic-settings)      - CORS Policy                           |  |
|  | - Supabase JWT Validator          - Strict Auth Guards                    |  |
|  +---------------------------------------------------------------------------+  |
|                                                                                 |
|  +---------------------------------------------------------------------------+  |
|  | Application Services:                                                     |  |
|  | - Health & Readiness Monitor      - Policy Extraction (PyMuPDF / OCR)     |  |
|  | - Hybrid Retrieval (BM25 + Vector) - Deterministic Cost Rules Engine      |  |
|  | - Claim Denial Analyzer           - Sandbox Insurer Mock Gateway          |  |
|  +---------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------+
                      |                                         |
                      | PostgreSQL / pgvector                   | Google AI Studio
                      v                                         v
+---------------------------------------------+   +-------------------------------+
|             SUPABASE INFRASTRUCTURE        |   |       GEMINI LLM ENGINE       |
|                                             |   |                               |
|  - PostgreSQL with Row Level Security (RLS) |   | - Evidence-grounded reasoning |
|  - pgvector (1024 dims for BGE-M3 vectors)  |   | - Citation-constrained output |
|  - Supabase Auth (JWT token issuance)       |   | - Structured JSON extraction  |
|  - Storage (Encrypted PDF document bucket)  |   |                               |
+---------------------------------------------+   +-------------------------------+
```

---

## Subsystem Responsibilities

### 1. Frontend (Next.js 15+ App Router, TypeScript, Tailwind CSS)
- **Design System**: Fintech-grade high contrast, emerald/indigo/slate color palette, accessible data tables, and status indicators.
- **Client Connectivity Health**: Real-time ping to backend `/api/v1/health` and `/api/v1/ready` displaying subsystem health directly in the UI.
- **Six Application Domains**:
  1. **Dashboard**: High-level overview of policies, pending claims, filing deadlines, and exclusion alerts.
  2. **AI Workspace**: Interactive evidence workspace where users query policy clauses with side-by-side citation highlights.
  3. **My Policies**: Uploaded policy documents, categorized by type (health, auto, home, etc.) with deductible and out-of-pocket breakdowns.
  4. **My Claims**: Active claims, dispute packages, denial letters, and sandbox submission simulations.
  5. **Compare & Choose**: Multi-policy side-by-side matrix contrasting exclusions, co-insurance, and network rules.
  6. **Settings & Security**: Data retention consents, API status, and cryptographic audit logs.

### 2. Backend (FastAPI, Python 3.13, Pydantic)
- **Decoupled Startup**: Starts immediately in all environments regardless of whether external API keys or DB credentials have been entered. Unconfigured optional services are reported via `/api/v1/ready`.
- **CORS Protection**: Origin-checked middleware preventing unauthorized cross-origin requests.
- **Deterministic Math Engine**: All financial calculations (deductible remaining, coinsurance % split, out-of-pocket accumulation) are executed in pure Python code using integer cents to guarantee mathematical correctness.
- **Untrusted File Pipeline**: Incoming PDFs and receipts are treated as untrusted user input, checked for MIME type, sanitized, and stored with SHA-256 integrity hashes.

### 3. Database & Security Model (Supabase PostgreSQL + RLS)
- **Row Level Security (RLS)**: Enforced at the database engine level. Every table requires authenticated user validation through `auth.uid() = user_id`.
- **No Client Trust**: Client-submitted user IDs in query parameters or payloads are never trusted. Identity is verified exclusively server-side via Supabase JWT tokens.
- **pgvector Integration**: Enables cosine similarity searches against 1024-dimensional embeddings generated by BGE-M3 for deep semantic clause matching.
- **Audit Logging**: Comprehensive, append-only logs for all sensitive actions (document uploads, claims generated, rules evaluated).

### 4. Sandbox Insurer Integration Principle
- Live claims are never submitted directly to insurance carriers without explicit user confirmation.
- Submissions target a mock sandbox insurer simulating real EDI 837P / remittance advice response codes (e.g. `APPROVED_SIMULATION`, `DENIED_EXCLUSION_SIMULATION`).

### 5. Multi-Policy Comparison Engine (Milestone 5)
- Cross-examines 2 to 4 authorized insurance policies across core dimensions: Deductibles, Coinsurance %, OOP Max, Copays, Exclusions, Network Tiers, Prior Authorization, and Waiting Periods.
- Transparent status tracking for every attribute: `verified`, `unknown` (never defaulted to zero), `conflicting`, or `not_applicable`.
- Uses deterministic integer-cents rules engine for illustrative annual cost comparisons under explicit user-defined assumptions.
- Summarizes factual trade-offs (e.g. deductible vs coinsurance breakeven spend points) without declaring an unsubstantiated "best" policy.

### 6. Evidence-Based Denial Appeal Generator (Milestone 5)
- Inspects denied or simulated-denied claims, remittance codes, itemized bill line items, and retrieved policy clauses.
- Generates structured, editable appeal drafts containing: Issue statement, factual record, exact cited policy clauses, rebuttal argument, missing documentation checklist, requested relief, and prominent review disclaimers.
- Strict citation validation: All policy assertions cite verified clause IDs, page numbers, and verbatim quotes.
- Prompt injection defense: Treats user inputs and uploaded records as untrusted data, never instructions.
- Distinguishes `generated`, `user_edited`, and `exported` states. No real insurer transmission.

### 7. Server-Side PDF Export System (Milestone 6)
- **Engine**: Headless, server-side document rendering using PyMuPDF (`pymupdf`).
- **Memory Safety & Privacy**: In-memory byte stream generation (`doc.tobytes()`) returned with streaming HTTP responses; zero persistence of private consumer medical documents in publicly served directories.
- **Three Export Pipelines**:
  1. **Explanation of Benefits (EOB)**: Itemized billed charges, allowed amounts, cost-sharing breakdown (deductible, copay, coinsurance), illustrative insurer share, mathematical audit verification, citations, and simulation disclaimer banner.
  2. **Reviewed Denial Appeal Letter**: Enforces user-reviewed state requirement (`user_edited` or `exported`). Renders formal consumer advocacy letter, verified citations, missing-evidence submission checklist, and legal review disclaimers.
  3. **Multi-Policy Comparison Report**: Multi-column matrix contrasting verified contract attributes across 2–4 plans with explicit evidence statuses, cost assumptions, and neutral trade-off analysis.

### 8. Cryptographic Audit Trail & Production Hardening (Milestone 6)
- **RFC 7519 Server-Side Authentication**: Cryptographic verification of Supabase access tokens using HS256 HMAC-SHA256 against `SUPABASE_JWT_SECRET`. Rejects expired, malformed, or untrusted tokens. Disables `dev-user-001` fallback in `ENVIRONMENT=production`. Fails closed if production credentials are missing.
- **Strict Tenant Isolation**: Server-side resource ownership checks on every protected endpoint (policies, claims, bills, EOBs, appeals, comparisons, and audit records). Cross-tenant access attempts return HTTP 403 Forbidden.
- **Tamper-Evident SHA-256 Hash Chaining**: Every security-critical action (uploads, adjudications, appeal edits, PDF exports) is recorded as a sequentially numbered event. Each event's payload is canonically serialized (RFC 8785) with the predecessor event's hash into a cryptographic digest.
- **Mathematical Integrity Verifier**: `POST /api/v1/audit/verify` detects tampered payloads, altered metadata, deleted records, broken previous-hash links, or sequence gaps.
- **Automated PII/PHI Redaction**: Metadata is sanitized recursively to redact passwords, tokens, API keys, SSNs, and raw clinical notes.

