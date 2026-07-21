"""Unit tests for worker.tasks.process_review.

The heavy/networked pipeline pieces (ingest, aggregate, fix, PDF render) are
monkeypatched module-level names in ``worker.tasks`` — the same seam used
elsewhere in ``core`` (injectable ``run_subprocess``, injectable ``render_pdf``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import worker.tasks as worker_tasks
from app.config import Settings, get_settings
from app.models import Base, FileAsset, FileAssetKind, FindingRow, Review, User
from app.services.file_assets import save_file_asset
from app.services.storage import LocalStorage
from core.ingest_errors import CorruptedFileError
from core.schemas import BBox, Category, Finding, Severity


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
                auto_fixable=True,
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
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()
    return get_settings()


async def _seed_queued_review(
    factory: async_sessionmaker[AsyncSession],
    storage: LocalStorage,
    *,
    deck_filename: str = "deck.pptx",
) -> tuple[Any, Any]:
    async with factory() as session:
        user = User(
            email=f"{uuid4()}@example.com",
            password_hash="x",
            plan="free",
            free_reviews_left=1,
            email_verified=True,
        )
        session.add(user)
        await session.flush()

        review = Review(
            user_id=user.id,
            status="queued",
            deck_filename=deck_filename,
            has_audio=False,
            has_data=False,
            # create_review всегда проставляет кошелёк списания — без него
            # возврат при провале не знает, куда вернуть Разбор.
            credit_source="free",
        )
        session.add(review)
        await session.flush()

        await save_file_asset(
            storage,
            session,
            review_id=review.id,
            kind=FileAssetKind.DECK_ORIGINAL,
            filename=deck_filename,
            data=b"fake-deck-bytes",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        await session.commit()
        return user.id, review.id


@pytest.fixture
async def worker_env(tmp_path: Path, settings: Settings):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}", poolclass=NullPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "store")
    try:
        yield factory, storage, settings
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_process_review_success_persists_findings_and_assets(
    worker_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, storage, settings = worker_env
    user_id, review_id = await _seed_queued_review(factory, storage)

    monkeypatch.setattr(worker_tasks, "DeckIngestor", FakeIngestor)
    monkeypatch.setattr(worker_tasks, "default_steps", lambda llm: [])
    monkeypatch.setattr(worker_tasks, "Aggregator", FakeAggregator)
    monkeypatch.setattr(worker_tasks, "PdfExporter", FakePdfExporter)

    worker_ctx = {"settings": settings, "session_factory": factory, "storage": storage}
    await worker_tasks.process_review(worker_ctx, str(review_id))

    async with factory() as check:
        review = await check.get(Review, review_id)
        assert review is not None
        assert review.status == "done"
        assert review.score is not None
        assert review.n_slides == 1
        assert review.finished_at is not None

        findings = (
            await check.execute(select(FindingRow).where(FindingRow.review_id == review_id))
        ).scalars().all()
        assert len(findings) == 1
        assert findings[0].auto_fixable is True
        assert findings[0].auto_fixed is False  # point-apply only; not batch-fixed in worker
        assert findings[0].screenshot_asset_id is not None

        assets = (
            await check.execute(select(FileAsset).where(FileAsset.review_id == review_id))
        ).scalars().all()
        kinds = {a.kind for a in assets}
        assert {
            "deck_original",
            "slide_png",
            "annotated_png",
            "fixed_pptx",
            "report_pdf",
        } <= kinds

        user = await check.get(User, user_id)
        assert user is not None
        assert user.free_reviews_left == 1  # credit stays spent on success


@pytest.mark.asyncio
async def test_process_review_saves_raw_slides_so_get_slides_needs_no_backfill(
    worker_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, storage, settings = worker_env
    _user_id, review_id = await _seed_queued_review(factory, storage)

    monkeypatch.setattr(worker_tasks, "DeckIngestor", FakeIngestor)
    monkeypatch.setattr(worker_tasks, "default_steps", lambda llm: [])
    monkeypatch.setattr(worker_tasks, "Aggregator", FakeAggregator)
    monkeypatch.setattr(worker_tasks, "PdfExporter", FakePdfExporter)

    worker_ctx = {"settings": settings, "session_factory": factory, "storage": storage}
    await worker_tasks.process_review(worker_ctx, str(review_id))

    async with factory() as check:
        slide_assets = (
            await check.execute(
                select(FileAsset).where(
                    FileAsset.review_id == review_id,
                    FileAsset.kind == FileAssetKind.SLIDE_PNG.value,
                )
            )
        ).scalars().all()

    assert len(slide_assets) == 1
    # Имя должно разбираться ``_SLIDE_FILENAME_RE`` в review_service, иначе
    # ``get_slides`` молча вернёт пустой список и уйдёт в перерендер Деки.
    assert slide_assets[0].storage_path.endswith("slide_001.png")


@pytest.mark.asyncio
async def test_process_review_ingest_failure_marks_failed_and_refunds(
    worker_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, storage, settings = worker_env
    user_id, review_id = await _seed_queued_review(factory, storage)

    async with factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.free_reviews_left = 0  # simulate the credit already having been reserved
        await session.commit()

    monkeypatch.setattr(worker_tasks, "DeckIngestor", FailingIngestor)

    worker_ctx = {"settings": settings, "session_factory": factory, "storage": storage}
    await worker_tasks.process_review(worker_ctx, str(review_id))

    async with factory() as check:
        review = await check.get(Review, review_id)
        assert review is not None
        assert review.status == "failed"
        assert review.fail_reason == "Файл повреждён или не открывается"

        user = await check.get(User, user_id)
        assert user is not None
        assert user.free_reviews_left == 1  # refunded
