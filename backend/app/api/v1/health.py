"""Health check endpoint — reports DB and Redis connectivity (#25 И1)."""

from __future__ import annotations

from typing import Annotated

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db

router = APIRouter(tags=["health"])

_PING_TIMEOUT_SECONDS = 1.0


@router.get("/health")
async def health(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - health check reports failure, never raises
        database = "error"

    redis_client = redis_asyncio.from_url(
        settings.redis_url,
        socket_connect_timeout=_PING_TIMEOUT_SECONDS,
        socket_timeout=_PING_TIMEOUT_SECONDS,
    )
    try:
        await redis_client.ping()
        redis_status = "ok"
    except Exception:  # noqa: BLE001 - health check reports failure, never raises
        redis_status = "error"
    finally:
        await redis_client.aclose()

    overall = "ok" if database == "ok" and redis_status == "ok" else "degraded"
    return {"status": overall, "database": database, "redis": redis_status}
