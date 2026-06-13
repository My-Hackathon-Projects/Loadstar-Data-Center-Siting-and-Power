-- Add job-state columns to optimization_runs so the async endpoint can persist
-- pending/running/completed/failed transitions, capture solver wall-clock, and
-- correlate runs with the request_id from the structured logs.

ALTER TABLE optimization_runs
    ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'
    CHECK (status IN ('pending','running','completed','failed'));

ALTER TABLE optimization_runs ADD COLUMN started_at TEXT;
ALTER TABLE optimization_runs ADD COLUMN completed_at TEXT;
ALTER TABLE optimization_runs ADD COLUMN error_message TEXT;
ALTER TABLE optimization_runs ADD COLUMN solve_ms REAL;
ALTER TABLE optimization_runs ADD COLUMN request_id TEXT;
