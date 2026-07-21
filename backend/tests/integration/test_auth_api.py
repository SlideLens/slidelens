"""httpx integration tests for Auth API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db import get_db, reset_db_state
from app.main import create_app
from app.models import Base
from app.security import create_token


@pytest.fixture
async def auth_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-jwt-32bytes!!")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("SMTP_HOST", "")
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
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()
    reset_db_state()


def _assert_auth_tokens(payload: dict) -> None:
    assert "access_token" in payload
    assert "refresh_token" in payload
    assert payload.get("token_type", "bearer") == "bearer"
    user = payload["user"]
    for key in ("id", "email", "plan", "free_reviews_left", "email_verified"):
        assert key in user
    assert user["plan"] == "free"
    assert user["free_reviews_left"] == 2
    assert user["email_verified"] is True


@pytest.mark.asyncio
async def test_auth_full_cycle(auth_client: AsyncClient) -> None:
    reg = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": "User@Example.com", "password": "password1"},
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    _assert_auth_tokens(body)
    assert body["user"]["email"] == "user@example.com"

    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password1"},
    )
    assert login.status_code == 200
    tokens = login.json()
    _assert_auth_tokens(tokens)

    refresh = await auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 200
    refreshed = refresh.json()
    _assert_auth_tokens(refreshed)

    me = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email_verified"] is True
    assert me.json()["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_register_can_create_review_without_verify(auth_client: AsyncClient) -> None:
    """MVP: no email verification gate on POST /reviews (expects deck file → 422)."""
    reg = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": "raw@example.com", "password": "password1"},
    )
    access = reg.json()["access_token"]
    resp = await auth_client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {access}"},
    )
    # Not 403 for unverified — missing multipart deck → 422
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_refresh_after_access_expiry(auth_client: AsyncClient) -> None:
    reg = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": "exp@example.com", "password": "password1"},
    )
    assert reg.status_code == 201
    settings = get_settings()
    user_id = reg.json()["user"]["id"]

    expired_access = create_token(
        user_id=UUID(user_id),
        token_type="access",
        settings=settings,
        expires_delta=timedelta(seconds=-10),
    )
    refresh_token = reg.json()["refresh_token"]

    me = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_access}"},
    )
    assert me.status_code == 401

    refreshed = await auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    me_ok = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert me_ok.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_register_conflict(auth_client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "password1"}
    assert (await auth_client.post("/api/v1/auth/register", json=payload)).status_code == 201
    again = await auth_client.post("/api/v1/auth/register", json=payload)
    assert again.status_code == 409
