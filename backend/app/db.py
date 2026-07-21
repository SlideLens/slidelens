"""Database engine, session factory, and ``get_db`` dependency helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_settings = None
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_engine() -> async_sessionmaker[AsyncSession]:
    global _settings, _engine, _session_factory
    if _session_factory is None:
        _settings = get_settings()
        _engine = create_async_engine(
            _settings.database_url.get_secret_value(),
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` and close it after the request."""
    factory = _ensure_engine()
    async with factory() as session:
        yield session


def reset_db_state() -> None:
    """Clear cached engine (tests)."""
    global _settings, _engine, _session_factory
    _settings = None
    _engine = None
    _session_factory = None
