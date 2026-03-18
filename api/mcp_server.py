"""Manic-AI MCP (Model Context Protocol) server.

Exposes the Manic-AI knowledge base as MCP tools for use with
Claude Desktop and other MCP-compatible clients.
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg
import httpx
from mcp.server import Server
from mcp.types import TextContent, Tool

from api.config import settings
from api.repositories.supabase_documents import SupabaseDocumentRepository
from api.schemas.ingest import IngestRequest
from api.services.embedding import generate_embedding
from api.services.ingestion import ingest_document
from api.services.search import unified_search

logger = logging.getLogger(__name__)

server = Server("manic-ai")

# These are set during initialization (see mcp_main.py)
_db_pool: Optional[asyncpg.Pool] = None
_http_client: Optional[httpx.AsyncClient] = None


def set_db_pool(pool: asyncpg.Pool) -> None:
    """Inject the database connection pool."""
    import api.mcp_server as _mod
    _mod._db_pool = pool


def set_http_client(client: httpx.AsyncClient) -> None:
    """Inject the shared HTTP client."""
    import api.mcp_server as _mod
    _mod._http_client = client


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: List[Tool] = [
    Tool(
        name="search_knowledge_base",
        description="Search the Manic-AI knowledge base using hybrid vector + keyword search",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query text",
                },
                "collection": {
                    "type": "string",
                    "description": "Optional collection ID to scope the search",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="ingest_document",
        description="Ingest a document into the Manic-AI knowledge base",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Document title (used as filename)",
                },
                "content": {
                    "type": "string",
                    "description": "The document content to ingest",
                },
                "collection": {
                    "type": "string",
                    "description": "Optional collection ID to file the document under",
                },
                "content_type": {
                    "type": "string",
                    "description": "MIME type of the content",
                    "default": "text/plain",
                },
            },
            "required": ["title", "content"],
        },
    ),
    Tool(
        name="list_collections",
        description="List all document collections in the knowledge base",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="web_search",
        description="Search the web using SearXNG",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
]


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """Return the list of available MCP tools."""
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Dispatch an MCP tool call to the appropriate handler."""
    handlers = {
        "search_knowledge_base": _handle_search,
        "ingest_document": _handle_ingest,
        "list_collections": _handle_list_collections,
        "web_search": _handle_web_search,
    }

    handler = handlers.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        return await handler(arguments)
    except Exception as exc:
        logger.exception("MCP tool %s failed", name)
        return [TextContent(type="text", text=f"Error: {exc}")]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_search(arguments: Dict[str, Any]) -> List[TextContent]:
    """Search the knowledge base using the existing unified_search service."""
    query = arguments["query"]
    collection = arguments.get("collection")
    top_k = arguments.get("top_k", 5)

    if _http_client is None:
        return [TextContent(type="text", text="Error: HTTP client not initialized")]

    query_embedding = await generate_embedding(query, client=_http_client)

    results = await unified_search(
        query_text=query,
        query_embedding=query_embedding,
        backend="supabase" if _db_pool else "qdrant",
        top_k=top_k,
        threshold=settings.RAG_THRESHOLD,
        use_hybrid=True,
        collection_id=collection,
        user_id=None,
        db=_db_pool,
        client=_http_client,
        rerank=False,
    )

    if not results:
        return [TextContent(type="text", text="No results found.")]

    lines: List[str] = []
    for i, r in enumerate(results, 1):
        score = r.get("score", 0)
        content = r.get("content", "")
        doc_id = r.get("document_id", "unknown")
        lines.append(f"--- Result {i} (score: {score:.3f}, doc: {doc_id}) ---")
        lines.append(content)
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_ingest(arguments: Dict[str, Any]) -> List[TextContent]:
    """Ingest a document using the existing ingestion service."""
    title = arguments["title"]
    content = arguments["content"]
    collection = arguments.get("collection")
    content_type = arguments.get("content_type", "text/plain")

    if _http_client is None:
        return [TextContent(type="text", text="Error: HTTP client not initialized")]

    request = IngestRequest(
        content=content,
        filename=title,
        content_type=content_type,
        collection_id=collection,
        backend="supabase" if _db_pool else "qdrant",
    )

    result = await ingest_document(request, _db_pool, _http_client)

    return [TextContent(
        type="text",
        text=(
            f"Document ingested successfully.\n"
            f"  Document ID: {result.document_id}\n"
            f"  Filename: {result.filename}\n"
            f"  Chunks created: {result.chunks_created}\n"
            f"  Status: {result.status}"
        ),
    )]


async def _handle_list_collections(arguments: Dict[str, Any]) -> List[TextContent]:
    """List collections from the database."""
    if _db_pool is None:
        return [TextContent(type="text", text="Error: Database not connected")]

    repo = SupabaseDocumentRepository(_db_pool)
    collections = await repo.list_collections()

    if not collections:
        return [TextContent(type="text", text="No collections found.")]

    lines: List[str] = []
    for c in collections:
        name = c.get("name", "unnamed")
        cid = c.get("id", "unknown")
        doc_count = c.get("document_count", 0)
        description = c.get("description", "")
        line = f"- {name} (id: {cid}, documents: {doc_count})"
        if description:
            line += f"\n  {description}"
        lines.append(line)

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_web_search(arguments: Dict[str, Any]) -> List[TextContent]:
    """Search the web via SearXNG."""
    query = arguments["query"]
    num_results = arguments.get("num_results", 5)

    if _http_client is None:
        return [TextContent(type="text", text="Error: HTTP client not initialized")]

    response = await _http_client.get(
        f"{settings.SEARXNG_URL}/search",
        params={
            "q": query,
            "format": "json",
            "pageno": 1,
        },
    )
    response.raise_for_status()
    data = response.json()

    results = data.get("results", [])[:num_results]

    if not results:
        return [TextContent(type="text", text="No web results found.")]

    lines: List[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        snippet = r.get("content", "")
        lines.append(f"{i}. {title}")
        lines.append(f"   URL: {url}")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]
