# ClaimWise — Evidence-First AI Insurance Assistant

> **"Evidence first. If no proof, no answer."**

ClaimWise is an AI-powered insurance intelligence platform built for the **FinTechathon** competition. It transforms dense, jargon-laden insurance policies into actionable clarity while strictly guarding against AI hallucinations.

---

## 🛡️ Core Value Proposition

Most AI insurance bots guess or synthesize plausible-sounding answers. In insurance, a hallucinated benefit or misquoted exclusion leads to claim rejections, surprise medical bills, and financial hardship.

ClaimWise enforces an **Evidence-First Guarantee**:
1. **Verifiable Citations**: Every explanation, coverage determination, and exclusion warning is anchored to an exact clause reference and page citation in your policy contract.
2. **Deterministic Rules for Calculations**: Deductibles, out-of-pocket maximums, and co-insurance splits are computed by a deterministic mathematical rules engine—never by generative guesswork.
3. **Transparent Uncertainty**: When policy language is silent, ambiguous, or contradictory, ClaimWise explicitly states that no proof exists and generates precise questions to ask the insurer.
4. **Denial Investigation & Sandbox Filing**: Investigate insurer rejection codes against contract terms and simulate claims in a safe mock sandbox environment before taking real-world action.

---

## 🏛️ System Architecture & Stack

### Frontend
- **Framework**: Next.js 15+ (App Router)
- **Language**: TypeScript (Strict mode)
- **Styling**: Tailwind CSS with fintech-grade design tokens
- **Features**: Live backend health & readiness telemetry, 6 modular navigation views, responsive dashboards, zero-fabrication empty states.

### Backend
- **Framework**: FastAPI (Python 3.13)
- **Settings & Validation**: Pydantic v2 & `pydantic-settings`
- **ASGI Server**: Uvicorn
- **HTTP Client & Testing**: HTTPX & Pytest Asyncio
- **Decoupled Architecture**: Starts gracefully without external keys; provides detailed subsystem diagnostic telemetry via `/api/v1/ready`.

### Database & Security
- **Engine**: Supabase PostgreSQL
- **Vectors**: `pgvector` with HNSW indexing for 1024-dimensional BGE-M3 embeddings
- **Authorization**: PostgreSQL **Row Level Security (RLS)** with explicit user ownership policies (`auth.uid() = user_id`)
- **Auditability**: Immutable append-only audit trail and explicit user consent tracking

### Future AI Pipeline (Milestone 2+)
- **LLM**: Google Gemini API with evidence-constrained reasoning
- **Embeddings**: BGE-M3 dense vectors (1024 dimensions)
- **Retrieval**: Hybrid search combining BM25 keyword matching and cosine vector similarity
- **Document Processing**: PyMuPDF with OCR fallback for scanned contracts

---

## 📂 Repository Structure

```
ClaimWise/
├── frontend/                # Next.js App Router, TypeScript & Tailwind CSS
│   ├── src/
│   │   ├── app/             # Application routes & layouts
│   │   └── components/      # UI components & telemetry widgets
│   ├── package.json
│   └── tsconfig.json
├── backend/                 # FastAPI modular application
│   ├── app/
│   │   ├── api/             # API v1 endpoints & router
│   │   ├── core/            # Config, security, exception handlers
│   │   ├── db/              # Session manager & migrations
│   │   ├── models/          # Domain models & enums
│   │   ├── schemas/         # Pydantic request/response models
│   │   └── services/        # Health diagnostics & business logic
│   ├── tests/               # Pytest automated test suite
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Backend environment template
├── docs/                    # Architecture, API, and Schema specifications
│   ├── ARCHITECTURE.md
│   ├── API_SPECIFICATION.md
│   ├── DATABASE_SCHEMA.md
│   └── schema/              # Version-controlled SQL migrations
├── output.txt               # Milestone handoff & audit report for AI pairing
├── .gitignore
└── README.md
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python**: 3.11+ (Python 3.13 recommended)
- **Node.js**: v18+ (Node.js v22 recommended)
- **npm**: 9+

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env

# Run automated tests
pytest -v

# Start FastAPI development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Base URL: `http://127.0.0.1:8000`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/v1/health`
- Readiness Check: `http://127.0.0.1:8000/api/v1/ready`

### 3. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Copy environment configuration
cp .env.example .env.local

# Run frontend development server
npm run dev
```
- Frontend Web App: `http://localhost:3000`

---

## 🔒 Security Principles

1. **Zero Secrets in Code**: All API keys, passwords, and service-role secrets are managed exclusively through environment variables.
2. **Never Trust Client User IDs**: User identity is verified strictly server-side through Supabase JWT tokens. Client-provided user IDs in request bodies are ignored.
3. **Row Level Security (RLS)**: Enforced at the PostgreSQL layer. Non-permissive policies prevent cross-tenant data leakage even in the event of an application-layer bug.
4. **Untrusted Uploads**: Uploaded policy PDFs and claim receipts are validated for MIME type, file size, and hashed with SHA-256 before extraction.
5. **No Production Insurer Submissions**: Live claim submissions are prohibited. Claim workflows execute against mock sandbox insurance gateways.

---

## 📋 Milestone Status

| Component | Status | Notes |
| :--- | :--- | :--- |
| **FastAPI Backend Core** | **DONE** | Modular architecture, configuration, error handling, CORS |
| **Liveness & Readiness Endpoints** | **DONE** | `/api/v1/health` & `/api/v1/ready` reporting subsystem states |
| **Backend Test Suite** | **DONE** | 5 automated tests passing with zero warnings |
| **Database Schema & Migrations** | **DONE** | 8 tables with RLS policies, pgvector indexes |
| **Next.js Frontend Foundation** | **DONE** | App Router, TypeScript, Tailwind CSS, 6 navigation views |
| **Telemetry & Health Widget** | **DONE** | Real-time frontend connectivity check with backend |
| **Supabase Live Connection** | **BLOCKED** | Pending user-provided Supabase project credentials |
| **Gemini AI / Hybrid RAG** | **NOT STARTED** | Staged for Milestone 2 (Document parsing & embedding engine) |

---

## 📄 License
FinTechathon Competition Project — Proprietary & Confidential.
