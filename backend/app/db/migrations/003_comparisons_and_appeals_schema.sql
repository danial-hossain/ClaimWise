-- ==============================================================================
-- CLAIMWISE DATABASE MIGRATION 003: MULTI-POLICY COMPARISONS & APPEAL DRAFTS
-- ==============================================================================
-- Adds:
-- 1. public.comparisons table for multi-policy side-by-side comparison snapshots.
-- 2. appeal_draft JSONB column on public.claims for editable, evidence-grounded denial appeals.
-- ==============================================================================

-- 1. Create comparisons table if it does not exist
CREATE TABLE IF NOT EXISTS public.comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    policy_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    comparison_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    cost_simulation JSONB,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

-- Index for user comparisons
CREATE INDEX IF NOT EXISTS idx_comparisons_user_id ON public.comparisons(user_id);

-- 2. Add appeal_draft column to public.claims
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS appeal_draft JSONB;
