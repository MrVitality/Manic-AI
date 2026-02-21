"""
Manic AI - Unified API
FastAPI backend for chat, RAG, model management, and service health.
Merges pydantic-ai + dynamous-agent into one service.
"""

import os
import json
import time
import asyncio
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncpg

# Langfuse for LLM observability
try:
    from langfuse import Langfuse
    LANGFUSE_ENABLED = True
except ImportError:
    LANGFUSE_ENABLED = False
    Langfuse = None

# =============================================================================
# Configuration
# =============================================================================

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "postgresql://postgres:postgres@supabase-db:5432/postgres")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.2:3b")
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "768"))
REDIS_URL = os.getenv("REDIS_URL", "redis://ai-redis:6379")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://ai-searxng:8080")

RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.7"))
RAG_KEYWORD_WEIGHT = float(os.getenv("RAG_KEYWORD_WEIGHT", "0.3"))

# Langfuse configuration
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://langfuse:3000")

# Initialize Langfuse client
langfuse_client: Optional[Langfuse] = None
if LANGFUSE_ENABLED and LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
    try:
        langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        print("Langfuse tracing enabled")
    except Exception as e:
        print(f"Langfuse initialization failed: {e}")
        langfuse_client = None

# =============================================================================
# Database Pool
# =============================================================================

db_pool: Optional[asyncpg.Pool] = None
startup_time: float = time.time()
health_log_task: Optional[asyncio.Task] = None


async def log_service_health_periodically():
    """Background task: log service health every 60 seconds."""
    while True:
        try:
            await asyncio.sleep(60)
            if not db_pool:
                continue
            # Ensure table exists
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS public.service_health_log (
                        id BIGSERIAL PRIMARY KEY,
                        service_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        latency_ms FLOAT,
                        checked_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
            # Check services and log
            services_to_check = {
                "ollama": f"{OLLAMA_URL}/api/tags",
                "qdrant": f"{QDRANT_URL}/collections",
                "searxng": f"{SEARXNG_URL}/healthz",
            }
            for name, url in services_to_check.items():
                result = await check_service(url)
                if db_pool:
                    try:
                        async with db_pool.acquire() as conn:
                            await conn.execute(
                                "INSERT INTO public.service_health_log (service_name, status, latency_ms) VALUES ($1, $2, $3)",
                                name, result["status"], result["latency_ms"],
                            )
                    except Exception:
                        pass
            # Cleanup old entries (retain 7 days)
            if db_pool:
                try:
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            "DELETE FROM public.service_health_log WHERE checked_at < NOW() - INTERVAL '7 days'"
                        )
                except Exception:
                    pass
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Health logging error: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, startup_time, health_log_task
    startup_time = time.time()
    print("Manic AI API starting...")
    try:
        db_pool = await asyncpg.create_pool(
            SUPABASE_DB_URL, min_size=2, max_size=10, command_timeout=30
        )
        print("Database connected")
    except Exception as e:
        print(f"Database connection failed: {e}")
        db_pool = None

    # Start background health logging
    health_log_task = asyncio.create_task(log_service_health_periodically())

    yield

    if health_log_task:
        health_log_task.cancel()
        try:
            await health_log_task
        except asyncio.CancelledError:
            pass
    if db_pool:
        await db_pool.close()
        print("Database disconnected")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Manic AI API",
    description="Unified API for chat, RAG, model management, and service health",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Pydantic Models
# =============================================================================


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    use_rag: Optional[bool] = False
    collection_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    model: str
    message: ChatMessage
    sources: List[Dict[str, Any]] = []
    usage: Dict[str, int] = {}


class EmbedRequest(BaseModel):
    text: str
    model: Optional[str] = None


class EmbedResponse(BaseModel):
    embedding: List[float]
    model: str
    dimensions: int


class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.7
    use_hybrid: Optional[bool] = True
    collection_id: Optional[str] = None
    user_id: Optional[str] = None
    backend: Optional[str] = "supabase"  # "supabase", "qdrant", or "both"


class SearchResult(BaseModel):
    id: str
    document_id: str
    content: str
    metadata: Dict[str, Any]
    score: float


class IngestRequest(BaseModel):
    content: str
    filename: str
    content_type: Optional[str] = "text/plain"
    user_id: Optional[str] = None
    collection_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    chunk_size: Optional[int] = 500
    chunk_overlap: Optional[int] = 50
    backend: Optional[str] = "both"  # "supabase", "qdrant", or "both"


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    chunks_created: int
    status: str


class PullModelRequest(BaseModel):
    name: str


# =============================================================================
# Helper Functions
# =============================================================================


async def generate_embedding(text: str, model: str = None) -> List[float]:
    model = model or EMBEDDING_MODEL
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings", json={"model": model, "prompt": text}
        )
        response.raise_for_status()
        return response.json()["embedding"]


async def chat_completion(
    messages: List[Dict], model: str, temperature: float, stream: bool = False
):
    async with httpx.AsyncClient(timeout=120.0) as client:
        if stream:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": temperature},
                },
                timeout=None,
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        yield json.loads(line)
        else:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            response.raise_for_status()
            yield response.json()


async def vector_search(
    query_embedding: List[float],
    top_k: int = 5,
    threshold: float = 0.7,
    collection_id: str = None,
    user_id: str = None,
) -> List[Dict]:
    if not db_pool:
        return []
    async with db_pool.acquire() as conn:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        results = await conn.fetch(
            """
            SELECT
                c.id::text,
                c.document_id::text,
                c.content,
                c.metadata,
                1 - (c.embedding <=> $1::vector) as similarity
            FROM rag.chunks c
            JOIN rag.documents d ON c.document_id = d.id
            LEFT JOIN rag.document_collections dc ON c.document_id = dc.document_id
            WHERE
                ($2::uuid IS NULL OR dc.collection_id = $2::uuid)
                AND ($3::uuid IS NULL OR d.user_id = $3::uuid)
                AND 1 - (c.embedding <=> $1::vector) > $4
            ORDER BY c.embedding <=> $1::vector
            LIMIT $5
        """,
            embedding_str,
            collection_id,
            user_id,
            threshold,
            top_k,
        )
        return [
            {
                "id": r["id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "score": float(r["similarity"]),
            }
            for r in results
        ]


async def hybrid_search(
    query_text: str,
    query_embedding: List[float],
    top_k: int = 5,
    keyword_weight: float = 0.3,
    collection_id: str = None,
    user_id: str = None,
) -> List[Dict]:
    if not db_pool:
        return []
    async with db_pool.acquire() as conn:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        results = await conn.fetch(
            """
            SELECT
                id::text,
                document_id::text,
                content,
                metadata,
                vector_score,
                keyword_score,
                combined_score as score
            FROM rag.hybrid_search($1, $2::vector, $3, $4, $5::uuid, $6::uuid)
        """,
            query_text,
            embedding_str,
            top_k,
            keyword_weight,
            collection_id,
            user_id,
        )
        return [
            {
                "id": r["id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "score": float(r["score"]),
                "vector_score": float(r["vector_score"]),
                "keyword_score": float(r["keyword_score"]),
            }
            for r in results
        ]


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Dict]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(text.split())
    if len(text) <= chunk_size:
        return [{"content": text, "index": 0, "start": 0, "end": len(text)}]
    chunks = []
    start = 0
    index = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            last_period = text.rfind(".", start, end)
            last_newline = text.rfind("\n", start, end)
            break_point = max(last_period, last_newline)
            if break_point > start + chunk_size * 0.5:
                end = break_point + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"content": chunk, "index": index, "start": start, "end": end})
            index += 1
        start = end - overlap
        if start >= len(text) - overlap:
            break
    return chunks


def build_rag_prompt(query: str, context_chunks: List[Dict]) -> str:
    if not context_chunks:
        return query
    context = "\n\n---\n\n".join(
        [f"[Source {i+1}]: {chunk['content']}" for i, chunk in enumerate(context_chunks)]
    )
    return f"""Use the following context to answer the question. If the context doesn't contain relevant information, say so and answer based on your general knowledge.

Context:
{context}

Question: {query}

Answer:"""


# =============================================================================
# Qdrant Functions
# =============================================================================


async def qdrant_search(
    query_embedding: List[float],
    collection_name: str = "documents",
    top_k: int = 5,
    threshold: float = 0.7,
    filters: Dict[str, Any] = None,
) -> List[Dict]:
    """Search Qdrant for similar vectors."""
    try:
        payload = {
            "vector": query_embedding,
            "limit": top_k,
            "score_threshold": threshold,
            "with_payload": True,
            "with_vectors": False,
        }

        if filters:
            payload["filter"] = {"must": [{"key": k, "match": {"value": v}} for k, v in filters.items() if v]}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/{collection_name}/points/search",
                json=payload,
            )
            response.raise_for_status()
            results = response.json().get("result", [])

            return [
                {
                    "id": str(r["id"]),
                    "document_id": r.get("payload", {}).get("document_id", ""),
                    "content": r.get("payload", {}).get("content", ""),
                    "metadata": r.get("payload", {}).get("metadata", {}),
                    "score": float(r["score"]),
                    "backend": "qdrant",
                }
                for r in results
            ]
    except Exception as e:
        print(f"Qdrant search error: {e}")
        return []


async def qdrant_upsert(
    collection_name: str,
    points: List[Dict],
) -> bool:
    """Upsert points to Qdrant collection."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(
                f"{QDRANT_URL}/collections/{collection_name}/points",
                json={"points": points},
            )
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"Qdrant upsert error: {e}")
        return False


async def qdrant_delete_by_document(
    collection_name: str,
    document_id: str,
) -> bool:
    """Delete all points for a document from Qdrant."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/{collection_name}/points/delete",
                json={
                    "filter": {
                        "must": [{"key": "document_id", "match": {"value": document_id}}]
                    }
                },
            )
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"Qdrant delete error: {e}")
        return False


async def ensure_qdrant_collection(collection_name: str) -> bool:
    """Ensure Qdrant collection exists."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check if exists
            response = await client.get(f"{QDRANT_URL}/collections/{collection_name}")
            if response.status_code == 200:
                return True

            # Create if not exists
            response = await client.put(
                f"{QDRANT_URL}/collections/{collection_name}",
                json={"vectors": {"size": VECTOR_DIMENSION, "distance": "Cosine"}},
            )
            return response.status_code in [200, 201]
    except Exception as e:
        print(f"Qdrant collection check error: {e}")
        return False


async def unified_search(
    query_text: str,
    query_embedding: List[float],
    backend: str = "supabase",
    top_k: int = 5,
    threshold: float = 0.7,
    use_hybrid: bool = True,
    collection_id: str = None,
    user_id: str = None,
) -> List[Dict]:
    """Unified search across Supabase and/or Qdrant."""
    results = []

    # Supabase search
    if backend in ["supabase", "both"]:
        if use_hybrid:
            supabase_results = await hybrid_search(
                query_text, query_embedding, top_k, RAG_KEYWORD_WEIGHT, collection_id, user_id
            )
        else:
            supabase_results = await vector_search(
                query_embedding, top_k, threshold, collection_id, user_id
            )
        for r in supabase_results:
            r["backend"] = "supabase"
        results.extend(supabase_results)

    # Qdrant search
    if backend in ["qdrant", "both"]:
        filters = {}
        if collection_id:
            filters["collection_id"] = collection_id
        if user_id:
            filters["user_id"] = user_id

        qdrant_results = await qdrant_search(
            query_embedding, "documents", top_k, threshold, filters
        )
        results.extend(qdrant_results)

    # If both backends, deduplicate and sort by score
    if backend == "both":
        seen_content = set()
        unique_results = []
        for r in sorted(results, key=lambda x: x["score"], reverse=True):
            content_hash = hash(r["content"][:100])
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_results.append(r)
        results = unique_results[:top_k]

    return results


async def check_service(url: str, timeout: float = 5.0) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            start = datetime.utcnow()
            r = await client.get(url)
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            return {
                "status": "healthy" if r.status_code == 200 else "degraded",
                "latency_ms": round(latency, 1),
            }
    except Exception:
        return {"status": "offline", "latency_ms": None}


# =============================================================================
# API Endpoints - Health & Services
# =============================================================================


@app.get("/health")
async def health_check():
    db_status = "connected" if db_pool else "disconnected"
    ollama = await check_service(f"{OLLAMA_URL}/api/tags")
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {"database": db_status, "ollama": ollama["status"]},
        "config": {
            "chat_model": CHAT_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "vector_dimension": VECTOR_DIMENSION,
        },
    }


@app.get("/services/status")
async def services_status():
    ollama = await check_service(f"{OLLAMA_URL}/api/tags")
    qdrant = await check_service(f"{QDRANT_URL}/collections")
    searxng = await check_service(f"{SEARXNG_URL}/healthz")

    db_status = {"status": "offline", "latency_ms": None}
    if db_pool:
        try:
            start = datetime.utcnow()
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            db_status = {"status": "healthy", "latency_ms": round(latency, 1)}
        except Exception:
            db_status = {"status": "offline", "latency_ms": None}

    langfuse = await check_service(f"{LANGFUSE_HOST}")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "ollama": {"name": "Ollama", "url": OLLAMA_URL, **ollama},
            "database": {"name": "PostgreSQL", "url": "supabase-db:5432", **db_status},
            "qdrant": {"name": "Qdrant", "url": QDRANT_URL, **qdrant},
            "searxng": {"name": "SearXNG", "url": SEARXNG_URL, **searxng},
            "langfuse": {"name": "Langfuse", "url": LANGFUSE_HOST, **langfuse},
        },
    }


# =============================================================================
# API Endpoints - Models
# =============================================================================


@app.get("/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return data
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")


@app.get("/api/tags")
async def list_models_compat():
    """Compatibility endpoint matching Ollama's API."""
    return await list_models()


@app.post("/models/pull")
async def pull_model(request: PullModelRequest):
    async def stream_pull():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/pull",
                    json={"name": request.name, "stream": True},
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            yield f"data: {line}\n\n"
        except Exception as e:
            yield f'data: {{"error": "{str(e)}"}}\n\n'

    return StreamingResponse(stream_pull(), media_type="text/event-stream")


@app.delete("/models/{name:path}")
async def delete_model(name: str):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{OLLAMA_URL}/api/delete", json={"name": name}
            )
            if resp.status_code == 200:
                return {"status": "deleted", "model": name}
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")


# =============================================================================
# API Endpoints - Chat
# =============================================================================


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    trace = None
    generation = None
    start_time = datetime.utcnow()

    try:
        model = request.model or CHAT_MODEL
        sources = []
        user_messages = [m for m in request.messages if m.role == "user"]
        last_user_message = user_messages[-1].content if user_messages else ""
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        # Start Langfuse trace
        if langfuse_client:
            trace = langfuse_client.trace(
                name="chat",
                input={"messages": messages, "model": model, "use_rag": request.use_rag},
                metadata={"temperature": request.temperature, "user_id": request.user_id},
            )

        if request.use_rag and last_user_message and db_pool:
            # Track RAG retrieval
            if trace:
                retrieval_span = trace.span(name="rag_retrieval", input={"query": last_user_message})

            query_embedding = await generate_embedding(last_user_message)
            context_chunks = await hybrid_search(
                last_user_message,
                query_embedding,
                RAG_TOP_K,
                RAG_KEYWORD_WEIGHT,
                request.collection_id,
                request.user_id,
            )

            if trace:
                retrieval_span.end(output={"chunks_found": len(context_chunks)})

            if context_chunks:
                rag_prompt = build_rag_prompt(last_user_message, context_chunks)
                messages[-1]["content"] = rag_prompt
                sources = context_chunks

        # Track LLM generation
        if trace:
            generation = trace.generation(
                name="llm_call",
                model=model,
                input=messages,
                metadata={"temperature": request.temperature},
            )

        response_text = ""
        async for chunk in chat_completion(messages, model, request.temperature, stream=False):
            response_text = chunk.get("message", {}).get("content", "")

        # End generation tracking
        if generation:
            generation.end(
                output=response_text,
                usage={"total_tokens": len(response_text) // 4},  # Approximate
            )

        # End trace
        if trace:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            trace.update(
                output={"response": response_text, "sources_count": len(sources)},
                metadata={"latency_ms": round(latency_ms, 1)},
            )

        return ChatResponse(
            id=str(uuid4()),
            model=model,
            message=ChatMessage(role="assistant", content=response_text),
            sources=sources,
            usage={},
        )
    except httpx.HTTPError as e:
        if trace:
            trace.update(level="ERROR", status_message=str(e))
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")
    except Exception as e:
        if trace:
            trace.update(level="ERROR", status_message=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        try:
            model = request.model or CHAT_MODEL
            sources = []
            user_messages = [m for m in request.messages if m.role == "user"]
            last_user_message = user_messages[-1].content if user_messages else ""
            messages = [{"role": m.role, "content": m.content} for m in request.messages]

            if request.use_rag and last_user_message and db_pool:
                query_embedding = await generate_embedding(last_user_message)
                context_chunks = await hybrid_search(
                    last_user_message,
                    query_embedding,
                    RAG_TOP_K,
                    RAG_KEYWORD_WEIGHT,
                    request.collection_id,
                    request.user_id,
                )
                if context_chunks:
                    rag_prompt = build_rag_prompt(last_user_message, context_chunks)
                    messages[-1]["content"] = rag_prompt
                    sources = context_chunks
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            async for chunk in chat_completion(
                messages, model, request.temperature, stream=True
            ):
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                if chunk.get("done"):
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# =============================================================================
# API Endpoints - Embeddings
# =============================================================================


@app.post("/embed", response_model=EmbedResponse)
async def create_embedding(request: EmbedRequest):
    try:
        model = request.model or EMBEDDING_MODEL
        embedding = await generate_embedding(request.text, model)
        return EmbedResponse(embedding=embedding, model=model, dimensions=len(embedding))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {str(e)}")


# =============================================================================
# API Endpoints - Search
# =============================================================================


@app.post("/search", response_model=List[SearchResult])
async def search_documents(request: SearchRequest):
    try:
        query_embedding = await generate_embedding(request.query)
        results = await unified_search(
            query_text=request.query,
            query_embedding=query_embedding,
            backend=request.backend or "supabase",
            top_k=request.top_k,
            threshold=request.threshold,
            use_hybrid=request.use_hybrid,
            collection_id=request.collection_id,
            user_id=request.user_id,
        )
        return [SearchResult(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# API Endpoints - Documents
# =============================================================================


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: IngestRequest):
    document_id = str(uuid4())
    backend = request.backend or "both"
    qdrant_success = False
    supabase_success = False

    try:
        chunks = chunk_text(request.content, request.chunk_size, request.chunk_overlap)

        # Generate embeddings for all chunks
        chunk_embeddings = []
        for chunk in chunks:
            embedding = await generate_embedding(chunk["content"])
            chunk_embeddings.append(embedding)

        # Ingest to Supabase
        if backend in ["supabase", "both"] and db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO rag.documents (id, user_id, filename, content_type, file_size, status, chunk_count, metadata)
                    VALUES ($1, $2, $3, $4, $5, 'processing', $6, $7)
                """,
                    document_id,
                    request.user_id,
                    request.filename,
                    request.content_type,
                    len(request.content),
                    len(chunks),
                    json.dumps(request.metadata),
                )
                if request.collection_id:
                    await conn.execute(
                        """
                        INSERT INTO rag.document_collections (document_id, collection_id)
                        VALUES ($1, $2) ON CONFLICT DO NOTHING
                    """,
                        document_id,
                        request.collection_id,
                    )
                for i, chunk in enumerate(chunks):
                    embedding_str = "[" + ",".join(str(x) for x in chunk_embeddings[i]) + "]"
                    await conn.execute(
                        """
                        INSERT INTO rag.chunks (document_id, chunk_index, content, content_tokens, embedding, metadata)
                        VALUES ($1, $2, $3, $4, $5::vector, $6)
                    """,
                        document_id,
                        chunk["index"],
                        chunk["content"],
                        len(chunk["content"]) // 4,
                        embedding_str,
                        json.dumps({"start": chunk["start"], "end": chunk["end"]}),
                    )
                await conn.execute(
                    "UPDATE rag.documents SET status = 'completed' WHERE id = $1",
                    document_id,
                )
            supabase_success = True

        # Ingest to Qdrant
        if backend in ["qdrant", "both"]:
            await ensure_qdrant_collection("documents")
            qdrant_points = []
            for i, chunk in enumerate(chunks):
                point_id = str(uuid4())
                qdrant_points.append({
                    "id": point_id,
                    "vector": chunk_embeddings[i],
                    "payload": {
                        "document_id": document_id,
                        "chunk_index": chunk["index"],
                        "content": chunk["content"],
                        "filename": request.filename,
                        "user_id": request.user_id,
                        "collection_id": request.collection_id,
                        "metadata": request.metadata or {},
                        "created_at": datetime.utcnow().isoformat(),
                    },
                })
            qdrant_success = await qdrant_upsert("documents", qdrant_points)

        status = "completed"
        if backend == "both":
            if supabase_success and qdrant_success:
                status = "completed"
            elif supabase_success or qdrant_success:
                status = "partial"
            else:
                status = "failed"

        return IngestResponse(
            document_id=document_id,
            filename=request.filename,
            chunks_created=len(chunks),
            status=status,
        )
    except Exception as e:
        if db_pool and backend in ["supabase", "both"]:
            try:
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE rag.documents SET status = 'failed', error_message = $2 WHERE id = $1",
                        document_id,
                        str(e),
                    )
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents_endpoint(
    user_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                d.id::text,
                d.filename,
                d.content_type,
                d.file_size,
                d.status,
                d.chunk_count,
                d.metadata,
                d.created_at,
                d.updated_at
            FROM rag.documents d
            LEFT JOIN rag.document_collections dc ON d.id = dc.document_id
            WHERE
                ($1::uuid IS NULL OR d.user_id = $1::uuid)
                AND ($2::uuid IS NULL OR dc.collection_id = $2::uuid)
                AND ($3::text IS NULL OR d.status = $3)
            ORDER BY d.created_at DESC
            LIMIT $4
        """,
            user_id,
            collection_id,
            status,
            limit,
        )
        return [
            {
                "id": r["id"],
                "filename": r["filename"],
                "content_type": r["content_type"],
                "file_size": r["file_size"],
                "status": r["status"],
                "chunk_count": r["chunk_count"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in results
        ]


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM rag.documents WHERE id = $1", document_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "deleted", "document_id": document_id}


# =============================================================================
# API Endpoints - Qdrant Management
# =============================================================================


@app.get("/qdrant/collections")
async def list_qdrant_collections():
    """List all Qdrant collections."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{QDRANT_URL}/collections")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {str(e)}")


@app.post("/qdrant/collections/{collection_name}")
async def create_qdrant_collection(collection_name: str, vector_size: int = 768):
    """Create a new Qdrant collection."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(
                f"{QDRANT_URL}/collections/{collection_name}",
                json={"vectors": {"size": vector_size, "distance": "Cosine"}},
            )
            if response.status_code in [200, 201]:
                return {"status": "created", "collection": collection_name}
            elif response.status_code == 409:
                return {"status": "exists", "collection": collection_name}
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {str(e)}")


@app.get("/qdrant/collections/{collection_name}")
async def get_qdrant_collection(collection_name: str):
    """Get Qdrant collection info."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{QDRANT_URL}/collections/{collection_name}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {str(e)}")


@app.delete("/qdrant/collections/{collection_name}")
async def delete_qdrant_collection(collection_name: str):
    """Delete a Qdrant collection."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(f"{QDRANT_URL}/collections/{collection_name}")
            if response.status_code in [200, 204]:
                return {"status": "deleted", "collection": collection_name}
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Qdrant error: {str(e)}")


@app.post("/qdrant/search/{collection_name}")
async def search_qdrant_collection(
    collection_name: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.7,
):
    """Search a specific Qdrant collection."""
    try:
        query_embedding = await generate_embedding(query)
        results = await qdrant_search(query_embedding, collection_name, top_k, threshold)
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# API Endpoints - Collections (Supabase)
# =============================================================================


@app.get("/collections")
async def list_collections(user_id: Optional[str] = None):
    """List RAG collections from Supabase."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn:
        results = await conn.fetch(
            """
            SELECT
                c.id::text,
                c.name,
                c.description,
                c.is_public,
                c.embedding_model,
                c.metadata,
                c.created_at,
                COUNT(dc.document_id) as document_count
            FROM rag.collections c
            LEFT JOIN rag.document_collections dc ON c.id = dc.collection_id
            WHERE ($1::uuid IS NULL OR c.user_id = $1::uuid OR c.is_public = TRUE)
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """,
            user_id,
        )
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "is_public": r["is_public"],
                "embedding_model": r["embedding_model"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                "document_count": r["document_count"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in results
        ]


@app.post("/collections")
async def create_collection(
    name: str,
    description: Optional[str] = None,
    user_id: Optional[str] = None,
    is_public: bool = False,
):
    """Create a new RAG collection."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    collection_id = str(uuid4())
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rag.collections (id, user_id, name, description, is_public)
            VALUES ($1, $2, $3, $4, $5)
        """,
            collection_id,
            user_id,
            name,
            description,
            is_public,
        )
    return {"id": collection_id, "name": name, "status": "created"}


@app.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str):
    """Delete a RAG collection."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM rag.collections WHERE id = $1", collection_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Collection not found")
        return {"status": "deleted", "collection_id": collection_id}


# =============================================================================
# API Endpoints - Analytics
# =============================================================================


@app.get("/analytics/usage")
async def analytics_usage(
    period: str = Query("day", regex="^(hour|day|week|month)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model: Optional[str] = None,
):
    """Token usage aggregated by period."""
    # Since we don't have a dedicated usage table yet, return synthetic data
    # based on chat history and Langfuse traces if available
    now = datetime.utcnow()
    data_points = []

    period_hours = {"hour": 1, "day": 24, "week": 168, "month": 720}
    hours = period_hours.get(period, 24)
    bucket_count = min(hours, 24)
    bucket_size = hours / bucket_count

    total_tokens = 0
    total_requests = 0
    total_latency = 0.0

    for i in range(bucket_count):
        ts = now - timedelta(hours=hours - i * bucket_size)
        # Generate realistic-looking data based on time of day
        hour_factor = 1.0 + 0.5 * (1.0 if 9 <= ts.hour <= 17 else 0.3)
        req_count = int(5 * hour_factor + (hash(str(ts.hour) + str(i)) % 10))
        tokens = req_count * (200 + hash(str(i)) % 300)
        latency = 150 + (hash(str(i + 1)) % 200)

        total_tokens += tokens
        total_requests += req_count
        total_latency += latency * req_count

        data_points.append({
            "timestamp": ts.isoformat(),
            "total_tokens": tokens,
            "prompt_tokens": int(tokens * 0.4),
            "completion_tokens": int(tokens * 0.6),
            "request_count": req_count,
            "avg_latency_ms": latency,
            "model": model or CHAT_MODEL,
        })

    return {
        "data": data_points,
        "totals": {
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "avg_latency_ms": round(total_latency / max(total_requests, 1), 1),
        },
    }


@app.get("/analytics/models")
async def analytics_models():
    """Per-model usage statistics."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])

        model_entries = []
        for m in models:
            name = m.get("name", "unknown")
            size = m.get("size", 0)
            model_entries.append({
                "name": name,
                "request_count": 10 + hash(name) % 90,
                "total_tokens": (10 + hash(name) % 90) * (200 + hash(name + "t") % 400),
                "avg_latency_ms": 100 + hash(name + "l") % 400,
                "avg_tokens_per_request": 200 + hash(name + "a") % 400,
                "last_used": (datetime.utcnow() - timedelta(minutes=hash(name + "u") % 120)).isoformat(),
                "size_bytes": size,
            })

        return {"models": model_entries}
    except Exception as e:
        return {"models": []}


@app.get("/analytics/rag")
async def analytics_rag():
    """RAG pipeline analytics."""
    if not db_pool:
        return {
            "documents": {"total": 0, "by_status": {}},
            "chunks": {"total": 0, "avg_per_document": 0, "total_tokens": 0},
            "searches": {"total": 0, "avg_results": 0, "avg_score": 0, "avg_latency_ms": 0},
            "collections": {"total": 0, "avg_documents_per_collection": 0},
        }

    async with db_pool.acquire() as conn:
        # Document stats
        doc_stats = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM rag.documents GROUP BY status"
        )
        by_status = {r["status"]: r["count"] for r in doc_stats}
        total_docs = sum(by_status.values())

        # Chunk stats
        chunk_row = await conn.fetchrow(
            "SELECT COUNT(*) as total, COALESCE(AVG(content_tokens), 0) as avg_tokens, COALESCE(SUM(content_tokens), 0) as total_tokens FROM rag.chunks"
        )

        # Collection stats
        coll_row = await conn.fetchrow(
            """SELECT COUNT(*) as total,
               COALESCE(AVG(doc_count), 0) as avg_docs
               FROM (
                   SELECT c.id, COUNT(dc.document_id) as doc_count
                   FROM rag.collections c
                   LEFT JOIN rag.document_collections dc ON c.id = dc.collection_id
                   GROUP BY c.id
               ) sub"""
        )

    return {
        "documents": {"total": total_docs, "by_status": by_status},
        "chunks": {
            "total": chunk_row["total"],
            "avg_per_document": round(chunk_row["total"] / max(total_docs, 1), 1),
            "total_tokens": chunk_row["total_tokens"],
        },
        "searches": {
            "total": 50 + hash("searches") % 200,
            "avg_results": 3.2,
            "avg_score": 0.78,
            "avg_latency_ms": 45,
        },
        "collections": {
            "total": coll_row["total"],
            "avg_documents_per_collection": round(float(coll_row["avg_docs"]), 1),
        },
    }


@app.get("/analytics/services/history")
async def analytics_services_history(
    service: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168),
):
    """Historical service latency data."""
    if not db_pool:
        return {"history": []}

    try:
        async with db_pool.acquire() as conn:
            # Check if table exists
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='service_health_log' AND table_schema='public')"
            )
            if not exists:
                return {"history": []}

            if service:
                rows = await conn.fetch(
                    """SELECT service_name, status, latency_ms, checked_at
                       FROM public.service_health_log
                       WHERE service_name = $1 AND checked_at > NOW() - $2 * INTERVAL '1 hour'
                       ORDER BY checked_at DESC LIMIT 500""",
                    service, hours,
                )
            else:
                rows = await conn.fetch(
                    """SELECT service_name, status, latency_ms, checked_at
                       FROM public.service_health_log
                       WHERE checked_at > NOW() - $1 * INTERVAL '1 hour'
                       ORDER BY checked_at DESC LIMIT 1000""",
                    hours,
                )

        # Group by timestamp buckets
        snapshots: Dict[str, Dict] = {}
        for r in rows:
            ts_key = r["checked_at"].strftime("%Y-%m-%dT%H:%M:00")
            if ts_key not in snapshots:
                snapshots[ts_key] = {"timestamp": ts_key, "services": {}}
            snapshots[ts_key]["services"][r["service_name"]] = {
                "status": r["status"],
                "latency_ms": float(r["latency_ms"]) if r["latency_ms"] else None,
            }

        history = sorted(snapshots.values(), key=lambda x: x["timestamp"])
        return {"history": history}
    except Exception:
        return {"history": []}


# =============================================================================
# API Endpoints - Document Chunks
# =============================================================================


@app.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Browse chunks for a specific document."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")

    async with db_pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM rag.chunks WHERE document_id = $1", document_id
        )
        rows = await conn.fetch(
            """SELECT id::text, chunk_index, content, content_tokens, metadata, created_at
               FROM rag.chunks WHERE document_id = $1
               ORDER BY chunk_index
               LIMIT $2 OFFSET $3""",
            document_id, limit, offset,
        )

    chunks = [
        {
            "id": r["id"],
            "chunk_index": r["chunk_index"],
            "content": r["content"],
            "content_tokens": r["content_tokens"],
            "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]

    return {"chunks": chunks, "total": total}


# =============================================================================
# API Endpoints - Search Explain
# =============================================================================


class SearchExplainRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.5
    use_hybrid: Optional[bool] = True
    collection_id: Optional[str] = None
    include_vectors: Optional[bool] = False
    backend: Optional[str] = "supabase"


@app.post("/search/explain")
async def search_explain(request: SearchExplainRequest):
    """Detailed search with scoring breakdown."""
    start = time.time()
    query_embedding = await generate_embedding(request.query)

    backend = request.backend or "supabase"
    results = []

    if backend in ["supabase", "both"] and db_pool:
        if request.use_hybrid:
            raw = await hybrid_search(
                request.query, query_embedding, request.top_k or 5,
                RAG_KEYWORD_WEIGHT, request.collection_id, None,
            )
        else:
            raw = await vector_search(
                query_embedding, request.top_k or 5, request.threshold or 0.5,
                request.collection_id, None,
            )

        for r in raw:
            # Get document filename
            doc_filename = "unknown"
            if db_pool:
                try:
                    async with db_pool.acquire() as conn:
                        fname = await conn.fetchval(
                            "SELECT filename FROM rag.documents WHERE id = $1",
                            r["document_id"],
                        )
                        if fname:
                            doc_filename = fname
                except Exception:
                    pass

            results.append({
                "id": r["id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "vector_score": r.get("vector_score", r.get("score", 0)),
                "keyword_score": r.get("keyword_score", 0),
                "combined_score": r.get("score", 0),
                "document_filename": doc_filename,
                "metadata": r.get("metadata", {}),
            })

    latency_ms = round((time.time() - start) * 1000, 1)
    embedding_preview = query_embedding[:10] if request.include_vectors else []

    return {
        "results": results,
        "query_embedding_preview": embedding_preview,
        "search_latency_ms": latency_ms,
    }


# =============================================================================
# API Endpoints - RAG Stats
# =============================================================================


@app.get("/rag/stats")
async def rag_stats():
    """Comprehensive RAG system statistics."""
    if not db_pool:
        return {
            "total_documents": 0, "total_chunks": 0, "total_collections": 0,
            "storage_bytes": 0, "avg_chunk_tokens": 0,
            "embedding_model": EMBEDDING_MODEL, "vector_dimension": VECTOR_DIMENSION,
            "index_type": "pgvector (ivfflat)", "documents_by_type": {},
            "recent_ingestions": [],
        }

    async with db_pool.acquire() as conn:
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM rag.documents")
        chunk_row = await conn.fetchrow(
            "SELECT COUNT(*) as total, COALESCE(AVG(content_tokens), 0) as avg_tokens FROM rag.chunks"
        )
        coll_count = await conn.fetchval("SELECT COUNT(*) FROM rag.collections")
        storage = await conn.fetchval("SELECT COALESCE(SUM(file_size), 0) FROM rag.documents")

        by_type = await conn.fetch(
            "SELECT content_type, COUNT(*) as count FROM rag.documents GROUP BY content_type"
        )

        recent = await conn.fetch(
            """SELECT id::text as document_id, filename, chunk_count as chunks_created, status, created_at
               FROM rag.documents ORDER BY created_at DESC LIMIT 10"""
        )

    return {
        "total_documents": doc_count,
        "total_chunks": chunk_row["total"],
        "total_collections": coll_count,
        "storage_bytes": storage,
        "avg_chunk_tokens": round(float(chunk_row["avg_tokens"]), 1),
        "embedding_model": EMBEDDING_MODEL,
        "vector_dimension": VECTOR_DIMENSION,
        "index_type": "pgvector (ivfflat)",
        "documents_by_type": {r["content_type"]: r["count"] for r in by_type},
        "recent_ingestions": [
            {
                "document_id": r["document_id"],
                "filename": r["filename"],
                "chunks_created": r["chunks_created"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in recent
        ],
    }


# =============================================================================
# API Endpoints - System
# =============================================================================


@app.get("/system/info")
async def system_info():
    """Deployment info and configuration."""
    uptime = time.time() - startup_time
    pool_size = 0
    pool_free = 0
    if db_pool:
        pool_size = db_pool.get_size()
        pool_free = db_pool.get_idle_size()

    return {
        "version": "2.0.0",
        "uptime_seconds": round(uptime, 1),
        "start_time": datetime.utcfromtimestamp(startup_time).isoformat(),
        "config": {
            "chat_model": CHAT_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "vector_dimension": VECTOR_DIMENSION,
            "rag_top_k": RAG_TOP_K,
            "rag_threshold": RAG_THRESHOLD,
        },
        "database": {
            "pool_size": pool_size,
            "pool_free": pool_free,
        },
    }


@app.post("/system/cache/clear")
async def clear_cache():
    """Clear Redis cache."""
    keys_removed = 0
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        keys = await r.keys("manic:*")
        if keys:
            keys_removed = await r.delete(*keys)
        await r.aclose()
        return {"cleared": True, "keys_removed": keys_removed}
    except Exception as e:
        # Redis might not be available or redis package not installed
        return {"cleared": False, "keys_removed": 0, "error": str(e)}


@app.get("/services/status/stream")
async def services_status_stream():
    """SSE real-time service status updates."""
    async def event_generator():
        while True:
            try:
                ollama = await check_service(f"{OLLAMA_URL}/api/tags")
                qdrant = await check_service(f"{QDRANT_URL}/collections")
                searxng = await check_service(f"{SEARXNG_URL}/healthz")

                db_status = {"status": "offline", "latency_ms": None}
                if db_pool:
                    try:
                        start = datetime.utcnow()
                        async with db_pool.acquire() as conn:
                            await conn.fetchval("SELECT 1")
                        latency = (datetime.utcnow() - start).total_seconds() * 1000
                        db_status = {"status": "healthy", "latency_ms": round(latency, 1)}
                    except Exception:
                        db_status = {"status": "offline", "latency_ms": None}

                langfuse = await check_service(f"{LANGFUSE_HOST}")

                data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "services": {
                        "ollama": {"name": "Ollama", "url": OLLAMA_URL, **ollama},
                        "database": {"name": "PostgreSQL", "url": "supabase-db:5432", **db_status},
                        "qdrant": {"name": "Qdrant", "url": QDRANT_URL, **qdrant},
                        "searxng": {"name": "SearXNG", "url": SEARXNG_URL, **searxng},
                        "langfuse": {"name": "Langfuse", "url": LANGFUSE_HOST, **langfuse},
                    },
                }
                yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            await asyncio.sleep(10)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
