# n8n Knowledge Source Connectors

Workflow templates that sync external knowledge sources into Manic AI's RAG pipeline via the `/v1/ingest` API endpoint.

## Available Connectors

| Connector | File | Source |
|-----------|------|--------|
| Notion | `notion-connector.json` | Notion databases/pages |
| Google Drive | `google-drive-connector.json` | Google Docs, TXT, MD, HTML, PDF |
| Confluence | `confluence-connector.json` | Confluence wiki pages |

## Real Estate — Phase 1 Workflows

Two workflows ported from `~/Downloads/Lead and Content Machine/` and patched
to target the `re.*` schema (migration `005_re_schema_phase1.sql`).

| File | Purpose | Trigger |
|---|---|---|
| `02_hot_lead_response.json` | Instant email to hot leads + interaction log | Supabase Realtime webhook on `re.leads` INSERT where `tier='hot'` (or cron fallback via `re.v_hot_leads`) |
| `03_drip_nurture.json` | Daily drip send to warm/cold leads via `re.v_drip_due_today` | Cron Mon–Sat 8am |

### Import checklist

1. Open n8n at `http://100.98.154.61:5679`.
2. **Settings → Credentials → New** and create:
   - **Postgres** → host `ai-supabase-db`, port `5432`, db `postgres`, user/password from `.env` (`POSTGRES_USER` / `POSTGRES_PASSWORD`), SSL off (internal network).
   - **Gmail OAuth2** → use Mark's `mvitale@veracohenrealty.com` Google account, scopes `gmail.send` / `gmail.compose` / `gmail.modify`.
   - *(optional)* **Telegram Bot** for hot-lead phone alerts.
3. **Workflows → Import from File** for each of `02_*.json` and `03_*.json`.
4. For every imported node, re-bind the credential (n8n imports drop credential references by design).
5. In WF02, pick a trigger strategy:
   - **Recommended**: Supabase Realtime webhook on `re.leads` INSERT with filter `tier=hot` → points at the n8n webhook URL. Near-instant.
   - **Fallback**: Cron every 5 min, query `SELECT * FROM re.v_hot_leads`.
6. Activate both workflows.

### Verification

Fire a test intake with `POST /v1/re/leads/intake` (see plan section 11) and confirm:
- A row lands in `re.leads` with a score and tier.
- If tier=`hot`, WF02 fires and an email shows up. Start with your own address, not a real lead.
- WF03 runs tomorrow at 8am — or trigger it manually via the n8n UI to smoke test against seeded warm leads.

### Fair Housing reminder

These workflows send email. Protected-class references in `re.drip_sequences`
body templates are your responsibility until the Phase 2 compliance critic
lands. Review all templates before activation and never auto-drip untested
copy.

All connectors run on a 6-hour schedule and perform incremental sync (only pages modified since the last run).

## Setup Instructions

### Prerequisites

- n8n running at `http://localhost:5679` (included in Manic AI docker-compose)
- Manic AI API running at `http://api:8081` (internal Docker network)

### Importing a Workflow

1. Open n8n at [http://localhost:5679](http://localhost:5679)
2. Click **Add workflow** (+ button)
3. Click the **...** menu (top right) and select **Import from File**
4. Select the desired `.json` template from this directory
5. Configure the credentials (see below)
6. Activate the workflow with the toggle switch

### Notion Connector

**Required credentials:**

1. Create a Notion integration at [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Copy the **Internal Integration Token**
3. Share your target database with the integration (click "..." on the database page, then "Add connections")
4. In n8n, go to **Credentials** and create a new **Notion API** credential with the token

**Configuration:**

- The workflow queries a Notion database for recently modified pages
- Update the `notion_database_id` in the "Notion - List Modified Pages" node with your database ID
- Database ID is the 32-character hex string in your database URL: `notion.so/{workspace}/{database_id}?v=...`

### Google Drive Connector

**Required credentials:**

1. Create OAuth2 credentials in [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Enable the Google Drive API
3. Configure OAuth consent screen with `https://www.googleapis.com/auth/drive.readonly` scope
4. In n8n, go to **Credentials** and create **Google Drive OAuth2 API** credentials
5. Complete the OAuth flow

**Configuration:**

- Set the target folder ID in the "Google Drive - List Files" node
- Folder ID is the last path segment in the folder URL: `drive.google.com/drive/folders/{folder_id}`
- Supported file types: Google Docs, plain text, Markdown, HTML, PDF
- Google Docs are auto-converted to plain text for ingestion

### Confluence Connector

**Required credentials:**

1. Generate an API token at [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. In n8n, go to **Credentials** and create **HTTP Basic Auth** credentials:
   - **User**: Your Atlassian email address
   - **Password**: The API token (not your account password)

**Configuration:**

- Update `confluence_base_url` in the "Confluence - List Pages" node to your instance URL (e.g., `https://your-domain.atlassian.net`)
- The workflow fetches the 50 most recently updated pages
- HTML content is automatically stripped to plain text before ingestion

## How It Works

Each connector follows the same pipeline:

```
Schedule Trigger (every 6h)
    → List items from source
    → Filter (only modified since last run)
    → Fetch content
    → POST to http://api:8081/v1/ingest
    → Store last_run timestamp
```

The ingest API payload format:

```json
{
  "title": "Document Title",
  "content": "Full text content...",
  "collection": "notion|google-drive|confluence",
  "content_type": "text/markdown|text/plain",
  "metadata": {
    "source": "notion|google-drive|confluence",
    "page_id": "...",
    "last_updated": "2026-03-17T00:00:00Z"
  }
}
```

## Troubleshooting

### Workflow does not trigger

- Verify the workflow is **activated** (toggle is green)
- Check n8n execution log for errors: **Executions** tab in the workflow editor
- Confirm the API container is reachable from n8n via `http://api:8081` (both on the same Docker network)

### Authentication errors

- **Notion**: Ensure the integration is shared with the target database
- **Google Drive**: Re-authorize OAuth if the refresh token expired
- **Confluence**: Verify email + API token (not password), and that the token has not been revoked

### No pages ingested

- Check filter conditions: the "last_run" timestamp may already be ahead of your content
- For first run, the filter defaults to 6 hours ago (Notion/Google Drive) or epoch (Confluence)
- Manually trigger the workflow once with the **Test workflow** button to verify

### Ingest API returns errors

- Confirm the API is running: `curl http://localhost:8081/health`
- Check API logs: `docker logs manic-ai-api`
- Verify the `/v1/ingest` endpoint exists and accepts the payload format above

### Large documents fail

- The default HTTP timeout is 30 seconds; increase it in the HTTP Request node if needed
- Consider chunking very large documents before ingestion
