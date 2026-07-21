"""httpx integration tests for POST /events."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db import get_db, reset_db_state
from app.main import create_app
from app.models import Base, Event


@pytest.fixture
async def events_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    db_path = tmp_path / "events.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-jwt-32bytes!!")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    reset_db_state()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app(get_settings())
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory

    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()
    reset_db_state()


async def _register(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "password1"})
    assert reg.status_code == 201, reg.text
    access: str = reg.json()["access_token"]
    return access


async def _user_id(client: AsyncClient, access: str) -> UUID:
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    return UUID(me.json()["id"])


@pytest.mark.asyncio
async def test_batch_of_events_is_recorded(
    events_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, factory = events_client
    access = await _register(client, "events@example.com")
    user_id = await _user_id(client, access)

    resp = await client.post(
        "/api/v1/events",
        headers={"Authorization": f"Bearer {access}"},
        json=[
            {"name": "report_opened", "properties": {"review_id": "abc"}},
            {"name": "pdf_downloaded"},
        ],
    )
    assert resp.status_code == 204

    async with factory() as check:
        rows = (
            await check.execute(select(Event).where(Event.user_id == user_id))
        ).scalars().all()
        names = {r.name for r in rows}
        # registration itself already tracks a "signup" event; just check ours landed too.
        assert {"report_opened", "pdf_downloaded"} <= names


@pytest.mark.asyncio
async def test_empty_batch_is_noop(
    events_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, factory = events_client
    access = await _register(client, "emptyevents@example.com")

    async with factory() as check:
        before = len((await check.execute(select(Event))).scalars().all())

    resp = await client.post(
        "/api/v1/events", headers={"Authorization": f"Bearer {access}"}, json=[]
    )
    assert resp.status_code == 204

    async with factory() as check:
        after = len((await check.execute(select(Event))).scalars().all())
        assert after == before


@pytest.mark.asyncio
async def test_requires_auth(
    events_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _factory = events_client
    resp = await client.post("/api/v1/events", json=[{"name": "x"}])
    assert resp.status_code == 401
