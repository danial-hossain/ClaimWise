-- Coverage workflow records use the existing PostgreSQL connection and server-verified owner.
CREATE TABLE IF NOT EXISTS coverage_analyses (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    data JSONB NOT NULL,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_coverage_analyses_owner_policy ON coverage_analyses(user_id, policy_id, created_at DESC);
