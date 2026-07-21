"""httpx integration tests for the Reviews API (upload -> poll -> report)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import worker.tasks as worker_tasks
from app.config import get_settings
from app.db import get_db, reset_db_state
from app.main import create_app
from app.models import Base, User
from app.queue import get_queue, reset_queue_state
from app.services.storage import LocalStorage
from core.ingest_errors import CorruptedFileError
from core.schemas import BBox, Category, Finding, Severity


class FakeQueue:
    """Records enqueue_job calls instead of talking to Redis (ADR 0003: 202 must not block)."""

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, name: str, *args: Any) -> None:
        self.enqueued.append((name, args))


class FakeIngestor:
    async def ingest(self, deck: Path, workdir: Path, ctx: Any) -> list[Path]:
        png_path = workdir / "slide_001.png"
        Image.new("RGB", (20, 20), color="white").save(png_path)
        ctx.slide_pngs[1] = png_path
        return [png_path]


class FailingIngestor:
    async def ingest(self, deck: Path, workdir: Path, ctx: Any) -> list[Path]:
        raise CorruptedFileError("bad deck")


class FakeAggregator:
    def __init__(self, llm: Any) -> None:
        del llm

    async def run(self, findings: list[Finding]) -> list[Finding]:
        del findings
        return [
            Finding(
                slide_num=1,
                category=Category.TYPOGRAPHY,
                severity=Severity.MINOR,
                title="Мелкий шрифт",
                description="Текст меньше 14pt",
                fix_suggestion="Увеличьте кегль",
                bbox=BBox(x=0.1, y=0.1, w=0.2, h=0.2),
                auto_fixable=False,
                source="fake",
            )
        ]


class FakePdfExporter:
    def export(
        self, report: Any, *, annotations: dict[Any, Path] | None = None
    ) -> tuple[str, bytes]:
        del report, annotations
        return "<html></html>", b"%PDF-fake"


@pytest.fixture
async def reviews_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession], FakeQueue]]:
    db_path = tmp_path / "reviews.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-jwt-32bytes!!")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    reset_db_state()
    await reset_queue_state()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    fake_queue = FakeQueue()

    async def override_get_queue() -> AsyncIterator[FakeQueue]:
        yield fake_queue

    app = create_app(get_settings())
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_queue] = override_get_queue

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory, fake_queue

    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()
    reset_db_state()


async def _register(client: AsyncClient, email: str) -> str:
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "password1"})
    assert reg.status_code == 201, reg.text
    access: str = reg.json()["access_token"]
    return access


@pytest.mark.asyncio
async def test_upload_poll_report_full_cycle(
    reviews_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], FakeQueue],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory, queue = reviews_client
    access = await _register(client, "reviewer@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    created = await client.post(
        "/api/v1/reviews",
        headers=headers,
        files={"deck": ("deck.pptx", b"fake-deck-bytes", "application/octet-stream")},
    )
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["status"] == "queued"
    assert body["deck_filename"] == "deck.pptx"
    review_id = body["id"]

    # 202 must not block on the pipeline: nothing ran yet, only enqueued.
    assert queue.enqueued == [("process_review", (review_id,))]
    still_queued = await client.get(f"/api/v1/reviews/{review_id}", headers=headers)
    assert still_queued.json()["status"] == "queued"

    # Simulate the worker consuming the job (heavy pipeline steps monkeypatched, see
    # tests/unit/test_worker_process_review.py for the same seam used in isolation).
    monkeypatch.setattr(worker_tasks, "DeckIngestor", FakeIngestor)
    monkeypatch.setattr(worker_tasks, "default_steps", lambda llm: [])
    monkeypatch.setattr(worker_tasks, "Aggregator", FakeAggregator)
    monkeypatch.setattr(worker_tasks, "PdfExporter", FakePdfExporter)
    settings = get_settings()
    storage = LocalStorage(Path(settings.storage_root))
    worker_ctx = {"settings": settings, "session_factory": factory, "storage": storage}
    await worker_tasks.process_review(worker_ctx, review_id)

    polled = await client.get(f"/api/v1/reviews/{review_id}", headers=headers)
    assert polled.status_code == 200
    assert polled.json()["status"] == "done"
    assert polled.json()["score"] is not None

    report = await client.get(f"/api/v1/reviews/{review_id}/report", headers=headers)
    assert report.status_code == 200, report.text
    report_body = report.json()
    for key in ("review_id", "score", "n_slides", "findings", "auto_fixed_count"):
        assert key in report_body
    assert report_body["review_id"] == review_id
    assert len(report_body["findings"]) == 1
    assert report_body["auto_fixed_count"] == 0
    finding = report_body["findings"][0]
    assert finding["auto_fixed"] is False
    assert finding["user_like"] is False
    assert finding["screenshot_asset_id"] is not None
    assert report_body["pdf_asset_id"] is not None
    assert report_body["fixed_pptx_asset_id"] is not None

    # screenshot_url is a ready-to-use signed link — no separate mint call needed (design.md #5).
    screenshot_url = finding["screenshot_url"]
    assert screenshot_url is not None
    assert screenshot_url.startswith(f"/api/v1/files/{finding['screenshot_asset_id']}?sig=")
    screenshot = await client.get(screenshot_url)  # no Authorization header, like an <img> tag
    assert screenshot.status_code == 200


@pytest.mark.asyncio
async def test_report_not_ready_returns_409(
    reviews_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], FakeQueue],
) -> None:
    client, _factory, _queue = reviews_client
    access = await _register(client, "pending@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    created = await client.post(
        "/api/v1/reviews",
        headers=headers,
        files={"deck": ("deck.pptx", b"fake-deck-bytes", "application/octet-stream")},
    )
    review_id = created.json()["id"]

    report = await client.get(f"/api/v1/reviews/{review_id}/report", headers=headers)
    assert report.status_code == 409


@pytest.mark.asyncio
async def test_corrupted_deck_fails_and_refunds_credit(
    reviews_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], FakeQueue],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory, _queue = reviews_client
    access = await _register(client, "broken@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    created = await client.post(
        "/api/v1/reviews",
        headers=headers,
        files={"deck": ("deck.pptx", b"fake-deck-bytes", "application/octet-stream")},
    )
    review_id = created.json()["id"]

    me_before = await client.get("/api/v1/auth/me", headers=headers)
    assert me_before.json()["free_reviews_left"] == 1

    monkeypatch.setattr(worker_tasks, "DeckIngestor", FailingIngestor)
    settings = get_settings()
    storage = LocalStorage(Path(settings.storage_root))
    worker_ctx = {"settings": settings, "session_factory": factory, "storage": storage}
    await worker_tasks.process_review(worker_ctx, review_id)

    failed = await client.get(f"/api/v1/reviews/{review_id}", headers=headers)
    assert failed.json()["status"] == "failed"
    assert failed.json()["fail_reason"]

    me_after = await client.get("/api/v1/auth/me", headers=headers)
    assert me_after.json()["free_reviews_left"] == 2  # refunded


@pytest.mark.asyncio
async def test_exhausted_limit_returns_402(
    reviews_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], FakeQueue],
) -> None:
    client, factory, queue = reviews_client
    access = await _register(client, "exhausted@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    me = await client.get("/api/v1/auth/me", headers=headers)
    user_id = UUID(me.json()["id"])
    async with factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.free_reviews_left = 0
        await session.commit()

    resp = await client.post(
        "/api/v1/reviews",
        headers=headers,
        files={"deck": ("deck.pptx", b"fake-deck-bytes", "application/octet-stream")},
    )
    assert resp.status_code == 402
    assert queue.enqueued == []


@pytest.mark.asyncio
async def test_oversized_deck_returns_413(
    reviews_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], FakeQueue],
) -> None:
    client, _factory, _queue = reviews_client
    access = await _register(client, "big@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    big = b"x" * (50 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/reviews",
        headers=headers,
        files={"deck": ("deck.pptx", big, "application/octet-stream")},
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_wrong_format_deck_returns_422(
    reviews_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], FakeQueue],
) -> None:
    client, _factory, _queue = reviews_client
    access = await _register(client, "wrongfmt@example.com")
    headers = {"Authorization": f"Bearer {access}"}

    resp = await client.post(
        "/api/v1/reviews",
        headers=headers,
        files={"deck": ("deck.key", b"content", "application/octet-stream")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_reviews_scoped_to_owner(
    reviews_client: tuple[AsyncClient, async_sessionmaker[AsyncSession], FakeQueue],
) -> None:
    client, _factory, _queue = reviews_client
    access_a = await _register(client, "a@example.com")
    access_b = await _register(client, "b@example.com")

    await client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {access_a}"},
        files={"deck": ("deck.pptx", b"fake-deck-bytes", "application/octet-stream")},
    )

    list_a = await client.get("/api/v1/reviews", headers={"Authorization": f"Bearer {access_a}"})
    list_b = await client.get("/api/v1/reviews", headers={"Authorization": f"Bearer {access_b}"})
    assert len(list_a.json()) == 1
    assert list_b.json() == []
