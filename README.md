# Manic-AI

Full-stack AI platform with RAG (Retrieval-Augmented Generation) capabilities.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |
| API | FastAPI (Python) |
| Vector DB | Supabase (pgvector + BM25) + Qdrant |
| LLM Inference | Ollama (local models) |
| Infrastructure | Docker Compose (18 services) |

## Quick Start

```bash
cp .env.example .env   # fill in your values
docker compose up -d
```

Open [http://localhost:3000](http://localhost:3000)

## Documentation

Full documentation is in [`docs/FAQ/`](docs/FAQ/README.md).

## License

See [LICENSE](LICENSE).
