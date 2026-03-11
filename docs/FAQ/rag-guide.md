# Manic AI - RAG (Retrieval-Augmented Generation) Guide

Complete documentation for using the RAG system in Manic AI.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [API Endpoints](#api-endpoints)
4. [Document Ingestion](#document-ingestion)
5. [Searching Documents](#searching-documents)
6. [Using RAG with Chat](#using-rag-with-chat)
7. [Collections](#collections)
8. [Configuration](#configuration)
9. [cURL Examples](#curl-examples)
10. [Python Examples](#python-examples)
11. [JavaScript Examples](#javascript-examples)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The Manic AI RAG system allows you to:

- **Ingest documents** - Upload text content that gets chunked and embedded
- **Search semantically** - Find relevant content using vector similarity
- **Hybrid search** - Combine vector search with keyword (BM25) matching
- **Augment chat** - Automatically inject relevant context into AI conversations

### Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Document  │────▶│   Chunker   │────▶│  Ollama Embed   │
│   Content   │     │  (500 char) │     │ (nomic-embed)   │
└─────────────┘     └─────────────┘     └────────┬────────┘
                                                 │
                                                 ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│    Query    │────▶│   Embed     │────▶│   PostgreSQL    │
│             │     │   Query     │     │   + pgvector    │
└─────────────┘     └─────────────┘     └────────┬────────┘
                                                 │
                                                 ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Response  │◀────│   Ollama    │◀────│ Context + Query │
│             │     │    Chat     │     │                 │
└─────────────┘     └─────────────┘     └─────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Embedding Model** | `nomic-embed-text` (768 dimensions) |
| **Vector Store** | PostgreSQL with pgvector extension |
| **Search Algorithm** | HNSW index with cosine similarity |
| **Hybrid Search** | RRF (Reciprocal Rank Fusion) of vector + BM25 |

---

## Quick Start

### Base URL

```
http://100.111.244.124:8081
```

### 1. Ingest a Document

```bash
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Manic AI is a powerful AI platform that combines local LLMs with RAG capabilities.",
    "filename": "about.txt"
  }'
```

### 2. Search Your Documents

```bash
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Manic AI?"
  }'
```

### 3. Chat with RAG Context

```bash
curl -X POST http://100.111.244.124:8081/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is Manic AI?"}],
    "use_rag": true
  }'
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest` | POST | Upload and process a document |
| `/search` | POST | Search documents semantically |
| `/documents` | GET | List all documents |
| `/documents/{id}` | DELETE | Delete a document |
| `/chat` | POST | Chat with optional RAG |
| `/chat/stream` | POST | Streaming chat with optional RAG |
| `/embed` | POST | Generate embeddings for text |

---

## Document Ingestion

### POST `/ingest`

Upload text content to be chunked, embedded, and stored.

#### Request Body

```json
{
  "content": "string (required) - The text content to ingest",
  "filename": "string (required) - Name for the document",
  "content_type": "string (optional) - MIME type, default: text/plain",
  "user_id": "uuid (optional) - Associate with a user",
  "collection_id": "uuid (optional) - Add to a collection",
  "metadata": "object (optional) - Custom metadata",
  "chunk_size": "integer (optional) - Characters per chunk, default: 500",
  "chunk_overlap": "integer (optional) - Overlap between chunks, default: 50"
}
```

#### Response

```json
{
  "document_id": "uuid - Unique identifier for the document",
  "filename": "string - The filename provided",
  "chunks_created": "integer - Number of chunks generated",
  "status": "string - 'completed' or 'failed'"
}
```

#### Example: Ingest a Text File

```bash
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "PostgreSQL is a powerful open-source relational database. It supports advanced features like JSON, full-text search, and vector operations through extensions like pgvector.",
    "filename": "postgres-guide.txt",
    "metadata": {
      "author": "Admin",
      "category": "database"
    }
  }'
```

#### Example: Ingest with Custom Chunking

```bash
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Your very long document content here...",
    "filename": "long-doc.txt",
    "chunk_size": 1000,
    "chunk_overlap": 100
  }'
```

### Chunking Behavior

The system intelligently chunks your content:

1. **Chunk Size**: Default 500 characters per chunk
2. **Smart Breaks**: Prefers breaking at sentence boundaries (`.`) or newlines
3. **Overlap**: 50 character overlap between chunks for context continuity
4. **Minimum Break Point**: Won't break before 50% of chunk size

---

## Searching Documents

### POST `/search`

Search your documents using semantic similarity and/or keyword matching.

#### Request Body

```json
{
  "query": "string (required) - The search query",
  "top_k": "integer (optional) - Number of results, default: 5",
  "threshold": "float (optional) - Minimum similarity 0-1, default: 0.7",
  "use_hybrid": "boolean (optional) - Enable hybrid search, default: true",
  "collection_id": "uuid (optional) - Filter by collection",
  "user_id": "uuid (optional) - Filter by user"
}
```

#### Response

```json
[
  {
    "id": "uuid - Chunk ID",
    "document_id": "uuid - Parent document ID",
    "content": "string - The chunk text",
    "metadata": "object - Chunk metadata",
    "score": "float - Combined relevance score",
    "vector_score": "float - Semantic similarity (hybrid only)",
    "keyword_score": "float - BM25 keyword score (hybrid only)"
  }
]
```

#### Example: Basic Search

```bash
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How does PostgreSQL handle vectors?"
  }'
```

#### Example: Search with More Results

```bash
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database performance",
    "top_k": 10,
    "threshold": 0.5
  }'
```

#### Example: Vector-Only Search (No Hybrid)

```bash
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning embeddings",
    "use_hybrid": false
  }'
```

### Search Types Explained

| Type | Description | Best For |
|------|-------------|----------|
| **Hybrid (default)** | Combines vector + keyword with RRF | General purpose, best accuracy |
| **Vector Only** | Pure semantic similarity | Conceptual queries, paraphrased content |

---

## Using RAG with Chat

### POST `/chat`

Chat with the AI, optionally augmented with document context.

#### Request Body

```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is pgvector?"}
  ],
  "model": "string (optional) - Model name, default: llama3.2:3b",
  "temperature": "float (optional) - Creativity 0-1, default: 0.7",
  "use_rag": "boolean (optional) - Enable RAG, default: false",
  "collection_id": "uuid (optional) - Limit RAG to collection",
  "user_id": "uuid (optional) - Limit RAG to user's documents"
}
```

#### Response

```json
{
  "id": "uuid - Response ID",
  "model": "string - Model used",
  "message": {
    "role": "assistant",
    "content": "The AI response..."
  },
  "sources": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "content": "Relevant chunk content...",
      "score": 0.85
    }
  ]
}
```

#### Example: Chat WITHOUT RAG

```bash
curl -X POST http://100.111.244.124:8081/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```

#### Example: Chat WITH RAG

```bash
curl -X POST http://100.111.244.124:8081/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Explain the vector features in our database docs"}
    ],
    "use_rag": true
  }'
```

#### Example: RAG with Specific Collection

```bash
curl -X POST http://100.111.244.124:8081/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What are the API endpoints?"}
    ],
    "use_rag": true,
    "collection_id": "123e4567-e89b-12d3-a456-426614174000"
  }'
```

### POST `/chat/stream`

Streaming version - returns Server-Sent Events (SSE).

#### SSE Event Types

| Event Type | Payload |
|------------|---------|
| `sources` | `{"type": "sources", "sources": [...]}` - RAG sources found |
| `content` | `{"type": "content", "content": "text"}` - Token from AI |
| `done` | `{"type": "done"}` - Stream complete |
| `error` | `{"type": "error", "error": "message"}` - Error occurred |

#### Example: Streaming Chat with RAG

```bash
curl -N -X POST http://100.111.244.124:8081/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Summarize our documentation"}
    ],
    "use_rag": true
  }'
```

---

## Collections

Collections let you organize documents into groups for filtered searching.

### Database Schema

```sql
-- Collections table
CREATE TABLE rag.collections (
    id UUID PRIMARY KEY,
    user_id UUID,
    name TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    embedding_model TEXT DEFAULT 'nomic-embed-text',
    metadata JSONB DEFAULT '{}'
);

-- Document-Collection mapping
CREATE TABLE rag.document_collections (
    document_id UUID,
    collection_id UUID,
    PRIMARY KEY (document_id, collection_id)
);
```

### Creating a Collection (SQL)

```sql
INSERT INTO rag.collections (id, name, description)
VALUES (
    uuid_generate_v4(),
    'Technical Docs',
    'All technical documentation'
);
```

### Adding Document to Collection

When ingesting, include the `collection_id`:

```bash
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "API documentation content...",
    "filename": "api-docs.txt",
    "collection_id": "your-collection-uuid"
  }'
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model for embeddings |
| `CHAT_MODEL` | `llama3.2:3b` | Default chat model |
| `VECTOR_DIMENSION` | `768` | Embedding dimensions |
| `RAG_TOP_K` | `5` | Default results per search |
| `RAG_THRESHOLD` | `0.7` | Minimum similarity score |
| `RAG_KEYWORD_WEIGHT` | `0.3` | Weight for keyword vs vector (0-1) |

### Tuning Search Quality

#### Increase Results
```json
{"query": "...", "top_k": 10}
```

#### Lower Threshold for More Matches
```json
{"query": "...", "threshold": 0.5}
```

#### Disable Hybrid (Vector Only)
```json
{"query": "...", "use_hybrid": false}
```

---

## cURL Examples

### Complete Workflow

```bash
# 1. Check API health
curl http://100.111.244.124:8081/health

# 2. List available models
curl http://100.111.244.124:8081/models

# 3. Ingest a document
curl -X POST http://100.111.244.124:8081/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Manic AI uses Ollama for local LLM inference. It supports models like llama3.2, mistral, and codellama. The embedding model nomic-embed-text generates 768-dimensional vectors for semantic search.",
    "filename": "manic-overview.txt"
  }'

# 4. List documents
curl "http://100.111.244.124:8081/documents"

# 5. Search documents
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What embedding model is used?"}'

# 6. Chat with RAG
curl -X POST http://100.111.244.124:8081/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What models does Manic AI support?"}],
    "use_rag": true
  }'

# 7. Delete a document
curl -X DELETE http://100.111.244.124:8081/documents/YOUR_DOCUMENT_ID
```

### Generate Embeddings

```bash
curl -X POST http://100.111.244.124:8081/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

---

## Python Examples

### Basic Usage

```python
import requests

API_URL = "http://100.111.244.124:8081"

# Ingest a document
def ingest_document(content: str, filename: str):
    response = requests.post(f"{API_URL}/ingest", json={
        "content": content,
        "filename": filename
    })
    return response.json()

# Search documents
def search(query: str, top_k: int = 5):
    response = requests.post(f"{API_URL}/search", json={
        "query": query,
        "top_k": top_k
    })
    return response.json()

# Chat with RAG
def chat_with_rag(message: str):
    response = requests.post(f"{API_URL}/chat", json={
        "messages": [{"role": "user", "content": message}],
        "use_rag": True
    })
    return response.json()

# Example usage
result = ingest_document(
    "Python is a programming language known for its readability.",
    "python-intro.txt"
)
print(f"Created document: {result['document_id']}")

results = search("What is Python?")
for r in results:
    print(f"Score: {r['score']:.2f} - {r['content'][:100]}...")

response = chat_with_rag("Tell me about Python")
print(response['message']['content'])
```

### Streaming Chat with RAG

```python
import requests
import json

def stream_chat_with_rag(message: str):
    response = requests.post(
        "http://100.111.244.124:8081/chat/stream",
        json={
            "messages": [{"role": "user", "content": message}],
            "use_rag": True
        },
        stream=True
    )

    sources = []
    full_response = ""

    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])

                if data['type'] == 'sources':
                    sources = data['sources']
                    print(f"Found {len(sources)} relevant sources")

                elif data['type'] == 'content':
                    print(data['content'], end='', flush=True)
                    full_response += data['content']

                elif data['type'] == 'done':
                    print("\n--- Done ---")

    return full_response, sources

# Usage
response, sources = stream_chat_with_rag("Explain the RAG system")
```

### Batch Ingest Multiple Files

```python
import os
import requests

API_URL = "http://100.111.244.124:8081"

def ingest_folder(folder_path: str, collection_id: str = None):
    """Ingest all .txt files from a folder."""
    results = []

    for filename in os.listdir(folder_path):
        if filename.endswith('.txt'):
            filepath = os.path.join(folder_path, filename)

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            payload = {
                "content": content,
                "filename": filename,
                "metadata": {"source_path": filepath}
            }

            if collection_id:
                payload["collection_id"] = collection_id

            response = requests.post(f"{API_URL}/ingest", json=payload)
            result = response.json()
            results.append(result)
            print(f"Ingested {filename}: {result['chunks_created']} chunks")

    return results

# Usage
ingest_folder("/path/to/documents")
```

---

## JavaScript Examples

### Basic Usage (Node.js/Browser)

```javascript
const API_URL = 'http://100.111.244.124:8081';

// Ingest a document
async function ingestDocument(content, filename, options = {}) {
  const response = await fetch(`${API_URL}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      filename,
      ...options
    })
  });
  return response.json();
}

// Search documents
async function search(query, options = {}) {
  const response = await fetch(`${API_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      top_k: options.topK || 5,
      use_hybrid: options.useHybrid !== false
    })
  });
  return response.json();
}

// Chat with RAG
async function chatWithRag(message, options = {}) {
  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: [{ role: 'user', content: message }],
      use_rag: true,
      ...options
    })
  });
  return response.json();
}

// Example usage
(async () => {
  // Ingest
  const doc = await ingestDocument(
    'JavaScript is a versatile programming language.',
    'js-intro.txt'
  );
  console.log('Document ID:', doc.document_id);

  // Search
  const results = await search('What is JavaScript?');
  console.log('Found:', results.length, 'results');

  // Chat
  const response = await chatWithRag('Tell me about JavaScript');
  console.log('AI:', response.message.content);
})();
```

### Streaming Chat (Browser)

```javascript
async function streamChatWithRag(message, onToken, onSources) {
  const response = await fetch('http://100.111.244.124:8081/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: [{ role: 'user', content: message }],
      use_rag: true
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));

        if (data.type === 'sources' && onSources) {
          onSources(data.sources);
        } else if (data.type === 'content' && onToken) {
          onToken(data.content);
        } else if (data.type === 'done') {
          return;
        }
      }
    }
  }
}

// Usage
let fullResponse = '';
await streamChatWithRag(
  'Explain the system',
  (token) => {
    fullResponse += token;
    document.getElementById('output').textContent = fullResponse;
  },
  (sources) => {
    console.log('RAG Sources:', sources);
  }
);
```

---

## Troubleshooting

### Common Issues

#### 1. "Database not connected"

**Error**: `503 - Database not connected`

**Solution**: Check PostgreSQL is running:
```bash
docker ps | grep supabase-db
docker logs ai-supabase-db
```

#### 2. "Ollama error" on Ingest

**Error**: `502 - Ollama error`

**Solution**: Ensure embedding model is pulled:
```bash
docker exec ai-ollama ollama pull nomic-embed-text
```

#### 3. Empty Search Results

**Causes**:
- Threshold too high (try `0.5` instead of `0.7`)
- No documents ingested
- Query too different from content

**Debug**:
```bash
# Check document count
curl http://100.111.244.124:8081/documents

# Try lower threshold
curl -X POST http://100.111.244.124:8081/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "threshold": 0.3}'
```

#### 4. RAG Not Finding Context

**Causes**:
- `use_rag: false` (default)
- Collection filter too restrictive
- Low similarity scores

**Solution**: Always set `use_rag: true` for RAG:
```json
{
  "messages": [...],
  "use_rag": true
}
```

#### 5. Slow Ingestion

**Cause**: Large documents generate many embeddings

**Solutions**:
- Increase chunk size: `"chunk_size": 1000`
- Use faster embedding model
- Pre-process documents to remove unnecessary content

### Checking Service Health

```bash
# API health
curl http://100.111.244.124:8081/health

# All services status
curl http://100.111.244.124:8081/services/status
```

### Database Direct Access

Connect via Supabase Studio at `http://100.111.244.124:3005`

Or via SQL:
```sql
-- Count documents
SELECT COUNT(*) FROM rag.documents;

-- Count chunks
SELECT COUNT(*) FROM rag.chunks;

-- View recent documents
SELECT id, filename, status, chunk_count, created_at
FROM rag.documents
ORDER BY created_at DESC
LIMIT 10;

-- Check embedding dimensions
SELECT id, array_length(embedding::float[], 1) as dims
FROM rag.chunks
LIMIT 1;
```

---

## Quick Reference Card

| Action | Endpoint | Key Parameters |
|--------|----------|----------------|
| **Ingest** | `POST /ingest` | `content`, `filename` |
| **Search** | `POST /search` | `query`, `top_k`, `use_hybrid` |
| **Chat** | `POST /chat` | `messages`, `use_rag` |
| **Stream** | `POST /chat/stream` | `messages`, `use_rag` |
| **List Docs** | `GET /documents` | `user_id`, `collection_id` |
| **Delete Doc** | `DELETE /documents/{id}` | - |
| **Embed** | `POST /embed` | `text` |
| **Health** | `GET /health` | - |
| **Status** | `GET /services/status` | - |

---

*Generated for Manic AI v2.0.0*
*API Base: http://100.111.244.124:8081*
