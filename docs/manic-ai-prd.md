# Manic-AI Real Estate Hub — Product Requirements Document

> **Status**: Living document. Reflects as-of 2026-04-14.
> **Audience**: (1) Mark Vitale as solo-op reference, (2) future Claude Code sessions loading context.
> **Updated by**: edit in place; bump the "Status" date.
> **Related**: `CLAUDE.md` (operational rules), `.claude/plans/modular-puzzling-feigenbaum.md` (implementation plan), `docs/ARCHITECTURE.md` (technical reference).

---

## 1. Context and origin

Manic-AI started as a general-purpose AI platform: FastAPI + Next.js + Ollama + Supabase pgvector hybrid RAG, running on a Hostinger VPS behind Tailscale. It was a solid foundation but had no specific business purpose.

In April 2026, Mark decided to pivot Manic-AI into the **central operations hub for his real estate business** (Vera Cohen Realty, Capital Region NY). He had already built a parallel 9-workflow n8n + Supabase "Lead and Content Machine" playbook designed to run on this exact stack at $0 marginal cost. The pivot is mostly integration, not invention: bring the playbook into the hub, wire the frontend, make it a product instead of a pile of workflows.

This PRD exists because we'd been building at velocity and need to anchor the vision before Phase 3+ so:
- Mark has one place to orient anyone (including himself) on what this thing is
- Future Claude Code sessions can re-acquire context without a 2-hour conversation
- Scope creep has a reference to push back against

---

## 2. Problem

Mark is a solo real estate agent in a market where speed-to-lead, consistent content, and compliance discipline separate winners from churners. Like most solo agents, he is the constraint: a lead sits for 6 hours because he was at a showing, a listing goes live without matching social content because he was drafting offers, a Fair Housing foot-gun slips through because he was exhausted.

The standard "solutions" fail him:
- **CRMs** (Follow Up Boss, LionDesk, kvCORE) are rented, expensive per-seat, and make his data hostage. They don't know his market, his templates, or his voice.
- **Content tools** (Canva, ChatGPT, Listings-to-Leads) don't integrate with his lead pipeline and have no Fair Housing awareness.
- **Hand-rolled automations** (n8n, Zapier) work but sprawl into unmanaged tech debt and have no UI. He'd end up maintaining 12 separate workflows he's afraid to touch.
- **Generic AI chat** (ChatGPT, Claude) can draft copy but has no memory of his leads, his listings, or his past clients — every session starts from zero.

The meta-problem: **a solo agent's tooling should feel like an employee, not a toolbox.** One system, one place to look, owns his data, knows his market, gets faster the longer he uses it.

---

## 3. Users

Single-tenant for the foreseeable future:

### Primary — Mark Vitale (solo real estate agent)
- Licensed in NY, working the Capital Region (Albany, Troy, Schenectady, Saratoga Springs, plus satellite locales like Delmar, Clifton Park, East Greenbush)
- Technical enough to SSH to a VPS, read a Dockerfile, run a migration, edit a prompt
- NOT a full-time developer — can't maintain sprawling infrastructure
- Has: an existing Seller Blueprint funnel, a re-crm Next.js app he built, the Lead and Content Machine n8n playbook, training materials (Mulrenin, Top Dollar Blueprint)
- Uses: Gmail (mvitale@veracohenrealty.com), Google Calendar, Facebook Pages, Instagram, occasionally TikTok/Reels, eventual MLS/IDX feed (coming within 30 days as of 2026-04-13)

### Secondary — future Mark (same user, 6 months in)
The PRD must keep Mark-in-6-months as honest as Mark-today. Features that cost him ongoing maintenance must earn their keep.

### Secondary — Claude Code sessions
Every new Claude conversation should be able to read `CLAUDE.md` + this PRD + the current plan file and know enough to help without re-litigating architecture.

### Not a user (by design)
- Other agents at Vera Cohen Realty (for now)
- Buyers and sellers (they interact with his funnel, not the hub)
- White-label customers / other solo agents (not ruled out, but not in scope)

---

## 4. Goals

In priority order:

**G1 — No lead drops.** Every lead from every source (Seller Blueprint, Zillow, referral, open house, manual entry) lands in one place, gets scored within seconds, and enters the right nurture cadence. Speed-to-lead for hot leads < 2 minutes (automated email + phone alert).

**G2 — Content production scales without Mark becoming a copywriter.** A new listing generates 5 platform-ready content drafts (MLS, IG, FB, email, Reels) within minutes, every one pre-checked for Fair Housing compliance, queued for his approval before publishing.

**G3 — Fair Housing compliance is never an afterthought.** Every generated content piece has an auditable verdict (`pass / warn / block`), a human-readable audit log, and a retention trail. An obvious violation (`"no kids"`, `"55+"`, `"no Section 8"`) can never reach `approved` status without an explicit admin override — and there is no override in Phase 1-4.

**G4 — One pane of glass for the business.** Leads, listings, deals, content, market intel — all in one dashboard. Mark opens his laptop, sees "who do I call next / what's in the pipeline / what closes this week" without switching apps.

**G5 — Data ownership.** Every byte lives on Mark's VPS. No SaaS subscription can be turned off. No CRM vendor can raise his price 40% at renewal. The data is his.

**G6 — Zero marginal cost.** Everything runs on the VPS Mark is already paying for. No Follow Up Boss, no SendGrid, no Twilio, no Firecrawl Cloud. Gmail + Telegram + local Ollama + self-hosted n8n + Supabase cover the functional surface.

**G7 — Compounding intelligence.** Every lead interaction, every listing, every past client conversation becomes retrievable context in the RAG layer. The longer Mark uses the hub, the better his "draft a follow-up to lead 47" becomes because it knows lead 47.

---

## 5. Non-goals

Things the hub explicitly does NOT try to do. When a feature request pushes here, push back.

- **N1** — Be a multi-tenant CRM. Single user, single agent, forever (until proven otherwise).
- **N2** — Replace the MLS. The hub ingests listings from an MLS feed when one is available; it does not BE the MLS.
- **N3** — Auto-publish content without human approval in Phases 1-2. Approval is a hard gate. The evergreen auto-post workflow (WF09) only draws from content already manually approved and sitting in `re.v_content_queue`.
- **N4** — Provide legal Fair Housing advice. The compliance gate reduces risk but does not eliminate it. Mark carries the final liability and the critic tells him so.
- **N5** — Replicate every Follow Up Boss feature. If a feature requires implementing 80% of Salesforce, it's out of scope.
- **N6** — Match Zillow / Redfin search UX. Listings search is for Mark to answer buyer questions, not for public consumers.
- **N7** — Train custom models. Off-the-shelf Ollama models (bge-m3, llama3.2:3b, mistral:7b) handle everything. Fine-tuning is a Phase 5+ consideration at best.
- **N8** — Build a mobile app. Web-responsive only. Mark's phone hits the hub in a browser over Tailscale.
- **N9** — Integrate with every social platform. Phase 1-4 covers Instagram, Facebook, email, Reels/TikTok (via script delivery), and LinkedIn. Twitter/X, Threads, Snapchat, Pinterest are explicitly not in scope until proven necessary.
- **N10** — Persist design-time Claude subagents as runtime services. The 4 subagents that generate code (`crm-dashboard-dev`, `integration-builder`, `landing-page-builder`, plus any future ones like `python-reviewer`) stay in `~/.claude/agents/` for Mark's Claude Code sessions — they are NOT exposed via the hub's API.

---

## 6. Requirements

Organized by domain area. Each requirement has a Phase tag showing when it lands.

### 6.1 Lead pipeline (Phases 1, 3)

- **R1.1** *(P1 ✅)* Webhook-compatible lead intake endpoint (`POST /v1/re/leads/intake`) that any form, funnel, or automation can POST to with a flexible payload.
- **R1.2** *(P1 ✅)* Every incoming lead is scored 0-100 and tiered `hot / warm / cold` by an Ollama-powered model within seconds of intake.
- **R1.3** *(P1 ✅)* Scoring falls back gracefully on LLM failure — lead still persists, marked for manual review, never dropped.
- **R1.4** *(P1 ✅)* `/leads` page shows all leads in a scannable table with tier filters, clickable rows that open a detail drawer with scoring reasoning and activity timeline.
- **R1.5** *(P1 ✅)* Hot leads trigger an instant automated email via n8n WF02 (Gmail OAuth). Optional Telegram phone alert.
- **R1.6** *(P1 ✅)* Warm/cold leads enter a stateful drip sequence via n8n WF03, cadenced per-tier from seeded templates in `re.drip_sequences`.
- **R1.7** *(P3)* Lead → Contact conversion: qualified leads merge into `re.contacts`, which becomes the canonical person record for deals, showings, and past-client nurture.
- **R1.8** *(P3)* Monthly reactivation loop via n8n WF04 for dormant cold leads (60+ day silence).

### 6.2 Content machine (Phase 2, 4)

- **R2.1** *(P2 ✅)* Listings CRUD: `/listings` page with status filter, create form, card/table view, detail drawer.
- **R2.2** *(P2 ✅)* One-click content generation: selecting a listing and clicking "Generate Content" produces 5 platform drafts (MLS description, Instagram caption, Facebook post, email blast, Reels script) in under 5 minutes.
- **R2.3** *(P2 ✅)* Every generated piece runs through the Fair Housing compliance gate and is persisted to `re.content_calendar` with a verdict (`pass / warn / block`), audit log, and derived status.
- **R2.4** *(P2 ✅)* `/content` page shows all generated content with color-coded compliance badges, platform filter, status filter, editable body, and approve/reject/recheck actions.
- **R2.5** *(P2 ✅)* Approval is hard-blocked on `block` verdict — 409 from the API, red banner in the UI, no override path in Phase 1-4.
- **R2.6** *(P2 ✅)* Weekly market content generation via n8n WF07: Firecrawl scrapes Redfin → market_snapshots → Ollama generates multi-platform market updates.
- **R2.7** *(P2 ✅)* Evergreen auto-posting via n8n WF09 (Tue/Thu): pulls ONLY from `re.v_content_queue` (already approved) and posts to Facebook Graph API + emails Reels scripts to Mark.
- **R2.8** *(P4)* On-demand content repurposing: ad-hoc transformation of one piece into 5+ variants, invoked from chat.

### 6.3 Fair Housing compliance (Phase 2, ongoing)

- **R3.1** *(P2 ✅)* Two-layer compliance gate: deterministic regex against federal + NY State protected class language, then LLM critic grounded in HUD reference chunks from the `re_compliance` RAG collection.
- **R3.2** *(P2 ✅)* Never fail-open. If the LLM critic is unavailable, the verdict defaults to `warn`, never `pass`.
- **R3.3** *(P2 ✅)* Every verdict is logged to `re.content_calendar.fair_housing_notes` with a one-liner audit string suitable for legal defense (`"verdict=warn | rules: clean | llm: warn (1 issues)"`).
- **R3.4** *(P2 ✅)* Safe reframings are exposed in code (`SAFE_REFRAMINGS` dict) so the UI can later surface "try this instead" suggestions.
- **R3.5** *(ongoing)* Rule patterns and HUD reference corpus are versioned and reviewed quarterly. Edge cases like HOPA 55+ communities and cash-buyer language need per-deal overrides in Phase 4+.

### 6.4 Pipeline and deal flow (Phase 3)

- **R4.1** *(P3)* `re.deals` table with stage enum (`new → nurturing → appointment → listed → under_contract → closed → lost`).
- **R4.2** *(P3)* `/pipeline` page: kanban view by deal stage, drag-to-move, deal detail drawer.
- **R4.3** *(P3)* `re.showings` table with Google Calendar integration for showing schedule.
- **R4.4** *(P3)* Morning brief job (replaces L/C Machine WF05): daily 7am email summarizing yesterday's lead activity, today's showings, pipeline risks.

### 6.5 Chat and intelligence (Phase 3, 4)

- **R5.1** *(P3)* Persistent chat drawer on every route. Context-aware: knows which lead/listing the user is looking at and injects it into the system prompt.
- **R5.2** *(P3)* Natural-language queries against the pipeline: "show hot leads", "who haven't I talked to this week", "what closes in April".
- **R5.3** *(P4)* CMA (comparative market analysis) agent: "comps for 1006 Rockport" returns a structured CMA built from `re.listings` + `re.market_snapshots`.
- **R5.4** *(P4)* Integration with SEO content writer for on-demand blog, neighborhood guide, and email generation.

### 6.6 MLS data ingestion (Phase 4, 5)

- **R6.1** *(P4)* Playwright-based scraper as a scheduled job, targeting public MLS/Zillow/Redfin pages for the Capital Region. Rate-limited, robots.txt-respecting.
- **R6.2** *(P4)* Scraper writes to `re.listings` via a pluggable source interface.
- **R6.3** *(P5)* When IDX/RETS feed arrives, swap scraper for feed client — one-service change, same `re.listings` write target, no schema changes.

### 6.7 Data ingestion and RAG (Phase 1, ongoing)

- **R7.1** *(P1 ✅)* Bulk ingest script for `~/Downloads/Real_Estate/` populating `rag.collections` (`re_listings_past`, `re_training_sales`, `re_geography`, `re_compliance`).
- **R7.2** *(P1 ✅)* HUD Fair Housing reference corpus seeded as `re_compliance` collection.
- **R7.3** *(ongoing)* Past clients, closed transactions, and ongoing interactions populate the RAG layer so chat queries compound in usefulness.

### 6.8 Operational requirements (all phases)

- **R8.1** No new Docker containers beyond what the hub already runs. Every feature extends existing services (FastAPI, n8n, Supabase, Ollama, Qdrant).
- **R8.2** Zero incremental SaaS spend. Gmail + Telegram + local Ollama + n8n + Supabase + Facebook Graph API cover everything.
- **R8.3** All data stays on the VPS. Nothing leaves Tailscale.
- **R8.4** Every migration goes through `supabase/migrations/NNNN_*.sql`. Never hand-run DDL against the VPS.
- **R8.5** Every Python service handling compliance or money has unit tests against the deterministic layer.

---

## 7. Current state

As of 2026-04-14:

| Phase | Status | Delivered |
|---|---|---|
| **Phase 1** | ✅ Shipped | `re.*` schema (contacts, leads, interactions, drip_sequences), `/v1/re/leads/*` API, lead scoring service (llama3.2:3b), `/leads` frontend, n8n WF02 + WF03 committed to repo, ingest script. Commit `7f87956c`. |
| **Phase 2** | ✅ Shipped | `re.listings`, `re.content_calendar`, `re.market_snapshots` schema, Fair Housing gate (rule + LLM), content generator (5-platform Generator-Critic), SEO content writer, `/listings` + `/content` frontend with compliance badges, n8n WF07 + WF09 committed. Commits `9978b582` + `f292c33c`. End-to-end verified: 5 variants generated, 1 correctly flagged by LLM for familial-status language ("perfect for kids or pets"). |
| **Phase 3** | 📋 Planned | Pipeline + chat drawer + morning brief. Blocked only by user go-ahead. |
| **Phase 4** | 📋 Planned | CMA, MLS scraper, re-crm retirement, landing pages hosted in hub. |
| **Phase 5** | 📋 Deferred | MLS feed swap when IDX/RETS arrives (~30 days from 2026-04-13). |

**Outstanding manual tasks from Mark** (documented in `C:\Users\mark_\Desktop\MANIC-AI-PHASE1-TODO.txt`):
1. Import n8n WF02 + WF03 workflows, wire credentials
2. Retarget Seller Blueprint webhook to `/v1/re/leads/intake`
3. Run `scripts/ingest_real_estate.py` against the Real_Estate folder
4. Optional Ollama warmup cron
5. Review seeded drip templates for Fair Housing before activation

---

## 8. Success metrics

Measurable outcomes. Review monthly.

| Metric | Target | How measured |
|---|---|---|
| **Speed-to-lead (hot)** | < 2 min intake → first automated email | n8n WF02 execution log timestamps vs `re.leads.created_at` |
| **Lead capture rate** | 100% of Seller Blueprint submissions land in `re.leads` | Funnel submissions count vs `re.leads` source=seller_blueprint count, reconciled weekly |
| **Content throughput** | 5 compliance-checked drafts per listing within 5 min of Generate button click | `re.content_calendar` rows per listing + timestamps |
| **Fair Housing catch rate** | Zero blocked content reaches `approved` status | `SELECT COUNT(*) FROM re.content_calendar WHERE status='approved' AND fair_housing_verdict='block'` must always return 0 |
| **Fair Housing false-positive review burden** | < 20% of drafts require manual edit | `warn + block / total` ratio over 30 days |
| **Drip engagement** | At least 15% reply rate on warm drip sequences | Manual review of Gmail sent folder vs inbox, logged to `re.interactions` |
| **Uptime of core loop** | ≥ 99% of intake endpoint requests in last 7 days return 2xx | `public.chat_log` or API access log rollup |
| **Cost** | $0/mo incremental beyond VPS | Review `.env` + docker-compose; any new SaaS line item is a regression |
| **Mark's time in the hub** | 80% of CRM-ish work happens in the hub, not in other apps | Self-reported weekly check-in, no automated measure |

---

## 9. Open questions

Things that need answers before certain phases can land. Add to this list over time.

- **Q1** — **MLS feed vendor**: which one (IDX Broker, Realty Candy, Showcase IDX, RETS direct)? Determines the Phase 5 swap surface. *As of 2026-04-13, feed is "coming within 30 days" — vendor TBD.*
- **Q2** — **Chat drawer UX**: does the drawer push content or overlay as a floating panel? LeadsManager-style sidebar or fullscreen on mobile? Blocks Phase 3 start.
- **Q3** — **Morning brief delivery channel**: email, Telegram, or both? What time? Default is 7am Eastern, email-only.
- **Q4** — **Deal stages**: the enum proposed is `new → nurturing → appointment → listed → under_contract → closed → lost`. Mark, is that your actual flow or do you have stages like "pre-listing consultation" / "offer submitted"?
- **Q5** — **Multi-user horizon**: will Mark ever bring another agent on the hub? If yes in 12 months, Phase 3 should bake in `user_id` FK on the RE tables now rather than retrofitting later. If no, skip the cost.
- **Q6** — **HOPA 55+ listings**: does Mark ever market HOPA-qualified 55+ communities? Affects whether we add an override flag in the compliance gate.
- **Q7** — **Re-crm sunset**: when exactly does `re-crm` go dark? Phase 4 plan says end of Phase 4, but if Mark is actively using it today, we need a data migration path from re-crm's Prisma store to `re.*`.
- **Q8** — **Chat drawer cost ceiling**: the drawer means every route call potentially spawns an LLM query. Budget in tokens/month? Upper bound on context window injection?

---

## 10. Appendix

### 10.1 Stack

- **Frontend**: Next.js 16.2.2, React 19, TypeScript, Tailwind, Zustand 5, glassmorphism dark theme
- **API**: FastAPI (Python 3.12 in Docker), asyncpg, httpx, Pydantic, 20+ routers on `/v1/*` prefix
- **LLM inference**: Ollama (bge-m3 embeddings, llama3.2:3b chat, mistral:7b for heavier lifts)
- **Primary DB**: Supabase Postgres 15 + pgvector 0.7 + pg_trgm (hybrid vector + BM25 search)
- **Secondary DB**: Qdrant v1.13.2 (currently unused, kept for option value)
- **Cache / queues**: Redis 7
- **Workflow engine**: n8n 2.14.2 (cron + OAuth-heavy workflows)
- **Observability**: Langfuse 2, Grafana + Loki + Promtail + Prometheus
- **Edge**: Caddy 2 (behind Tailscale — no public TLS termination)
- **Host**: Hostinger VPS, 16GB RAM, 193GB disk, Tailscale IP `100.98.154.61`, SSH alias `openclaw-vps`

### 10.2 Schemas in Supabase

| Schema | Purpose |
|---|---|
| `public.*` | API internals: users, auth, chat history, ingest jobs, health logs |
| `rag.*` | Retrieval corpus: documents, chunks, collections (including `re_compliance`, `re_listings_past`, `re_training_sales`, `re_geography`, `re_market_intel`) |
| `re.*` | Real estate domain: contacts, leads, interactions, drip_sequences, listings, content_calendar, market_snapshots (+ deals, showings, offers in Phase 3-4) |

### 10.3 Key code paths

- `api/services/fair_housing.py` — two-layer compliance gate (compliance-critical, audited by main agent)
- `api/services/lead_scoring.py` — Ollama-powered lead scoring, ported from WF01
- `api/services/content_generator.py` — 5-platform content variants, WF06 prompts verbatim
- `api/services/seo_content_writer.py` — general RE copywriter
- `api/routers/re_leads.py`, `re_listings.py`, `re_content.py` — Phase 1-2 API routers
- `frontend/components/LeadsManager.tsx`, `ListingsManager.tsx`, `ContentCalendar.tsx` — primary frontend components
- `frontend/lib/stores/{leadStore,listingStore,contentStore}.ts` — Zustand domain stores
- `supabase/migrations/005_re_schema_phase1.sql`, `006_re_schema_phase2.sql` — domain schema
- `n8n-workflows/` — all n8n workflow JSONs (committed to repo, imported manually in n8n UI)
- `scripts/ingest_real_estate.py` — bulk RAG ingest with HUD Fair Housing seed
- `scripts/remediation/fix_service_health_log.sql` — VPS schema drift remediation (reference)

### 10.4 Out-of-repo references

- `~/Downloads/Lead and Content Machine/` — source of truth for n8n workflow JSONs and WF06 prompts
- `~/Downloads/Real_Estate/` — live data: past listings, training materials, geography
- `~/.claude/agents/lead-manager.md`, `mls-listing-scraper.md`, `re-data-analyst.md`, `seo-content-writer.md`, `crm-dashboard-dev.md`, `integration-builder.md`, `landing-page-builder.md` — Claude subagents (4 ported to runtime, 3 stay design-time)
- `~/.claude/projects/C--Users-mark--Desktop-Manic-AI/memory/MEMORY.md` — session memory with project state

### 10.5 Principles to follow

These came out of Phase 1-2 execution and are load-bearing:

1. **Compliance cannot live in n8n.** Anything that gates Fair Housing lives in Python where it's unit-testable and version-controlled.
2. **Two-layer compliance, always.** Rules for deterministic, LLM for gray area. Neither alone is sufficient.
3. **Never fail-open on compliance.** LLM unavailable → verdict `warn` minimum, never `pass`.
4. **Sequential Ollama calls** on the VPS. 16GB RAM cannot handle parallel 7B inference. Queue, don't parallelize.
5. **Schema drift is the silent killer.** Single source of truth in `supabase/migrations/`. Never hand-run raw SQL against prod.
6. **Every migration must be idempotent.** Assume it will be re-run. Use `CREATE TABLE IF NOT EXISTS`, `DROP POLICY IF EXISTS`, `ON CONFLICT DO NOTHING`.
7. **Check `docker inspect --format '{{json .State.Health.Log}}' <container>` FIRST** when a container shows unhealthy. The Phase 0 frontend "crash loop" was a healthcheck bug; the server was fine.
8. **Alpine + musl localhost → ::1.** Next.js binds IPv4. Always use `127.0.0.1` in Alpine healthchecks.
9. **Design-time agents stay design-time.** Claude subagents that generate code should never be exposed as runtime API. If a feature needs them at runtime, port the prompt into a Python service.
10. **Mark is the user and the constraint.** Every feature costs him ongoing maintenance. If it doesn't compound or self-operate, it's a liability.

---

## 11. Revision log

| Date | Change |
|---|---|
| 2026-04-14 | Initial PRD, post Phase 2 ship |

---

*This is a living document. Update "Current state", "Success metrics", and "Open questions" as phases ship. Keep "Non-goals" honest — if we're violating one, either remove it or push back on the request.*
