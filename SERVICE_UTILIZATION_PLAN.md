# Manic AI - Service Utilization Plan

Complete guide to setting up, integrating, and utilizing all services in your Manic AI stack.

---

## Service Overview

| Service | URL | Purpose |
|---------|-----|---------|
| **Manic AI Frontend** | http://100.111.244.124:3000 | Main chat interface with RAG |
| **Manic AI API** | http://100.111.244.124:8081 | Unified REST API |
| **Ollama** | http://100.111.244.124:11434 | Local LLM inference |
| **Open WebUI** | http://100.111.244.124:3006 | Alternative chat UI |
| **Supabase Studio** | http://100.111.244.124:3005 | Database management |
| **n8n** | http://100.111.244.124:5679 | Workflow automation |
| **Flowise** | http://100.111.244.124:3008 | Visual AI flow builder |
| **Langfuse** | http://100.111.244.124:3007 | LLM observability |
| **SearXNG** | http://100.111.244.124:8889 | Private web search |
| **Qdrant** | http://100.111.244.124:6333 | Vector database |
| **Redis** | http://100.111.244.124:6380 | Cache & sessions |

---

## Phase 1: Core Setup (Complete)

### 1.1 Ollama - Local LLM Engine

**Status**: Running

**Pull recommended models**:
```bash
# Chat models
docker exec ollama ollama pull llama3.2:3b      # Fast, good for general use
docker exec ollama ollama pull llama3.2:latest  # Larger, more capable
docker exec ollama ollama pull mistral:7b       # Great for coding
docker exec ollama ollama pull codellama:7b     # Specialized for code

# Embedding model (required for RAG)
docker exec ollama ollama pull nomic-embed-text
```

**Verify models**:
```bash
docker exec ollama ollama list
```

### 1.2 Supabase - Database & Auth

**Status**: Running with auth configured

**Your credentials**:
- Email: markvitale21@gmail.com
- Password: L0c4Linf0$

**Access Studio**: http://100.111.244.124:3005
- Username: admin
- Password: (your htpasswd password)

**Key tables created**:
- `rag.documents` - Uploaded documents
- `rag.chunks` - Document chunks with embeddings
- `rag.collections` - Document organization

### 1.3 Manic AI Frontend & API

**Status**: Running

**Features available**:
- Chat with local LLMs
- RAG document search
- Model management
- Dashboard with service status

---

## Phase 2: Workflow Automation with n8n

**URL**: http://100.111.244.124:5679

n8n is a powerful workflow automation tool. Here's how to integrate it with your stack:

### 2.1 Initial Setup

1. Open http://100.111.244.124:5679
2. Skip registration (click Skip)
3. Create your first workflow

### 2.2 Recommended Workflows

#### Workflow 1: Document Ingestion Pipeline

Automatically ingest documents from various sources into Manic AI RAG.

```
[Trigger] → [Fetch Content] → [Call Manic API /ingest] → [Log to Langfuse]
```

**Nodes to use**:
1. **Webhook Trigger** - Receive document URLs
2. **HTTP Request** - Fetch document content
3. **HTTP Request** - POST to `http://manic-ai-api:8081/ingest`
4. **HTTP Request** - Log to Langfuse

**Example n8n workflow JSON**:
```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "ingest-document",
        "httpMethod": "POST"
      }
    },
    {
      "name": "Ingest to Manic AI",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://manic-ai-api:8081/ingest",
        "method": "POST",
        "bodyType": "json",
        "body": {
          "content": "={{ $json.content }}",
          "filename": "={{ $json.filename }}"
        }
      }
    }
  ]
}
```

#### Workflow 2: Scheduled Web Scraping + RAG

Automatically scrape websites and add to your knowledge base.

```
[Cron Trigger] → [HTTP Request] → [Extract Text] → [Ingest to RAG]
```

#### Workflow 3: Chat with External Integrations

Connect Slack/Discord/Email to Manic AI for AI-powered responses.

```
[Slack Trigger] → [Call Manic API /chat] → [Reply to Slack]
```

#### Workflow 4: Backup Automation

Automatically backup your Supabase database.

```
[Cron Daily] → [Execute pg_dump] → [Upload to S3/Storage]
```

### 2.3 n8n Credentials to Create

| Credential | Use For |
|------------|---------|
| **Manic AI API** | Header Auth with no key (internal network) |
| **Supabase** | Database operations |
| **Ollama** | Direct LLM calls |

---

## Phase 3: Visual AI Flows with Flowise

**URL**: http://100.111.244.124:3008
**Login**: admin / (from FLOWISE_PASSWORD in .env)

Flowise lets you build LLM applications visually without code.

### 3.1 Initial Setup

1. Open http://100.111.244.124:3008
2. Login with admin credentials
3. Go to **Credentials** and add:

#### Add Ollama Credential
- Name: `Local Ollama`
- Base URL: `http://ollama:11434`

#### Add Supabase Credential (optional)
- Name: `Manic Supabase`
- Supabase URL: `http://supabase-kong:8000`
- API Key: (your ANON_KEY)

### 3.2 Recommended Flows

#### Flow 1: Simple Chatbot
```
[Chat Model (Ollama)] → [LLM Chain] → [Output]
```

#### Flow 2: RAG Chatbot with Qdrant
```
[Document Loaders] → [Text Splitter] → [Qdrant Upsert]
                                              ↓
[Chat Input] → [Qdrant Retriever] → [Conversational Retrieval QA] → [Output]
```

**Qdrant Configuration**:
- URL: `http://qdrant:6333`
- Collection: `manic-docs`

#### Flow 3: Agent with Web Search
```
[Ollama Chat] → [Agent] → [SearXNG Tool] → [Output]
                    ↓
              [Calculator Tool]
```

**SearXNG Tool Config**:
- URL: `http://ai-searxng:8080/search`

#### Flow 4: Multi-Model Router
Route queries to different models based on content type.

```
[Input] → [Classifier] → [Code Model (codellama)]
                    ↓
              [General Model (llama3.2)]
                    ↓
              [Creative Model (mistral)]
```

### 3.3 Flowise API Usage

Every Flowise chatflow gets an API endpoint:

```bash
curl -X POST http://100.111.244.124:3008/api/v1/prediction/<chatflow-id> \
  -H "Content-Type: application/json" \
  -d '{"question": "What is machine learning?"}'
```

---

## Phase 4: LLM Observability with Langfuse

**URL**: http://100.111.244.124:3007

Langfuse tracks all your LLM interactions for debugging, cost analysis, and improvement.

### 4.1 Initial Setup

1. Open http://100.111.244.124:3007
2. Create an account (first user becomes admin)
3. Create a new project
4. Get your API keys from Settings → API Keys

### 4.2 Integrate with Manic AI API

Add Langfuse tracking to your API. Update the API code to include:

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key="pk-...",
    secret_key="sk-...",
    host="http://langfuse:3000"
)

# Track a generation
trace = langfuse.trace(name="chat")
generation = trace.generation(
    name="llama-response",
    model="llama3.2:3b",
    input=user_message,
    output=ai_response
)
```

### 4.3 Integrate with Flowise

In Flowise, add the **Langfuse** node to any flow:
- Public Key: (from Langfuse)
- Secret Key: (from Langfuse)
- Host: `http://langfuse:3000`

### 4.4 What to Track

| Metric | Why |
|--------|-----|
| **Latency** | Identify slow responses |
| **Token Usage** | Monitor costs |
| **User Feedback** | Improve prompts |
| **Error Rate** | Debug issues |
| **RAG Relevance** | Tune retrieval |

---

## Phase 5: Private Web Search with SearXNG

**URL**: http://100.111.244.124:8889

SearXNG provides private, self-hosted web search.

### 5.1 Configure Search Engines

Edit `searxng/settings.yml` on your server:

```yaml
search:
  safe_search: 0
  autocomplete: "google"

engines:
  - name: google
    enabled: true
  - name: bing
    enabled: true
  - name: duckduckgo
    enabled: true
  - name: wikipedia
    enabled: true
  - name: github
    enabled: true
```

### 5.2 Use in Manic AI

The API already integrates SearXNG. Enable web search in chat:

```bash
curl -X POST http://100.111.244.124:8081/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What are the latest AI news?"}],
    "use_web_search": true
  }'
```

### 5.3 Use in n8n Workflows

Create an HTTP Request node:
- URL: `http://ai-searxng:8080/search?q={{query}}&format=json`
- Method: GET

---

## Phase 6: Alternative Chat with Open WebUI

**URL**: http://100.111.244.124:3006

Open WebUI is a feature-rich ChatGPT-like interface.

### 6.1 Features

- Multi-model chat
- Image generation (with compatible models)
- Voice input/output
- Document upload
- Chat history
- User management

### 6.2 Configuration

Open WebUI auto-connects to Ollama. Additional settings:

1. **Enable RAG**: Settings → Documents → Enable
2. **Add Web Search**: Settings → Web Search → Enable SearXNG
   - URL: `http://ai-searxng:8080`
3. **Customize Models**: Admin → Models → Add aliases

### 6.3 When to Use Which UI

| Use Case | Recommended UI |
|----------|----------------|
| Quick chat | Manic AI Frontend |
| Document Q&A | Manic AI Frontend (RAG) |
| Advanced features | Open WebUI |
| Image generation | Open WebUI |
| API testing | Manic AI API docs |

---

## Phase 7: Dual RAG System (Supabase + Qdrant)

Your Manic AI API now supports **both** Supabase (pgvector) and Qdrant for RAG storage and search.

### 7.1 Architecture Overview

| Feature | Supabase (pgvector) | Qdrant |
|---------|---------------------|--------|
| **Hybrid Search** | ✅ Vector + BM25 keyword | ❌ Vector only |
| **SQL Queries** | ✅ Full SQL support | ❌ No SQL |
| **Row Level Security** | ✅ Built-in RLS | ❌ Manual filtering |
| **Speed** | Fast | Very Fast |
| **Best For** | User data, complex queries | High-volume similarity search |

### 7.2 API Endpoints - Dual Backend Support

#### Search Documents (Unified)

```bash
# Search Supabase only (default) - supports hybrid search
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning basics",
    "backend": "supabase",
    "use_hybrid": true,
    "top_k": 5
  }'

# Search Qdrant only - fast vector search
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning basics",
    "backend": "qdrant",
    "top_k": 5
  }'

# Search BOTH backends (deduplicated, best results)
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning basics",
    "backend": "both",
    "top_k": 5
  }'
```

#### Ingest Documents (Dual Storage)

```bash
# Ingest to both backends (default)
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your document content here...",
    "filename": "document.txt",
    "backend": "both"
  }'

# Ingest to Supabase only
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your document content...",
    "filename": "doc.txt",
    "backend": "supabase"
  }'

# Ingest to Qdrant only
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your document content...",
    "filename": "doc.txt",
    "backend": "qdrant"
  }'
```

### 7.3 Qdrant Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/qdrant/collections` | GET | List all Qdrant collections |
| `/qdrant/collections/{name}` | POST | Create a new collection |
| `/qdrant/collections/{name}` | GET | Get collection info |
| `/qdrant/collections/{name}` | DELETE | Delete a collection |
| `/qdrant/search/{name}` | POST | Search a specific collection |

```bash
# List all Qdrant collections
curl http://100.111.244.124:8081/qdrant/collections

# Create a new collection
curl -X POST "http://100.111.244.124:8081/qdrant/collections/my-docs?vector_size=768"

# Get collection info
curl http://100.111.244.124:8081/qdrant/collections/documents

# Search a specific collection
curl -X POST "http://100.111.244.124:8081/qdrant/search/documents?query=your+search&top_k=5"

# Delete a collection
curl -X DELETE http://100.111.244.124:8081/qdrant/collections/my-docs
```

### 7.4 Supabase Collections Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/collections` | GET | List all RAG collections |
| `/collections` | POST | Create a new collection |
| `/collections/{id}` | DELETE | Delete a collection |

```bash
# List all collections
curl "http://100.111.244.124:8081/collections"

# Create a new collection
curl -X POST "http://100.111.244.124:8081/collections?name=My%20Docs&description=Project%20documentation"

# Delete a collection
curl -X DELETE http://100.111.244.124:8081/collections/uuid-here
```

### 7.5 Create Qdrant Collections (Direct)

```bash
# Create 'documents' collection (default for ingestion)
curl -X PUT http://100.111.244.124:6333/collections/documents \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 768, "distance": "Cosine"}}'

# Create 'code' collection for code snippets
curl -X PUT http://100.111.244.124:6333/collections/code \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 768, "distance": "Cosine"}}'

# Create 'knowledge_base' collection
curl -X PUT http://100.111.244.124:6333/collections/knowledge_base \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 768, "distance": "Cosine"}}'

# Verify collections
curl http://100.111.244.124:6333/collections
```

### 7.6 Qdrant Dashboard

Access the Qdrant web dashboard at: **http://100.111.244.124:6333/dashboard**

Features:
- View all collections
- Browse stored vectors
- Test similarity searches
- Monitor performance metrics

### 7.7 When to Use Which Backend

| Scenario | Recommended Backend |
|----------|---------------------|
| User-specific documents (needs RLS) | `supabase` |
| High-volume search (millions of docs) | `qdrant` |
| Hybrid search (vector + keyword) | `supabase` |
| Maximum search speed | `qdrant` |
| Complex SQL queries on metadata | `supabase` |
| Best accuracy (combine results) | `both` |

### 7.8 Use in Flowise

Add Qdrant nodes in Flowise for vector retrieval in your flows:
- **Qdrant URL**: `http://qdrant:6333`
- **Collection**: `documents`

---

## Phase 8: Integration Architecture

### 8.1 Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACES                                │
├─────────────────────────────────────────────────────────────────────────┤
│  Manic AI Frontend   │   Open WebUI   │   Flowise   │   Custom Apps    │
│       :3000          │     :3006      │    :3008    │                  │
└──────────┬───────────┴───────┬────────┴──────┬──────┴────────┬─────────┘
           │                   │               │               │
           ▼                   ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              MANIC AI API                                │
│                                 :8081                                    │
│  /chat  │  /ingest  │  /search  │  /models  │  /documents  │  /health  │
└────┬────┴─────┬─────┴─────┬─────┴─────┬─────┴──────┬───────┴────┬──────┘
     │          │           │           │            │            │
     ▼          ▼           ▼           ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Ollama  │ │Supabase │ │ Qdrant  │ │  Redis  │ │SearXNG  │ │Langfuse │
│ :11434  │ │  :5433  │ │  :6333  │ │  :6380  │ │  :8889  │ │  :3007  │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
     │
     ▼
┌─────────────────────┐
│    LLM Models       │
│  llama3.2, mistral  │
│  codellama, etc.    │
└─────────────────────┘
```

### 8.2 Automation Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              n8n WORKFLOWS                               │
│                                 :5679                                    │
└────┬────────────┬────────────┬────────────┬────────────┬───────────────┘
     │            │            │            │            │
     ▼            ▼            ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────────┐
│ Webhooks│ │  Cron   │ │  Email  │ │  Slack  │ │  External APIs      │
│         │ │ Triggers│ │ Triggers│ │ Triggers│ │  (GitHub, etc.)     │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────────────────┘
```

---

## Phase 9: Security Checklist

### 9.1 Current Security

- [x] All services behind Tailscale VPN
- [x] Supabase Studio protected with basic auth
- [x] Supabase API uses JWT authentication
- [x] Services not exposed to public internet

### 9.2 Recommended Additions

- [ ] Add basic auth to n8n
- [ ] Add basic auth to Langfuse
- [ ] Enable Open WebUI authentication
- [ ] Set strong Flowise password
- [ ] Regular database backups
- [ ] Monitor logs for anomalies

### 9.3 Add Auth to n8n

Update docker-compose.yml n8n environment:

```yaml
environment:
  - N8N_BASIC_AUTH_ACTIVE=true
  - N8N_BASIC_AUTH_USER=admin
  - N8N_BASIC_AUTH_PASSWORD=YourSecurePassword
```

---

## Phase 10: Maintenance & Monitoring

### 10.1 Daily Tasks

```bash
# Check all services
docker compose ps

# View recent logs
docker compose logs --tail=50

# Check disk usage
docker system df
```

### 10.2 Weekly Tasks

```bash
# Backup Supabase database
docker exec ai-supabase-db pg_dump -U postgres postgres > backup_$(date +%Y%m%d).sql

# Backup n8n workflows
docker exec ai-n8n n8n export:workflow --all --output=/home/node/.n8n/backups/

# Update containers
docker compose pull
docker compose up -d
```

### 10.3 Health Check Script

Create `health-check.sh`:

```bash
#!/bin/bash
services=(
  "http://100.111.244.124:3000|Frontend"
  "http://100.111.244.124:8081/health|API"
  "http://100.111.244.124:11434|Ollama"
  "http://100.111.244.124:5679|n8n"
  "http://100.111.244.124:3008|Flowise"
)

for service in "${services[@]}"; do
  url="${service%%|*}"
  name="${service##*|}"
  if curl -s --max-time 5 "$url" > /dev/null; then
    echo "✓ $name is UP"
  else
    echo "✗ $name is DOWN"
  fi
done
```

---

## Quick Start Checklist

### Immediate Actions

1. [ ] Pull all Ollama models
2. [ ] Login to Supabase Studio and verify tables
3. [ ] Create first n8n workflow
4. [ ] Login to Flowise and create first flow
5. [ ] Create Langfuse account and project
6. [ ] Test SearXNG search

### First Week Goals

1. [ ] Build document ingestion workflow in n8n
2. [ ] Create RAG chatbot in Flowise
3. [ ] Integrate Langfuse with API
4. [ ] Set up automated backups
5. [ ] Add auth to remaining services

### First Month Goals

1. [ ] Connect external services (Slack, email, etc.)
2. [ ] Build custom AI agents
3. [ ] Optimize model selection per use case
4. [ ] Create monitoring dashboard
5. [ ] Document custom workflows

---

## Credentials Reference

| Service | URL | Username | Password |
|---------|-----|----------|----------|
| Supabase Studio | :3005 | admin | (htpasswd) |
| Supabase Auth | :8001 | markvitale21@gmail.com | L0c4Linf0$ |
| n8n | :5679 | markvitale21@gmail.com | L0c4Linf0$ |
| Flowise | :3008 | admin | (FLOWISE_PASSWORD) |
| Langfuse | :3007 | (create account) | - |
| Open WebUI | :3006 | - | (no auth) |

## API Endpoints Quick Reference

### Core Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/services/status` | GET | All service statuses |
| `/models` | GET | List Ollama models |
| `/models/pull` | POST | Pull new model |
| `/chat` | POST | Chat with LLM |
| `/chat/stream` | POST | Streaming chat |
| `/embed` | POST | Generate embeddings |

### RAG Endpoints (Dual Backend)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | Search documents (backend: supabase/qdrant/both) |
| `/ingest` | POST | Ingest document (backend: supabase/qdrant/both) |
| `/documents` | GET | List documents |
| `/documents/{id}` | DELETE | Delete document |
| `/collections` | GET | List Supabase collections |
| `/collections` | POST | Create collection |

### Qdrant Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/qdrant/collections` | GET | List Qdrant collections |
| `/qdrant/collections/{name}` | POST | Create collection |
| `/qdrant/collections/{name}` | GET | Get collection info |
| `/qdrant/collections/{name}` | DELETE | Delete collection |
| `/qdrant/search/{name}` | POST | Search collection |

---

*Generated for Manic AI v2.0.0*
*Tailscale IP: 100.111.244.124*
