"""MCP server entry point for Manic-AI.

Runs the MCP server over stdio transport, connecting to the same
database and services as the main FastAPI application.

Usage:
    python -m api.mcp_main
"""

import asyncio
import logging

from mcp.server.stdio import stdio_server

from api.config import settings
from api.mcp_server import server, set_db_pool, set_http_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialize resources and run the MCP server via stdio."""
    import asyncpg
    import httpx

    # Initialize database connection pool
    db_pool = None
    if settings.SUPABASE_DB_URL:
        try:
            db_pool = await asyncpg.create_pool(
                settings.SUPABASE_DB_URL,
                min_size=1,
                max_size=5,
                command_timeout=30,
            )
            set_db_pool(db_pool)
            logger.info("Database pool initialized")
        except Exception as exc:
            logger.warning("Failed to connect to database: %s", exc)

    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=60.0)
    set_http_client(http_client)
    logger.info("HTTP client initialized")

    # Initialize Redis for embedding cache (optional)
    try:
        from api.services.embedding import init_redis
        await init_redis()
        logger.info("Redis embedding cache initialized")
    except Exception as exc:
        logger.warning("Redis unavailable, embedding cache disabled: %s", exc)

    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Manic-AI MCP server starting on stdio")
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # Cleanup
        await http_client.aclose()
        if db_pool:
            await db_pool.close()
        logger.info("Manic-AI MCP server shut down")


if __name__ == "__main__":
    asyncio.run(main())
