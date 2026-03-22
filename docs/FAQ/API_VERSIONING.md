# API Versioning Strategy

## Current State

All endpoints are under `/v1/`. The API uses URL path versioning (`/v1/`, `/v2/`).

## Versioning Rules

### Non-breaking changes (no version bump needed)
- Adding new fields to response objects
- Adding new optional query parameters
- Adding new endpoints
- Adding new enum values to existing fields
- Changing error messages (not error codes)

### Breaking changes (require new version)
- Removing or renaming response fields
- Changing field types
- Removing endpoints
- Changing required parameters
- Changing authentication methods
- Changing the envelope structure

## Migration Strategy

When a v2 is needed:

1. **Create v2 router**: `api/routers/v2/` directory
2. **Mount alongside v1**: Both versions active simultaneously
3. **Deprecation headers**: v1 responses include `Sunset` and `Deprecation` headers
4. **Migration period**: Minimum 3 months between deprecation announcement and removal
5. **Documentation**: Publish migration guide with before/after examples

## Sunset Process

```
Phase 1: Announce (Month 0)
  - Add Deprecation header to v1 responses
  - Publish migration guide
  - v2 goes live alongside v1

Phase 2: Warning (Month 1-2)
  - Add Sunset header with date
  - Log v1 usage for tracking migration progress

Phase 3: Removal (Month 3+)
  - v1 returns 410 Gone with migration link
  - Remove v1 code
```

## Current Endpoints by Router

### health (public — no auth required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Basic health check |
| GET | `/services/status` | All service status |
| GET | `/services/status/stream` | SSE stream of live service status |
| GET | `/metrics` | Prometheus metrics (not in OpenAPI schema) |

### chat (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat` | Chat completion (RAG-augmented) |
| POST | `/v1/chat/stream` | Streaming chat via SSE |

### search (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/search` | Hybrid vector + BM25 document search |
| POST | `/v1/search/explain` | Search with scoring breakdown |

### ingest (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/embed` | Generate and store embeddings |
| POST | `/v1/ingest` | Ingest document (chunk + embed + store) |
| GET | `/v1/ingest/{document_id}/status` | Ingestion job status |

### documents (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/documents` | List documents |
| DELETE | `/v1/documents/{document_id}` | Delete document |
| GET | `/v1/documents/{document_id}/chunks` | Inspect document chunks |

### collections (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/collections` | List collections |
| POST | `/v1/collections` | Create collection |
| DELETE | `/v1/collections/{collection_id}` | Delete collection |

### qdrant (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/qdrant/collections` | List Qdrant collections |
| POST | `/v1/qdrant/collections/{collection_name}` | Create Qdrant collection |
| GET | `/v1/qdrant/collections/{collection_name}` | Get Qdrant collection info |
| DELETE | `/v1/qdrant/collections/{collection_name}` | Delete Qdrant collection |
| POST | `/v1/qdrant/search/{collection_name}` | Vector search in a collection |

### analytics (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/analytics/usage` | Usage analytics |
| GET | `/v1/analytics/models` | Model usage analytics |
| GET | `/v1/analytics/rag` | RAG quality analytics |
| GET | `/v1/analytics/services/history` | Service health history |

### system (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/system/info` | System info and config |
| POST | `/v1/system/cache/clear` | Clear embedding cache |
| GET | `/v1/rag/stats` | RAG pipeline statistics |

### models (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/models` | List available Ollama models |
| GET | `/v1/api/tags` | Ollama-compatible tags endpoint |
| POST | `/v1/models/pull` | Pull a model from Ollama registry |
| DELETE | `/v1/models/{name}` | Delete a model |

### agent (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/agent/run` | Start a Generator-Critic agent run |
| GET | `/v1/agent/{run_id}/status` | Poll agent run status |
| POST | `/v1/agent/stream` | Streaming agent run via SSE |

### eval (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/eval/run` | Run RAG evaluation on a query |
| POST | `/v1/eval/batch` | Batch RAG evaluation |
| GET | `/v1/eval/search-history` | Search history analytics |

### feedback (`/v1/`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/feedback` | Submit chat response feedback |
| GET | `/v1/feedback/stats` | Feedback statistics |

## Header Convention

```
Deprecation: true
Sunset: Sat, 01 Jan 2027 00:00:00 GMT
Link: <https://docs.example.com/migration>; rel="sunset"
```
