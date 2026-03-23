#!/usr/bin/env python3
"""
Manic AI - Migration Script: bge-m3 (1024 dimensions)
======================================================

Handles all three migration steps:
  1. Rebuild Supabase database (alter vector columns + rebuild HNSW indexes)
  2. Re-embed all existing documents with bge-m3
  3. Recreate Qdrant collections with optimized HNSW + quantization settings

Usage:
  python scripts/migrate_to_bge_m3.py              # Run all steps
  python scripts/migrate_to_bge_m3.py --step 1     # Database schema only
  python scripts/migrate_to_bge_m3.py --step 2     # Re-embed documents only
  python scripts/migrate_to_bge_m3.py --step 3     # Qdrant collections only
  python scripts/migrate_to_bge_m3.py --dry-run    # Show what would be done

Env vars:
  SUPABASE_DB_URL    Postgres connection string (default: postgresql://postgres:postgres@localhost:5433/postgres)
  OLLAMA_URL         Ollama API URL (default: http://localhost:11434)
  QDRANT_URL         Qdrant REST URL (default: http://localhost:6333)
  QDRANT_API_KEY     Qdrant API key (optional)
  EMBEDDING_MODEL    Model name (default: bge-m3)
  VECTOR_DIMENSION   Target dimensions (default: 1024)
  EMBED_BATCH_SIZE   Chunks per embedding batch (default: 8)
"""

import argparse
import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_URL = os.getenv("SUPABASE_DB_URL", "postgresql://postgres:postgres@localhost:5433/postgres")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "1024"))
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "8"))

# Qdrant collections to recreate (matches setup_qdrant.py)
QDRANT_COLLECTIONS = ["documents", "code", "conversations", "knowledge_base"]


def _log(msg: str, level: str = "INFO"):
    prefix = {"INFO": "[INFO]", "WARN": "[WARN]", "ERR": "[ERR!]", "OK": "[ OK ]", "SKIP": "[SKIP]"}
    print(f"  {prefix.get(level, '[????]')} {msg}")


def _qdrant_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY
    return headers


def _qdrant_request(method: str, path: str, body: dict | None = None, timeout: int = 30) -> dict | None:
    url = f"{QDRANT_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=_qdrant_headers(), method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        _log(f"Qdrant {method} {path} → {e.code}: {body_text[:200]}", "ERR")
        return None
    except URLError as e:
        _log(f"Qdrant unreachable: {e.reason}", "ERR")
        return None


def _ollama_embed(text: str) -> list[float] | None:
    """Generate embedding via Ollama."""
    url = f"{OLLAMA_URL}/api/embeddings"
    payload = json.dumps({"model": EMBEDDING_MODEL, "prompt": text}).encode()
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("embedding")
    except (HTTPError, URLError) as e:
        _log(f"Ollama embed failed: {e}", "ERR")
        return None


# ---------------------------------------------------------------------------
# Step 1: Database Schema Migration
# ---------------------------------------------------------------------------
def step1_database(dry_run: bool = False):
    print()
    print("=" * 60)
    print("Step 1: Database Schema Migration (768 → 1024 dimensions)")
    print("=" * 60)

    try:
        import psycopg2
    except ImportError:
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
            import psycopg2
        except Exception:
            _log("psycopg2 not available. Install with: pip install psycopg2-binary", "ERR")
            return False

    sql_statements = [
        # --- Drop old HNSW indexes (must drop before altering column type) ---
        "DROP INDEX IF EXISTS rag.idx_chunks_embedding_hnsw;",
        "DROP INDEX IF EXISTS public.idx_public_documents_embedding;",
        "DROP INDEX IF EXISTS public.idx_documents_embedding_hnsw;",

        # --- Alter vector columns to 1024 dimensions ---
        "ALTER TABLE rag.chunks ALTER COLUMN embedding TYPE vector(1024);",
        "ALTER TABLE public.documents ALTER COLUMN embedding TYPE vector(1024);",

        # --- Rebuild HNSW indexes with optimized settings ---
        """CREATE INDEX idx_chunks_embedding_hnsw
           ON rag.chunks USING hnsw (embedding vector_cosine_ops)
           WITH (m = 16, ef_construction = 128);""",
        """CREATE INDEX idx_public_documents_embedding
           ON public.documents USING hnsw (embedding vector_cosine_ops)
           WITH (m = 16, ef_construction = 128);""",

        # --- Replace SQL functions with 1024-dim signatures ---
        # match_documents
        """CREATE OR REPLACE FUNCTION public.match_documents(
             query_embedding vector(1024),
             match_count int DEFAULT 5,
             filter jsonb DEFAULT '{}'::jsonb
           ) RETURNS TABLE (id uuid, content text, metadata jsonb, similarity float)
           LANGUAGE plpgsql AS $$
           BEGIN
             RETURN QUERY
             SELECT d.id, d.content, d.metadata,
                    1 - (d.embedding <=> query_embedding) AS similarity
             FROM public.documents d
             WHERE CASE WHEN filter != '{}'::jsonb THEN d.metadata @> filter ELSE TRUE END
             ORDER BY d.embedding <=> query_embedding
             LIMIT match_count;
           END;
           $$;""",

        # search_similar_chunks
        """CREATE OR REPLACE FUNCTION rag.search_similar_chunks(
             query_embedding vector(1024),
             match_count int DEFAULT 5,
             similarity_threshold float DEFAULT 0.7,
             p_collection_id uuid DEFAULT NULL
           ) RETURNS TABLE (
             chunk_id uuid, document_id uuid, content text,
             chunk_index int, metadata jsonb, similarity float
           )
           LANGUAGE plpgsql AS $$
           BEGIN
             PERFORM set_config('hnsw.ef_search', '100', true);
             RETURN QUERY
             SELECT c.id, c.document_id, c.content, c.chunk_index,
                    c.metadata, 1 - (c.embedding <=> query_embedding) AS similarity
             FROM rag.chunks c
             JOIN rag.documents d ON d.id = c.document_id
             LEFT JOIN rag.document_collections dc ON dc.document_id = d.id
             WHERE 1 - (c.embedding <=> query_embedding) >= similarity_threshold
               AND (p_collection_id IS NULL OR dc.collection_id = p_collection_id)
             ORDER BY c.embedding <=> query_embedding
             LIMIT match_count;
           END;
           $$;""",

        # Set ef_search default
        "ALTER DATABASE postgres SET hnsw.ef_search = 100;",
    ]

    if dry_run:
        _log("DRY RUN — would execute the following SQL statements:")
        for i, sql in enumerate(sql_statements, 1):
            print(f"    [{i}] {sql[:120].strip()}{'...' if len(sql) > 120 else ''}")
        return True

    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cur = conn.cursor()

        for i, sql in enumerate(sql_statements, 1):
            try:
                _log(f"Executing statement {i}/{len(sql_statements)}...")
                cur.execute(sql)
                _log(f"Statement {i} OK", "OK")
            except Exception as e:
                _log(f"Statement {i} failed: {e}", "WARN")
                # Continue — some statements may fail if objects don't exist yet

        # Verify
        cur.execute("SELECT column_name, udt_name FROM information_schema.columns WHERE table_schema = 'rag' AND table_name = 'chunks' AND column_name = 'embedding'")
        row = cur.fetchone()
        if row:
            _log(f"rag.chunks.embedding type: {row[1]}", "OK")

        cur.close()
        conn.close()
        _log("Database schema migration complete", "OK")
        return True

    except Exception as e:
        _log(f"Database connection failed: {e}", "ERR")
        _log(f"Connection string: {DB_URL[:30]}...", "INFO")
        return False


# ---------------------------------------------------------------------------
# Step 2: Re-embed All Documents
# ---------------------------------------------------------------------------
def step2_reembed(dry_run: bool = False):
    print()
    print("=" * 60)
    print(f"Step 2: Re-embed Documents with {EMBEDDING_MODEL} ({VECTOR_DIMENSION}d)")
    print("=" * 60)

    # Check Ollama is running and model is available
    _log(f"Checking Ollama at {OLLAMA_URL}...")
    try:
        req = Request(f"{OLLAMA_URL}/api/tags")
        with urlopen(req, timeout=10) as resp:
            models = json.loads(resp.read())
            model_names = [m.get("name", "") for m in models.get("models", [])]
            if not any(EMBEDDING_MODEL in m for m in model_names):
                _log(f"Model '{EMBEDDING_MODEL}' not found in Ollama. Available: {model_names}", "WARN")
                _log(f"Pull it with: ollama pull {EMBEDDING_MODEL}", "INFO")
                if not dry_run:
                    _log("Attempting to pull model...", "INFO")
                    pull_req = Request(
                        f"{OLLAMA_URL}/api/pull",
                        data=json.dumps({"name": EMBEDDING_MODEL}).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    try:
                        with urlopen(pull_req, timeout=600) as pull_resp:
                            for line in pull_resp:
                                status = json.loads(line).get("status", "")
                                if "success" in status.lower():
                                    _log(f"Model {EMBEDDING_MODEL} pulled successfully", "OK")
                                    break
                    except Exception as e:
                        _log(f"Auto-pull failed: {e}. Please run: ollama pull {EMBEDDING_MODEL}", "ERR")
                        return False
            else:
                _log(f"Model '{EMBEDDING_MODEL}' is available", "OK")
    except Exception as e:
        _log(f"Cannot reach Ollama: {e}", "ERR")
        return False

    # Connect to database
    try:
        import psycopg2
    except ImportError:
        _log("psycopg2 not available", "ERR")
        return False

    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
    except Exception as e:
        _log(f"Database connection failed: {e}", "ERR")
        return False

    # Count chunks to re-embed
    cur.execute("SELECT COUNT(*) FROM rag.chunks")
    total_chunks = cur.fetchone()[0]
    _log(f"Total chunks to re-embed: {total_chunks}")

    # Also count public.documents
    cur.execute("SELECT COUNT(*) FROM public.documents WHERE content IS NOT NULL AND content != ''")
    total_docs = cur.fetchone()[0]
    _log(f"Total public.documents to re-embed: {total_docs}")

    if dry_run:
        _log(f"DRY RUN — would re-embed {total_chunks} chunks + {total_docs} documents")
        cur.close()
        conn.close()
        return True

    if total_chunks == 0 and total_docs == 0:
        _log("No documents to re-embed", "SKIP")
        cur.close()
        conn.close()
        return True

    # Re-embed rag.chunks in batches
    _log(f"Re-embedding rag.chunks (batch size: {EMBED_BATCH_SIZE})...")
    cur.execute("SELECT id, content FROM rag.chunks ORDER BY id")

    processed = 0
    failed = 0
    start_time = time.time()

    while True:
        rows = cur.fetchmany(EMBED_BATCH_SIZE)
        if not rows:
            break

        for chunk_id, content in rows:
            if not content or not content.strip():
                processed += 1
                continue

            embedding = _ollama_embed(content)
            if embedding and len(embedding) == VECTOR_DIMENSION:
                update_cur = conn.cursor()
                update_cur.execute(
                    "UPDATE rag.chunks SET embedding = %s::vector WHERE id = %s",
                    (str(embedding), chunk_id)
                )
                conn.commit()
                update_cur.close()
                processed += 1
            else:
                failed += 1
                processed += 1
                if embedding:
                    _log(f"Dimension mismatch for chunk {chunk_id}: got {len(embedding)}, expected {VECTOR_DIMENSION}", "WARN")

            if processed % 50 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total_chunks - processed) / rate if rate > 0 else 0
                _log(f"Progress: {processed}/{total_chunks} chunks ({rate:.1f}/s, ETA: {eta:.0f}s)")

    elapsed = time.time() - start_time
    _log(f"rag.chunks complete: {processed} processed, {failed} failed in {elapsed:.1f}s", "OK")

    # Re-embed public.documents
    if total_docs > 0:
        _log(f"Re-embedding public.documents...")
        cur.execute("SELECT id, content FROM public.documents WHERE content IS NOT NULL AND content != '' ORDER BY id")

        doc_processed = 0
        doc_failed = 0

        while True:
            rows = cur.fetchmany(EMBED_BATCH_SIZE)
            if not rows:
                break

            for doc_id, content in rows:
                embedding = _ollama_embed(content[:8000])  # Truncate very long docs
                if embedding and len(embedding) == VECTOR_DIMENSION:
                    update_cur = conn.cursor()
                    update_cur.execute(
                        "UPDATE public.documents SET embedding = %s::vector WHERE id = %s",
                        (str(embedding), doc_id)
                    )
                    conn.commit()
                    update_cur.close()
                    doc_processed += 1
                else:
                    doc_failed += 1
                    doc_processed += 1

                if doc_processed % 50 == 0:
                    _log(f"Progress: {doc_processed}/{total_docs} documents")

        _log(f"public.documents complete: {doc_processed} processed, {doc_failed} failed", "OK")

    cur.close()
    conn.close()
    _log("Re-embedding complete", "OK")
    return True


# ---------------------------------------------------------------------------
# Step 3: Recreate Qdrant Collections
# ---------------------------------------------------------------------------
def step3_qdrant(dry_run: bool = False):
    print()
    print("=" * 60)
    print("Step 3: Recreate Qdrant Collections (optimized settings)")
    print("=" * 60)

    # Check health
    result = _qdrant_request("GET", "/health")
    if not result:
        _log("Qdrant is not reachable", "ERR")
        return False
    _log("Qdrant is healthy", "OK")

    for name in QDRANT_COLLECTIONS:
        _log(f"--- Collection: {name} ---")

        if dry_run:
            _log(f"DRY RUN — would delete and recreate '{name}' with {VECTOR_DIMENSION}d, HNSW(m=16, ef=200), int8 quantization")
            continue

        # Delete existing collection
        _log(f"Deleting '{name}'...")
        _qdrant_request("DELETE", f"/collections/{name}")

        # Wait briefly for deletion to complete
        time.sleep(0.5)

        # Recreate with optimized settings
        body = {
            "vectors": {
                "size": VECTOR_DIMENSION,
                "distance": "Cosine"
            },
            "hnsw_config": {
                "m": 16,
                "ef_construct": 200
            },
            "quantization_config": {
                "scalar": {
                    "type": "int8",
                    "quantile": 0.99,
                    "always_ram": True
                }
            },
            "optimizers_config": {
                "default_segment_number": 2,
                "indexing_threshold": 10000
            }
        }

        result = _qdrant_request("PUT", f"/collections/{name}", body)
        if result:
            _log(f"Created '{name}' ({VECTOR_DIMENSION}d, HNSW m=16 ef=200, int8 quant)", "OK")
        else:
            _log(f"Failed to create '{name}'", "ERR")
            continue

        # Create payload indexes
        for field, schema in [("user_id", "keyword"), ("collection_id", "keyword"),
                               ("document_id", "keyword"), ("created_at", "datetime")]:
            idx_body = {"field_name": field, "field_schema": schema}
            _qdrant_request("PUT", f"/collections/{name}/index", idx_body)
            _log(f"  Index: {field} ({schema})", "OK")

    # Show final state
    print()
    result = _qdrant_request("GET", "/collections")
    if result:
        collections = result.get("result", {}).get("collections", [])
        _log(f"Final collections: {[c['name'] for c in collections]}", "OK")

    _log("Qdrant migration complete", "OK")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Migrate Manic AI to bge-m3 (1024 dimensions)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--step", type=int, choices=[1, 2, 3],
                        help="Run only a specific step (1=DB, 2=re-embed, 3=Qdrant)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  Manic AI — bge-m3 Migration (768 → 1024 dimensions)")
    print("=" * 60)
    print()
    print(f"  Database:    {DB_URL[:50]}...")
    print(f"  Ollama:      {OLLAMA_URL}")
    print(f"  Qdrant:      {QDRANT_URL}")
    print(f"  Model:       {EMBEDDING_MODEL} ({VECTOR_DIMENSION}d)")
    print(f"  Batch size:  {EMBED_BATCH_SIZE}")
    if args.dry_run:
        print(f"  Mode:        DRY RUN")
    print()

    steps = [args.step] if args.step else [1, 2, 3]
    results = {}

    if 1 in steps:
        results[1] = step1_database(args.dry_run)
    if 2 in steps:
        results[2] = step2_reembed(args.dry_run)
    if 3 in steps:
        results[3] = step3_qdrant(args.dry_run)

    # Summary
    print()
    print("=" * 60)
    print("  Migration Summary")
    print("=" * 60)
    for step_num, success in results.items():
        labels = {1: "Database schema", 2: "Re-embed documents", 3: "Qdrant collections"}
        status = "PASS" if success else "FAIL"
        icon = "[OK]" if success else "[!!]"
        print(f"  {icon} Step {step_num}: {labels[step_num]} — {status}")
    print("=" * 60)

    if all(results.values()):
        print()
        print("  Migration complete! Your RAG pipeline is now using")
        print(f"  {EMBEDDING_MODEL} ({VECTOR_DIMENSION} dimensions) with optimized indexes.")
        print()
        if not args.dry_run:
            print("  Next: Restart the API service to pick up the new settings.")
            print("        docker compose restart api")
        print()
        return 0
    else:
        print()
        print("  Some steps failed. Check the output above for details.")
        print("  You can re-run individual steps with --step N")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
