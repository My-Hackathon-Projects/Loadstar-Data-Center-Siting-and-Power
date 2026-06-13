-- Postgres equivalent of 003_optimization_runs_status_sqlite.sql.
-- Adds the same columns; types match the rest of the Postgres schema.

ALTER TABLE optimization_runs
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed';

ALTER TABLE optimization_runs DROP CONSTRAINT IF EXISTS optimization_runs_status_check;
ALTER TABLE optimization_runs
    ADD CONSTRAINT optimization_runs_status_check
    CHECK (status IN ('pending', 'running', 'completed', 'failed'));

ALTER TABLE optimization_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE optimization_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE optimization_runs ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE optimization_runs ADD COLUMN IF NOT EXISTS solve_ms DOUBLE PRECISION;
ALTER TABLE optimization_runs ADD COLUMN IF NOT EXISTS request_id TEXT;
