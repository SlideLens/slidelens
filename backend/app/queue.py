"""ARQ Redis pool and the ``get_queue`` dependency (mirrors ``app/db.py``)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.config import get_settings

_pool: ArqRedis | None = None


async def _ensure_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def get_queue() -> AsyncGenerator[ArqRedis, None]:
    """Yield the shared ARQ pool (FastAPI dependency)."""
    yield await _ensure_pool()


async def reset_queue_state() -> None:
    """Close and clear the cached pool (tests)."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
