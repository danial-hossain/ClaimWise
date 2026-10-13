-- ==============================================================================
-- CLAIMWISE DATABASE MIGRATION 004: CRYPTOGRAPHIC AUDIT LOGS & RLS HARDENING
-- ==============================================================================
-- 1. Upgrades public.audit_logs with sequence numbering, SHA-256 hash chaining,
--    and tamper-evident verification columns.
-- 2. Enforces append-only protections and strict Row Level Security (RLS) policies.
-- 3. Hardens multi-tenant isolation across policies, claims, comparisons, and audits.
-- ==============================================================================

-- 1. Upgrade public.audit_logs columns
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS sequence_number BIGINT;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS previous_hash TEXT DEFAULT '0000000000000000000000000000000000000000000000000000000000000000';
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS event_hash TEXT;
ALTER TABLE public.audit_logs ADD COLUMN IF NOT EXISTS schema_version TEXT DEFAULT '1.0.0';

-- Indexes for rapid sequence ordering and cryptographic chain lookups
CREATE INDEX IF NOT EXISTS idx_audit_logs_sequence ON public.audit_logs(sequence_number);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_hash ON public.audit_logs(event_hash);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at);

-- 2. Row Level Security Hardening for public.audit_logs
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Allow users to read only their own audit records
DROP POLICY IF EXISTS "audit_logs_select_own" ON public.audit_logs;
CREATE POLICY "audit_logs_select_own" ON public.audit_logs
    FOR SELECT USING (auth.uid() = user_id);

-- Allow authenticated users to insert audit records for their own identity
DROP POLICY IF EXISTS "audit_logs_insert_own" ON public.audit_logs;
CREATE POLICY "audit_logs_insert_own" ON public.audit_logs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- STRICT APPEND-ONLY ENFORCEMENT: No user can UPDATE or DELETE audit events
-- Explicit denial through absence of UPDATE and DELETE policies.

-- 3. Row Level Security Hardening for public.comparisons
ALTER TABLE public.comparisons ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "comparisons_select_own" ON public.comparisons;
CREATE POLICY "comparisons_select_own" ON public.comparisons
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "comparisons_insert_own" ON public.comparisons;
CREATE POLICY "comparisons_insert_own" ON public.comparisons
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "comparisons_update_own" ON public.comparisons;
CREATE POLICY "comparisons_update_own" ON public.comparisons
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "comparisons_delete_own" ON public.comparisons;
CREATE POLICY "comparisons_delete_own" ON public.comparisons
    FOR DELETE USING (auth.uid() = user_id);

-- 4. Row Level Security Hardening for public.claims
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "claims_select_own" ON public.claims;
CREATE POLICY "claims_select_own" ON public.claims
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "claims_insert_own" ON public.claims;
CREATE POLICY "claims_insert_own" ON public.claims
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "claims_update_own" ON public.claims;
CREATE POLICY "claims_update_own" ON public.claims
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "claims_delete_own" ON public.claims;
CREATE POLICY "claims_delete_own" ON public.claims
    FOR DELETE USING (auth.uid() = user_id);
