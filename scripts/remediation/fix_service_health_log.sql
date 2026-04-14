-- Remediation: drop the out-of-drift service_health_log table and recreate
-- it with the canonical schema from supabase/init.sql + alembic 001.
--
-- Context: the live VPS table had columns (service, response_time_ms,
-- error_message, created_at) from an older unknown migration, but
-- api/services/health_logger.py writes (service_name, status, latency_ms).
-- This caused "Health log error" spam every 60s and zero health history.
-- Historical rows are discarded (they were never written correctly).
--
-- Apply with:
--   docker exec -i ai-supabase-db psql -U postgres -d postgres \
--     < scripts/remediation/fix_service_health_log.sql

BEGIN;

DROP TABLE IF EXISTS public.service_health_log;

CREATE TABLE public.service_health_log (
    id           BIGSERIAL PRIMARY KEY,
    service_name TEXT NOT NULL,
    status       TEXT NOT NULL,
    latency_ms   DOUBLE PRECISION,
    checked_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_service_health_log_service    ON public.service_health_log(service_name);
CREATE INDEX idx_service_health_log_checked_at ON public.service_health_log(checked_at DESC);

ALTER TABLE public.service_health_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role access to service_health_log" ON public.service_health_log;
CREATE POLICY "Service role access to service_health_log"
    ON public.service_health_log FOR ALL USING (auth.role() = 'service_role');

COMMIT;
