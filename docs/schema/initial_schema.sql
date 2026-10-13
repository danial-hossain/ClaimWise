-- ==============================================================================
-- ClaimWise Database Schema Migration 001
-- Initial schema: Profiles, Policies, Policy Chunks, Claims, Documents,
-- Comparisons, Audit Logs, and User Consents with Row Level Security (RLS).
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector"; -- pgvector for BGE-M3 (1024 dims) embeddings

-- 2. USER PROFILES
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 3. POLICIES
CREATE TABLE IF NOT EXISTS public.policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    insurer_name TEXT NOT NULL,
    policy_number TEXT,
    policy_type TEXT NOT NULL CHECK (policy_type IN ('health', 'auto', 'home', 'life', 'travel', 'disability', 'other')),
    coverage_start_date DATE,
    coverage_end_date DATE,
    deductible_amount_cents BIGINT DEFAULT 0 CHECK (deductible_amount_cents >= 0),
    out_of_pocket_max_cents BIGINT DEFAULT 0 CHECK (out_of_pocket_max_cents >= 0),
    annual_limit_cents BIGINT CHECK (annual_limit_cents IS NULL OR annual_limit_cents >= 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled', 'draft')),
    raw_document_url TEXT,
    document_sha256 TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 4. POLICY CHUNKS (For Evidence Retrieval and BGE-M3 Embeddings)
CREATE TABLE IF NOT EXISTS public.policy_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL REFERENCES public.policies(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    page_number INTEGER CHECK (page_number >= 1),
    section_heading TEXT,
    clause_identifier TEXT,
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding vector(1024), -- 1024-dimensional vector for BGE-M3
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_policy_chunk_index UNIQUE (policy_id, chunk_index)
);

-- 5. CLAIMS
CREATE TABLE IF NOT EXISTS public.claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    policy_id UUID REFERENCES public.policies(id) ON DELETE SET NULL,
    claim_reference TEXT,
    incident_date DATE NOT NULL,
    claimed_amount_cents BIGINT NOT NULL CHECK (claimed_amount_cents >= 0),
    approved_amount_cents BIGINT DEFAULT 0 CHECK (approved_amount_cents >= 0),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'evidence_gathering', 'analyzed', 'sandbox_submitted', 'insurer_rejected', 'in_dispute', 'approved', 'closed')),
    insurer_reason_code TEXT,
    insurer_denial_notes TEXT,
    ai_investigation_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 6. CLAIM DOCUMENTS
CREATE TABLE IF NOT EXISTS public.claim_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES public.claims(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL CHECK (document_type IN ('medical_bill', 'repair_estimate', 'denial_letter', 'receipt', 'police_report', 'appeal_letter', 'other')),
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size_bytes BIGINT CHECK (file_size_bytes >= 0),
    mime_type TEXT NOT NULL,
    ocr_extracted_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 7. COMPARISONS
CREATE TABLE IF NOT EXISTS public.comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    policy_ids UUID[] NOT NULL,
    comparison_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
    comparison_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 8. AUDIT LOGS
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,
    ip_address INET,
    user_agent TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- 9. USER CONSENTS
CREATE TABLE IF NOT EXISTS public.consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    consent_type TEXT NOT NULL CHECK (consent_type IN ('data_processing', 'ai_analysis', 'sandbox_claim_submission', 'terms_of_service')),
    granted BOOLEAN NOT NULL DEFAULT true,
    policy_version TEXT NOT NULL,
    ip_address INET,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    revoked_at TIMESTAMPTZ
);

-- ==============================================================================
-- INDEXES
-- ==============================================================================

CREATE INDEX IF NOT EXISTS idx_policies_user_id ON public.policies(user_id);
CREATE INDEX IF NOT EXISTS idx_policies_status ON public.policies(status);
CREATE INDEX IF NOT EXISTS idx_policy_chunks_policy_id ON public.policy_chunks(policy_id);
CREATE INDEX IF NOT EXISTS idx_claims_user_id ON public.claims(user_id);
CREATE INDEX IF NOT EXISTS idx_claims_policy_id ON public.claims(policy_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON public.claims(status);
CREATE INDEX IF NOT EXISTS idx_claim_documents_claim_id ON public.claim_documents(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_documents_user_id ON public.claim_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_user_id ON public.comparisons(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_consents_user_id ON public.consents(user_id);

-- HNSW Vector Index for Cosine Similarity Searches on Policy Chunks
CREATE INDEX IF NOT EXISTS idx_policy_chunks_embedding
    ON public.policy_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policy_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comparisons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consents ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
CREATE POLICY "profiles_select_own" ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "profiles_update_own" ON public.profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "profiles_insert_own" ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- Policies Policies
CREATE POLICY "policies_select_own" ON public.policies FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "policies_insert_own" ON public.policies FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "policies_update_own" ON public.policies FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "policies_delete_own" ON public.policies FOR DELETE USING (auth.uid() = user_id);

-- Policy Chunks Policies
CREATE POLICY "policy_chunks_select_own" ON public.policy_chunks
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM public.policies WHERE public.policies.id = public.policy_chunks.policy_id AND public.policies.user_id = auth.uid())
    );
CREATE POLICY "policy_chunks_insert_own" ON public.policy_chunks
    FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM public.policies WHERE public.policies.id = public.policy_chunks.policy_id AND public.policies.user_id = auth.uid())
    );
CREATE POLICY "policy_chunks_delete_own" ON public.policy_chunks
    FOR DELETE USING (
        EXISTS (SELECT 1 FROM public.policies WHERE public.policies.id = public.policy_chunks.policy_id AND public.policies.user_id = auth.uid())
    );

-- Claims Policies
CREATE POLICY "claims_select_own" ON public.claims FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "claims_insert_own" ON public.claims FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "claims_update_own" ON public.claims FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "claims_delete_own" ON public.claims FOR DELETE USING (auth.uid() = user_id);

-- Claim Documents Policies
CREATE POLICY "claim_documents_select_own" ON public.claim_documents FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "claim_documents_insert_own" ON public.claim_documents FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "claim_documents_delete_own" ON public.claim_documents FOR DELETE USING (auth.uid() = user_id);

-- Comparisons Policies
CREATE POLICY "comparisons_select_own" ON public.comparisons FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "comparisons_insert_own" ON public.comparisons FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "comparisons_delete_own" ON public.comparisons FOR DELETE USING (auth.uid() = user_id);

-- Consents Policies
CREATE POLICY "consents_select_own" ON public.consents FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "consents_insert_own" ON public.consents FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Audit Logs Policies
CREATE POLICY "audit_logs_select_own" ON public.audit_logs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "audit_logs_insert" ON public.audit_logs FOR INSERT WITH CHECK (auth.uid() = user_id OR auth.uid() IS NULL);
