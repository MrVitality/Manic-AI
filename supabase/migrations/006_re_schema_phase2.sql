-- =============================================================================
-- Phase 2 — Real Estate Content Machine schema
-- =============================================================================
-- Adds the listings, content_calendar, and market_snapshots tables to the re.*
-- schema. Ported from ~/Downloads/Lead and Content Machine/01_schema.sql with
-- Phase 2 additions: fair_housing_verdict, compliance_checked_at,
-- fair_housing_notes, approved_by, approved_at, rag_collection_id link.
--
-- Idempotent: safe to re-run.
-- =============================================================================

BEGIN;

-- =============================================================================
-- re.listings -- property inventory + scraped/imported/manual listings
-- =============================================================================
CREATE TABLE IF NOT EXISTS re.listings (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    address           TEXT NOT NULL,
    city              TEXT,
    state             TEXT DEFAULT 'NY',
    zip               TEXT,
    beds              INTEGER,
    baths             NUMERIC(3,1),
    sqft              INTEGER,
    list_price        INTEGER,
    list_date         DATE,
    status            TEXT CHECK (status IN ('active','pending','sold','expired','withdrawn','draft')) DEFAULT 'draft',
    days_on_market    INTEGER,
    key_features      TEXT[],
    description       TEXT,
    mls_number        TEXT,
    agent_notes       TEXT,
    source            TEXT CHECK (source IN ('manual','scraper','idx','import')) DEFAULT 'manual',
    rag_collection_id UUID,
    content_generated BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listings_status     ON re.listings(status);
CREATE INDEX IF NOT EXISTS idx_listings_city       ON re.listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_source     ON re.listings(source);
CREATE INDEX IF NOT EXISTS idx_listings_mls_number ON re.listings(mls_number);
CREATE INDEX IF NOT EXISTS idx_listings_created    ON re.listings(created_at DESC);

DROP TRIGGER IF EXISTS listings_updated_at ON re.listings;
CREATE TRIGGER listings_updated_at
    BEFORE UPDATE ON re.listings
    FOR EACH ROW EXECUTE FUNCTION re.update_updated_at();

-- =============================================================================
-- re.content_calendar -- generated + manual content pieces for all platforms
-- Phase 2 additions: fair_housing_* fields for compliance audit trail.
-- =============================================================================
CREATE TABLE IF NOT EXISTS re.content_calendar (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id            UUID REFERENCES re.listings(id) ON DELETE SET NULL,
    scheduled_date        DATE,
    platform              TEXT CHECK (platform IN (
                              'instagram','facebook','linkedin','email',
                              'tiktok','youtube','mls','reels','all'
                          )),
    content_type          TEXT CHECK (content_type IN (
                              'listing','market_update','evergreen',
                              'educational','personal','testimonial'
                          )),
    status                TEXT CHECK (status IN (
                              'draft','flagged','blocked','approved',
                              'scheduled','posted','archived'
                          )) DEFAULT 'draft',
    title                 TEXT,
    content               TEXT NOT NULL,
    hashtags              TEXT,
    image_notes           TEXT,
    source_listing        TEXT,
    generated_by          TEXT,
    posted_at             TIMESTAMPTZ,
    engagement_notes      TEXT,
    -- Fair Housing audit trail (Phase 2)
    compliance_checked_at TIMESTAMPTZ,
    fair_housing_notes    TEXT,
    fair_housing_verdict  TEXT CHECK (fair_housing_verdict IN ('pass','warn','block')),
    approved_by           TEXT,
    approved_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_content_status          ON re.content_calendar(status);
CREATE INDEX IF NOT EXISTS idx_content_platform        ON re.content_calendar(platform);
CREATE INDEX IF NOT EXISTS idx_content_scheduled       ON re.content_calendar(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_content_type            ON re.content_calendar(content_type);
CREATE INDEX IF NOT EXISTS idx_content_listing_id      ON re.content_calendar(listing_id);
CREATE INDEX IF NOT EXISTS idx_content_fh_verdict      ON re.content_calendar(fair_housing_verdict);
CREATE INDEX IF NOT EXISTS idx_content_created         ON re.content_calendar(created_at DESC);

-- =============================================================================
-- re.market_snapshots -- weekly scraped market stats (populated by n8n WF07)
-- =============================================================================
CREATE TABLE IF NOT EXISTS re.market_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date       DATE NOT NULL,
    area                TEXT NOT NULL,
    median_price        INTEGER,
    avg_price           INTEGER,
    median_dom          INTEGER,
    avg_dom             INTEGER,
    active_listings     INTEGER,
    new_listings        INTEGER,
    pending_listings    INTEGER,
    sold_listings       INTEGER,
    months_of_supply    NUMERIC(4,2),
    list_to_sale_ratio  NUMERIC(5,3),
    raw_data            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_date ON re.market_snapshots(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_area ON re.market_snapshots(area);

-- =============================================================================
-- Allow re.interactions.lead_id to be NULL so system events (content
-- generation, market snapshots, admin actions) can log without a lead.
-- The original CHECK constraint requires lead_id OR contact_id; we relax it
-- to allow neither for system-wide events.
-- =============================================================================
ALTER TABLE re.interactions
    DROP CONSTRAINT IF EXISTS interactions_check;

ALTER TABLE re.interactions
    DROP CONSTRAINT IF EXISTS re_interactions_check;

-- No constraint re-added -- system events (workflow_id-anchored) can have
-- both lead_id and contact_id NULL, only workflow_id identifying them.

-- =============================================================================
-- Helper views
-- =============================================================================
CREATE OR REPLACE VIEW re.v_content_queue AS
SELECT c.*
FROM re.content_calendar c
WHERE c.status = 'approved'
  AND (c.scheduled_date IS NULL OR c.scheduled_date <= CURRENT_DATE)
ORDER BY c.scheduled_date ASC NULLS LAST, c.created_at ASC;

CREATE OR REPLACE VIEW re.v_content_this_week AS
SELECT
    platform,
    content_type,
    status,
    COUNT(*) AS count
FROM re.content_calendar
WHERE created_at >= DATE_TRUNC('week', NOW())
GROUP BY platform, content_type, status
ORDER BY platform, status;

CREATE OR REPLACE VIEW re.v_compliance_flags AS
SELECT
    id, listing_id, platform, content_type,
    status, fair_housing_verdict, fair_housing_notes,
    compliance_checked_at,
    LEFT(content, 200) AS content_preview,
    created_at
FROM re.content_calendar
WHERE fair_housing_verdict IN ('warn', 'block')
ORDER BY
    CASE fair_housing_verdict
        WHEN 'block' THEN 0
        WHEN 'warn' THEN 1
        ELSE 2
    END,
    created_at DESC;

CREATE OR REPLACE VIEW re.v_market_latest AS
SELECT DISTINCT ON (area)
    area, snapshot_date, median_price, avg_price, median_dom, avg_dom,
    active_listings, months_of_supply, list_to_sale_ratio
FROM re.market_snapshots
ORDER BY area, snapshot_date DESC;

-- =============================================================================
-- RLS policies (single-tenant, service role only)
-- =============================================================================
ALTER TABLE re.listings         ENABLE ROW LEVEL SECURITY;
ALTER TABLE re.content_calendar ENABLE ROW LEVEL SECURITY;
ALTER TABLE re.market_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role access to re.listings" ON re.listings;
CREATE POLICY "Service role access to re.listings" ON re.listings
    FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Service role access to re.content_calendar" ON re.content_calendar;
CREATE POLICY "Service role access to re.content_calendar" ON re.content_calendar
    FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Service role access to re.market_snapshots" ON re.market_snapshots;
CREATE POLICY "Service role access to re.market_snapshots" ON re.market_snapshots
    FOR ALL USING (auth.role() = 'service_role');

COMMIT;
