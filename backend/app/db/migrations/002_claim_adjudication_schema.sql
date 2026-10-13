-- ==============================================================================
-- CLAIMWISE DATABASE MIGRATION 002: CLAIM ADJUDICATION & EOB STRUCTURE
-- ==============================================================================
-- Adds JSONB storage for itemized bill line items, adjudicated clause evaluations,
-- structured Explanation of Benefits (EOB) payloads, and mock sandbox submission audits.
-- ==============================================================================

ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS line_items JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS adjudicated_items JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS eob_data JSONB;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS sandbox_submission JSONB;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS bill_document_hash TEXT;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS bill_document_name TEXT;

-- Index on bill document hash for rapid claim lookups
CREATE INDEX IF NOT EXISTS idx_claims_bill_document_hash ON public.claims(bill_document_hash);
