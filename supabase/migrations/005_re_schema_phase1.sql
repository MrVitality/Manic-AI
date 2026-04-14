-- =============================================================================
-- Phase 1 — Real Estate domain schema (contacts, leads, interactions, drips)
-- =============================================================================
-- Ported from ~/Downloads/Lead and Content Machine/01_schema.sql into a new
-- `re` schema so RE domain tables are namespaced away from `public.*` (API
-- internals) and `rag.*` (retrieval corpus).
--
-- Phase 1 scope: lead intake -> scoring -> drip nurture pipeline.
-- Phases 2-4 add: listings, content_calendar, market_snapshots, deals,
-- showings, offers.
--
-- Idempotent: safe to re-run. Uses IF NOT EXISTS / DROP POLICY IF EXISTS.
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS re;

-- =============================================================================
-- re.contacts -- canonical person record. FK target for leads/deals/etc.
-- =============================================================================
CREATE TABLE IF NOT EXISTS re.contacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name  TEXT,
    last_name   TEXT,
    email       TEXT,
    phone       TEXT,
    type        TEXT CHECK (type IN (
                    'buyer','seller','investor','tenant',
                    'landlord','vendor','referral','past_client','other'
                )) DEFAULT 'other',
    status      TEXT CHECK (status IN (
                    'lead','active','under_contract','closed','past_client','inactive'
                )) DEFAULT 'lead',
    tags        TEXT[],
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contacts_email  ON re.contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON re.contacts(status);
CREATE INDEX IF NOT EXISTS idx_contacts_type   ON re.contacts(type);

-- =============================================================================
-- re.leads -- raw lead intake (pre-qualified). One-way link to contacts
-- once qualified. Ported from L/C Machine schema with additions.
-- =============================================================================
CREATE TABLE IF NOT EXISTS re.leads (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id        UUID REFERENCES re.contacts(id) ON DELETE SET NULL,
    name              TEXT NOT NULL,
    email             TEXT,
    phone             TEXT,
    source            TEXT CHECK (source IN (
                          'zillow','facebook','website','referral',
                          'instagram','cold_outreach','open_house',
                          'seller_blueprint','landing_page','manual','other'
                      )),
    source_funnel     TEXT,
    message           TEXT,
    property_interest TEXT,
    timeline          TEXT,
    buyer_seller      TEXT CHECK (buyer_seller IN ('buyer','seller','both','unknown')),
    score             INTEGER CHECK (score >= 0 AND score <= 100),
    tier              TEXT CHECK (tier IN ('hot','warm','cold','converted','disqualified')),
    score_reasoning   TEXT,
    suggested_tone    TEXT,
    drip_stage        INTEGER DEFAULT 0,
    last_contacted    TIMESTAMPTZ,
    next_follow_up    TIMESTAMPTZ,
    notes             TEXT,
    tags              TEXT[],
    raw_payload       JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_tier           ON re.leads(tier);
CREATE INDEX IF NOT EXISTS idx_leads_score          ON re.leads(score DESC);
CREATE INDEX IF NOT EXISTS idx_leads_last_contact   ON re.leads(last_contacted);
CREATE INDEX IF NOT EXISTS idx_leads_next_followup  ON re.leads(next_follow_up);
CREATE INDEX IF NOT EXISTS idx_leads_source         ON re.leads(source);
CREATE INDEX IF NOT EXISTS idx_leads_created_at     ON re.leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_contact_id     ON re.leads(contact_id);

-- =============================================================================
-- re.interactions -- polymorphic touch log (lead / contact). Every email,
-- call, note, status change. Source of truth for activity timeline.
-- =============================================================================
CREATE TABLE IF NOT EXISTS re.interactions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id      UUID REFERENCES re.leads(id) ON DELETE CASCADE,
    contact_id   UUID REFERENCES re.contacts(id) ON DELETE CASCADE,
    type         TEXT CHECK (type IN (
                     'email_sent','email_received','sms_sent','sms_received',
                     'call','note','status_change','score_update','tier_change'
                 )),
    subject      TEXT,
    body         TEXT,
    direction    TEXT CHECK (direction IN ('outbound','inbound')),
    automated    BOOLEAN DEFAULT TRUE,
    workflow_id  TEXT,
    metadata     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (lead_id IS NOT NULL OR contact_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_interactions_lead_id    ON re.interactions(lead_id);
CREATE INDEX IF NOT EXISTS idx_interactions_contact_id ON re.interactions(contact_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON re.interactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_type       ON re.interactions(type);

-- =============================================================================
-- re.drip_sequences -- template library for drip cadences
-- =============================================================================
CREATE TABLE IF NOT EXISTS re.drip_sequences (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT NOT NULL,
    tier             TEXT NOT NULL,
    stage            INTEGER NOT NULL,
    delay_days       INTEGER NOT NULL,
    subject_template TEXT,
    body_template    TEXT,
    active           BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_drip_tier_stage ON re.drip_sequences(tier, stage);

-- Seed default sequences (idempotent via ON CONFLICT on tier+stage)
INSERT INTO re.drip_sequences (name, tier, stage, delay_days, subject_template, body_template) VALUES
('Warm Buyer Stage 1', 'warm', 0, 3,
 'Quick question about your home search, {{name}}',
 'Hi {{name}}, just following up on your interest in {{property_interest}}. The Capital Region market is moving fast right now — are you still actively looking? I have a few properties that might be a great fit.'),
('Warm Buyer Stage 2', 'warm', 1, 7,
 'Market update for {{property_interest}} area',
 'Hi {{name}}, I wanted to share a quick update on the {{property_interest}} market. Homes are averaging {{avg_dom}} days on market right now. Would you like to set up a quick call this week?'),
('Warm Buyer Stage 3', 'warm', 2, 14,
 'Checking in — still interested in buying in the Capital Region?',
 'Hi {{name}}, I know life gets busy. Just wanted to make sure you haven''t missed out on anything in the {{property_interest}} area. Let me know if your timeline has changed — happy to help whenever you''re ready.'),
('Cold Reactivation', 'cold', 0, 30,
 'Are you still thinking about buying/selling in the Capital Region?',
 'Hi {{name}}, it''s been a while since we connected. The market has shifted since we last spoke — I thought you might want an update. No pressure at all, just here when you''re ready.')
ON CONFLICT (tier, stage) DO NOTHING;

-- =============================================================================
-- Auto-update updated_at on leads/contacts
-- =============================================================================
CREATE OR REPLACE FUNCTION re.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS leads_updated_at ON re.leads;
CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON re.leads
    FOR EACH ROW EXECUTE FUNCTION re.update_updated_at();

DROP TRIGGER IF EXISTS contacts_updated_at ON re.contacts;
CREATE TRIGGER contacts_updated_at
    BEFORE UPDATE ON re.contacts
    FOR EACH ROW EXECUTE FUNCTION re.update_updated_at();

-- =============================================================================
-- Helper views
-- =============================================================================
CREATE OR REPLACE VIEW re.v_hot_leads AS
SELECT
    id, name, email, phone, source, source_funnel,
    property_interest, timeline, buyer_seller,
    score, score_reasoning, tier,
    last_contacted,
    EXTRACT(EPOCH FROM (NOW() - last_contacted))/3600 AS hours_since_contact,
    created_at
FROM re.leads
WHERE tier = 'hot'
  AND (last_contacted IS NULL OR last_contacted < NOW() - INTERVAL '24 hours')
ORDER BY score DESC, created_at DESC;

CREATE OR REPLACE VIEW re.v_drip_due_today AS
SELECT
    l.id, l.name, l.email, l.source,
    l.property_interest, l.timeline, l.tier,
    l.drip_stage, l.last_contacted,
    ds.subject_template, ds.body_template, ds.delay_days
FROM re.leads l
JOIN re.drip_sequences ds ON ds.tier = l.tier AND ds.stage = l.drip_stage
WHERE l.tier IN ('warm','cold')
  AND ds.active = TRUE
  AND (
      l.last_contacted IS NULL
      OR l.last_contacted < NOW() - (ds.delay_days || ' days')::INTERVAL
  )
ORDER BY l.last_contacted ASC NULLS FIRST;

-- =============================================================================
-- Row-level security (off for now, single-tenant). Enable explicitly when
-- multi-user support lands. Service role bypasses RLS.
-- =============================================================================
ALTER TABLE re.contacts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE re.leads        ENABLE ROW LEVEL SECURITY;
ALTER TABLE re.interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE re.drip_sequences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role access to re.contacts" ON re.contacts;
CREATE POLICY "Service role access to re.contacts" ON re.contacts
    FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Service role access to re.leads" ON re.leads;
CREATE POLICY "Service role access to re.leads" ON re.leads
    FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Service role access to re.interactions" ON re.interactions;
CREATE POLICY "Service role access to re.interactions" ON re.interactions
    FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Service role access to re.drip_sequences" ON re.drip_sequences;
CREATE POLICY "Service role access to re.drip_sequences" ON re.drip_sequences
    FOR ALL USING (auth.role() = 'service_role');

COMMIT;
