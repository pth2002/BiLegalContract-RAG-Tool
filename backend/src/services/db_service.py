"""Database service (asyncpg pool).

Kept minimal: provides a shared pool and init hook for pgvector extension/table setup.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING
 
from ..config import get_database_url

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import asyncpg

_pool: Optional[Any] = None


async def get_db_pool():
    global _pool
    if _pool is None:
        import asyncpg

        dsn = get_database_url()
        logger.info("[DB] Creating asyncpg pool")
        _pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        logger.info("[DB] Closing asyncpg pool")
        await _pool.close()
        _pool = None

