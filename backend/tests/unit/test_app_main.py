"""Tests for FastAPI application wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import get_db
from app.main import create_app


@pytest.mark.asyncio
async def test_health_reports_database_ok_when_reachable(tmp_path: Path) -> None:
    db_path = tmp_path / "health.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        body = (await client.get("/health")).json()
    assert body["database"] == "ok"
    # REDIS_URL still points nowhere real in tests — overall stays degraded.
    assert body["redis"] == "error"
    assert body["status"] == "degraded"

    await engine.dispose()


def test_health_and_metrics() -> None:
    client = TestClient(create_app())
    # No real Postgres/Redis in the unit-test environment — /health must still
    # respond (never raise) and honestly report both as unreachable.
    body = client.get("/health").json()
    assert body == {"status": "degraded", "database": "error", "redis": "error"}
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "review_cost_usd" in metrics.text


def test_request_id_header_on_api_paths() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    # health is skipped for logging middleware attachment of header on skip path
    # use a non-skip path that 404s
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert "X-Request-ID" in response.headers


def test_docs_disabled_in_production(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "")
    from app.config import get_settings

    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    get_settings.cache_clear()


def test_spa_served_when_static_dir_present(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    dist = tmp_path / "static"
    dist.mkdir()
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")

    monkeypatch.setenv("STATIC_DIR", str(dist))
    from app.config import get_settings

    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/").text == "<html>spa</html>"
    assert client.get("/cabinet").text == "<html>spa</html>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    # API routes still win over the SPA catch-all
    assert client.get("/health").status_code == 200
    get_settings.cache_clear()


def test_unexpected_exception_returns_500() -> None:
    application = create_app()

    @application.get("/api/v1/_boom", include_in_schema=False)
    async def boom() -> None:
        raise RuntimeError("boom")

    client = TestClient(application, raise_server_exceptions=False)
    response = client.get("/api/v1/_boom")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
