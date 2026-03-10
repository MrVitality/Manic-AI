import asyncpg
from typing import Optional
from fastapi import HTTPException

db_pool: Optional[asyncpg.Pool] = None


async def init_pool(dsn: str):
    global db_pool
    db_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, command_timeout=30)


async def close_pool():
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None


async def get_db() -> asyncpg.Pool:
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    return db_pool


def get_db_optional() -> Optional[asyncpg.Pool]:
    return db_pool
