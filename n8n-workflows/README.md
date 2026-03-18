# n8n Knowledge Source Connectors

Workflow templates that sync external knowledge sources into Manic AI's RAG pipeline via the `/v1/ingest` API endpoint.

## Available Connectors

| Connector | File | Source |
|-----------|------|--------|
| Notion | `notion-connector.json` | Notion databases/pages |
| Google Drive | `google-drive-connector.json` | Google Docs, TXT, MD, HTML, PDF |
| Confluence | `confluence-connector.json` | Confluence wiki pages |

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
