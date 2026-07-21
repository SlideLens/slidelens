"""httpx integration tests for the Files API (owner bearer / signed sig / expiry)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings
from app.db import get_db, reset_db_state
from app.main import create_app
from app.models import Base, FileAssetKind, Review
from app.security import create_file_token
from app.services.file_assets import save_file_asset
from app.services.storage import LocalStorage


@pytest.fixture
async def files_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession], Settings]]:
    db_path = tmp_path / "files.db"
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

    settings = get_settings()
    app = create_app(settings)
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory, settings

    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()
    reset_db_state()


async def _register(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "password1"})
    assert reg.status_code == 201, reg.text
    access: str = reg.json()["access_token"]
    return access


async def _seed_review_with_asset(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    user_id,
    kind: FileAssetKind = FileAssetKind.REPORT_PDF,
    data: bytes = b"%PDF-content",
    expires_at: datetime | None = None,
):
    storage = LocalStorage(Path(settings.storage_root))
    async with factory() as session:
        review = Review(
            user_id=user_id,
            status="done",
            deck_filename="deck.pptx",
            has_audio=False,
            has_data=False,
        )
        session.add(review)
        await session.flush()
        asset = await save_file_asset(
            storage,
            session,
            review_id=review.id,
            kind=kind,
            filename="report.pdf",
            data=data,
            expires_at=expires_at or (datetime.now(UTC) + timedelta(days=7)),
        )
        await session.commit()
        return asset.id


async def _user_id(client: AsyncClient, access: str):
    from uuid import UUID

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    return UUID(me.json()["id"])


@pytest.mark.asyncio
async def test_owner_downloads_via_bearer(
    files_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    client, factory, settings = files_client
    access = await _register(client, "owner@example.com")
    user_id = await _user_id(client, access)
    asset_id = await _seed_review_with_asset(factory, settings, user_id=user_id, data=b"hello-pdf")

    resp = await client.get(
        f"/api/v1/files/{asset_id}", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 200
    assert resp.content == b"hello-pdf"


@pytest.mark.asyncio
async def test_non_owner_bearer_gets_404(
    files_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    client, factory, settings = files_client
    owner_access = await _register(client, "owner2@example.com")
    owner_id = await _user_id(client, owner_access)
    other_access = await _register(client, "other@example.com")
    asset_id = await _seed_review_with_asset(factory, settings, user_id=owner_id)

    resp = await client.get(
        f"/api/v1/files/{asset_id}", headers={"Authorization": f"Bearer {other_access}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_no_auth_no_sig_gets_404(
    files_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    client, factory, settings = files_client
    access = await _register(client, "anon@example.com")
    user_id = await _user_id(client, access)
    asset_id = await _seed_review_with_asset(factory, settings, user_id=user_id)

    resp = await client.get(f"/api/v1/files/{asset_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_valid_sig_serves_without_bearer(
    files_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    client, factory, settings = files_client
    access = await _register(client, "sig@example.com")
    user_id = await _user_id(client, access)
    asset_id = await _seed_review_with_asset(
        factory, settings, user_id=user_id, kind=FileAssetKind.ANNOTATED_PNG, data=b"png-bytes"
    )

    sig = create_file_token(asset_id, settings)
    resp = await client.get(f"/api/v1/files/{asset_id}?sig={sig}")
    assert resp.status_code == 200
    assert resp.content == b"png-bytes"


@pytest.mark.asyncio
async def test_expired_sig_returns_401(
    files_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    client, factory, settings = files_client
    access = await _register(client, "expsig@example.com")
    user_id = await _user_id(client, access)
    asset_id = await _seed_review_with_asset(factory, settings, user_id=user_id)

    from app.security import create_token

    expired_sig = create_token(
        user_id=asset_id, token_type="file", settings=settings, expires_delta=timedelta(seconds=-1)
    )
    resp = await client.get(f"/api/v1/files/{asset_id}?sig={expired_sig}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sig_for_different_asset_returns_401(
    files_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    client, factory, settings = files_client
    access = await _register(client, "wrongsig@example.com")
    user_id = await _user_id(client, access)
    asset_id = await _seed_review_with_asset(factory, settings, user_id=user_id)

    other_sig = create_file_token(uuid4(), settings)
    resp = await client.get(f"/api/v1/files/{asset_id}?sig={other_sig}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_asset_returns_404_even_for_owner(
    files_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], Settings],
) -> None:
    client, factory, settings = files_client
    access = await _register(client, "expiredasset@example.com")
    user_id = await _user_id(client, access)
    asset_id = await _seed_review_with_asset(
        factory,
        settings,
        user_id=user_id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    resp = await client.get(
        f"/api/v1/files/{asset_id}", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 404
