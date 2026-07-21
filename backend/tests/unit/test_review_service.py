"""Unit tests for app.services.review_service."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.models import Base, FileAsset, FindingRow, Rehearsal, Review, User, UserPlan
from app.services import review_service
from app.services.events import EventTracker
from app.services.exceptions import (
    LimitExceededError,
    ReviewNotFoundError,
    ReviewTooLargeError,
    ReviewValidationError,
)
from app.services.storage import LocalStorage


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, name: str, *args: Any) -> None:
        self.enqueued.append((name, args))


@pytest.fixture
async def db_session(tmp_path: Path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'reviews.db'}",
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    from app.config import get_settings

    get_settings.cache_clear()
    return get_settings()


async def _seed_user(session: AsyncSession, *, free_left: int = 2) -> User:
    user = User(
        email=f"{uuid4()}@example.com",
        password_hash="x",
        plan=UserPlan.FREE.value,
        free_reviews_left=free_left,
        email_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


def _upload(name: str, data: bytes = b"content") -> UploadFile:
    return UploadFile(io.BytesIO(data), filename=name)


@pytest.mark.asyncio
async def test_create_review_reserves_and_enqueues(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    user = await _seed_user(db_session, free_left=2)
    storage = LocalStorage(tmp_path / "store")
    queue = FakeQueue()

    review = await review_service.create_review(
        db_session,
        user=user,
        deck=_upload("deck.pptx"),
        audio=_upload("pitch.mp3"),
        data=_upload("data.xlsx"),
        storage=storage,
        queue=queue,  # type: ignore[arg-type]
        settings=settings,
        event_tracker=EventTracker(),
    )
    await db_session.commit()

    assert review.status == "queued"
    assert review.has_audio is True
    assert review.has_data is True
    assert review.deck_filename == "deck.pptx"
    assert queue.enqueued == [("process_review", (str(review.id),))]

    await db_session.refresh(user)
    assert user.free_reviews_left == 1

    assets = (
        (await db_session.execute(select(FileAsset).where(FileAsset.review_id == review.id)))
        .scalars()
        .all()
    )
    assert {a.kind for a in assets} == {"deck_original", "audio", "data_xlsx"}


@pytest.mark.asyncio
async def test_create_review_rejects_oversized_deck(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")
    queue = FakeQueue()
    big = b"x" * (review_service.MAX_DECK_SIZE_BYTES + 1)

    with pytest.raises(ReviewTooLargeError):
        await review_service.create_review(
            db_session,
            user=user,
            deck=_upload("deck.pptx", big),
            audio=None,
            data=None,
            storage=storage,
            queue=queue,  # type: ignore[arg-type]
            settings=settings,
            event_tracker=EventTracker(),
        )


@pytest.mark.asyncio
async def test_create_review_rejects_bad_deck_format(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")
    queue = FakeQueue()

    with pytest.raises(ReviewValidationError):
        await review_service.create_review(
            db_session,
            user=user,
            deck=_upload("deck.key"),
            audio=None,
            data=None,
            storage=storage,
            queue=queue,  # type: ignore[arg-type]
            settings=settings,
            event_tracker=EventTracker(),
        )


@pytest.mark.asyncio
async def test_create_review_exhausted_limit_raises_and_reserves_nothing(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    user = await _seed_user(db_session, free_left=0)
    storage = LocalStorage(tmp_path / "store")
    queue = FakeQueue()

    with pytest.raises(LimitExceededError):
        await review_service.create_review(
            db_session,
            user=user,
            deck=_upload("deck.pptx"),
            audio=None,
            data=None,
            storage=storage,
            queue=queue,  # type: ignore[arg-type]
            settings=settings,
            event_tracker=EventTracker(),
        )
    assert queue.enqueued == []
    reviews = (await db_session.execute(select(Review))).scalars().all()
    assert reviews == []


@pytest.mark.asyncio
async def test_create_review_refunds_credit_on_post_reserve_failure(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    user = await _seed_user(db_session, free_left=2)
    await db_session.commit()  # real users are committed before a review request arrives
    queue = FakeQueue()

    class BoomStorage(LocalStorage):
        async def save(self, *args: Any, **kwargs: Any) -> str:
            raise RuntimeError("disk full")

    storage = BoomStorage(tmp_path / "store")

    with pytest.raises(RuntimeError):
        await review_service.create_review(
            db_session,
            user=user,
            deck=_upload("deck.pptx"),
            audio=None,
            data=None,
            storage=storage,
            queue=queue,  # type: ignore[arg-type]
            settings=settings,
            event_tracker=EventTracker(),
        )

    await db_session.refresh(user)
    assert user.free_reviews_left == 2
    reviews = (await db_session.execute(select(Review))).scalars().all()
    assert reviews == []


@pytest.mark.asyncio
async def test_list_and_get_review_scoped_to_owner(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    owner = await _seed_user(db_session)
    other = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")

    review = await review_service.create_review(
        db_session,
        user=owner,
        deck=_upload("deck.pptx"),
        audio=None,
        data=None,
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
        settings=settings,
        event_tracker=EventTracker(),
    )
    await db_session.commit()

    mine = await review_service.list_reviews(db_session, owner)
    assert [r.id for r in mine] == [review.id]

    theirs = await review_service.list_reviews(db_session, other)
    assert theirs == []

    with pytest.raises(ReviewNotFoundError):
        await review_service.get_review(db_session, other, review.id)


@pytest.mark.asyncio
async def test_delete_review_removes_findings_files_and_rehearsals(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")

    review = await review_service.create_review(
        db_session,
        user=user,
        deck=_upload("deck.pptx"),
        audio=None,
        data=None,
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
        settings=settings,
        event_tracker=EventTracker(),
    )
    await db_session.commit()

    assets = (
        (await db_session.execute(select(FileAsset).where(FileAsset.review_id == review.id)))
        .scalars()
        .all()
    )
    assert len(assets) == 1
    deck_asset_path = storage.root / assets[0].storage_path
    assert deck_asset_path.is_file()

    db_session.add(
        FindingRow(
            review_id=review.id,
            category="TYPOGRAPHY",
            severity="MINOR",
            title="t",
            description="d",
            fix_suggestion="f",
        )
    )
    audio_path = await storage.save(review.id, uuid4(), "rehearsal.webm", b"audio-bytes")
    db_session.add(
        Rehearsal(review_id=review.id, status="done", audio_path=audio_path, attempt_num=1)
    )
    await db_session.commit()
    rehearsal_audio_file = storage.root / audio_path
    assert rehearsal_audio_file.is_file()

    await review_service.delete_review(db_session, user, review.id, storage)

    assert not deck_asset_path.is_file()
    assert not rehearsal_audio_file.is_file()
    assert (await db_session.execute(select(Review))).scalars().all() == []
    assert (await db_session.execute(select(FileAsset))).scalars().all() == []
    assert (await db_session.execute(select(Rehearsal))).scalars().all() == []
    assert (await db_session.execute(select(FindingRow))).scalars().all() == []


@pytest.mark.asyncio
async def test_delete_review_not_owner_raises_and_keeps_row(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    owner = await _seed_user(db_session)
    other = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")

    review = await review_service.create_review(
        db_session,
        user=owner,
        deck=_upload("deck.pptx"),
        audio=None,
        data=None,
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
        settings=settings,
        event_tracker=EventTracker(),
    )
    await db_session.commit()

    with pytest.raises(ReviewNotFoundError):
        await review_service.delete_review(db_session, other, review.id, storage)

    remaining = (await db_session.execute(select(Review))).scalars().all()
    assert [r.id for r in remaining] == [review.id]


@pytest.mark.asyncio
async def test_delete_review_missing_id_raises(
    db_session: AsyncSession, settings: Settings, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")

    with pytest.raises(ReviewNotFoundError):
        await review_service.delete_review(db_session, user, uuid4(), storage)
