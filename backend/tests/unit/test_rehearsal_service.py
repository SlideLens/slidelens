"""Unit tests for app.services.rehearsal_service."""

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

from app.models import Base, Rehearsal, Review, ReviewStatus, User, UserPlan
from app.schemas.rehearsals import SlideTimingIn
from app.services import rehearsal_service
from app.services.exceptions import (
    RehearsalNotFoundError,
    RehearsalValidationError,
    ReviewNotFoundError,
    ReviewNotReadyError,
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
        f"sqlite+aiosqlite:///{tmp_path / 'rehearsals.db'}",
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


async def _seed_user(session: AsyncSession) -> User:
    user = User(
        email=f"{uuid4()}@example.com",
        password_hash="x",
        plan=UserPlan.FREE.value,
        free_reviews_left=2,
        email_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _seed_review(
    session: AsyncSession, user: User, *, status: str = ReviewStatus.DONE.value
) -> Review:
    review = Review(user_id=user.id, status=status, deck_filename="deck.pptx")
    session.add(review)
    await session.flush()
    return review


def _audio(name: str = "rehearsal.webm", data: bytes = b"fake-audio") -> UploadFile:
    return UploadFile(io.BytesIO(data), filename=name)


def _timings() -> list[SlideTimingIn]:
    return [SlideTimingIn(slide_num=1, start=0.0, end=5.0)]


@pytest.mark.asyncio
async def test_create_rehearsal_enqueues_and_saves_audio(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user)
    storage = LocalStorage(tmp_path / "store")
    queue = FakeQueue()

    rehearsal = await rehearsal_service.create_rehearsal(
        db_session,
        user=user,
        review_id=review.id,
        audio=_audio(),
        slide_timings=_timings(),
        storage=storage,
        queue=queue,  # type: ignore[arg-type]
    )

    assert rehearsal.status == "queued"
    assert rehearsal.attempt_num == 1
    assert rehearsal.audio_path is not None
    assert (storage.root / rehearsal.audio_path).is_file()
    assert queue.enqueued == [("process_rehearsal", (str(rehearsal.id),))]


@pytest.mark.asyncio
async def test_create_rehearsal_attempt_num_increments(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user)
    storage = LocalStorage(tmp_path / "store")

    first = await rehearsal_service.create_rehearsal(
        db_session,
        user=user,
        review_id=review.id,
        audio=_audio(),
        slide_timings=_timings(),
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
    )
    second = await rehearsal_service.create_rehearsal(
        db_session,
        user=user,
        review_id=review.id,
        audio=_audio(),
        slide_timings=_timings(),
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
    )

    assert first.attempt_num == 1
    assert second.attempt_num == 2


@pytest.mark.asyncio
async def test_create_rehearsal_requires_done_review(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user, status=ReviewStatus.PROCESSING.value)
    storage = LocalStorage(tmp_path / "store")

    with pytest.raises(ReviewNotReadyError):
        await rehearsal_service.create_rehearsal(
            db_session,
            user=user,
            review_id=review.id,
            audio=_audio(),
            slide_timings=_timings(),
            storage=storage,
            queue=FakeQueue(),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_create_rehearsal_rejects_missing_review(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")

    with pytest.raises(ReviewNotFoundError):
        await rehearsal_service.create_rehearsal(
            db_session,
            user=user,
            review_id=uuid4(),
            audio=_audio(),
            slide_timings=_timings(),
            storage=storage,
            queue=FakeQueue(),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_create_rehearsal_rejects_bad_audio_extension(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user)
    storage = LocalStorage(tmp_path / "store")

    with pytest.raises(RehearsalValidationError):
        await rehearsal_service.create_rehearsal(
            db_session,
            user=user,
            review_id=review.id,
            audio=_audio("clip.exe"),
            slide_timings=_timings(),
            storage=storage,
            queue=FakeQueue(),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_create_rehearsal_rejects_empty_slide_timings(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user)
    storage = LocalStorage(tmp_path / "store")

    with pytest.raises(RehearsalValidationError):
        await rehearsal_service.create_rehearsal(
            db_session,
            user=user,
            review_id=review.id,
            audio=_audio(),
            slide_timings=[],
            storage=storage,
            queue=FakeQueue(),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_list_and_get_rehearsal_scoped_to_owner(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    owner = await _seed_user(db_session)
    other = await _seed_user(db_session)
    review = await _seed_review(db_session, owner)
    storage = LocalStorage(tmp_path / "store")

    rehearsal = await rehearsal_service.create_rehearsal(
        db_session,
        user=owner,
        review_id=review.id,
        audio=_audio(),
        slide_timings=_timings(),
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
    )

    mine = await rehearsal_service.list_rehearsals(db_session, owner, review.id)
    assert [r.id for r in mine] == [rehearsal.id]

    with pytest.raises(ReviewNotFoundError):
        await rehearsal_service.list_rehearsals(db_session, other, review.id)

    with pytest.raises(RehearsalNotFoundError):
        await rehearsal_service.get_rehearsal(db_session, other, rehearsal.id)


@pytest.mark.asyncio
async def test_get_rehearsal_audio_returns_bytes_and_storage_path(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user)
    storage = LocalStorage(tmp_path / "store")

    rehearsal = await rehearsal_service.create_rehearsal(
        db_session,
        user=user,
        review_id=review.id,
        audio=_audio(data=b"raw-recording"),
        slide_timings=_timings(),
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
    )

    data, storage_path = await rehearsal_service.get_rehearsal_audio(
        db_session, user, rehearsal.id, storage
    )

    assert data == b"raw-recording"
    assert storage_path == rehearsal.audio_path
    assert storage_path.endswith("_rehearsal.webm")


@pytest.mark.asyncio
async def test_get_rehearsal_audio_not_owner_raises(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    owner = await _seed_user(db_session)
    other = await _seed_user(db_session)
    review = await _seed_review(db_session, owner)
    storage = LocalStorage(tmp_path / "store")

    rehearsal = await rehearsal_service.create_rehearsal(
        db_session,
        user=owner,
        review_id=review.id,
        audio=_audio(),
        slide_timings=_timings(),
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
    )

    with pytest.raises(RehearsalNotFoundError):
        await rehearsal_service.get_rehearsal_audio(db_session, other, rehearsal.id, storage)


@pytest.mark.asyncio
async def test_get_rehearsal_audio_missing_id_raises(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")

    with pytest.raises(RehearsalNotFoundError):
        await rehearsal_service.get_rehearsal_audio(db_session, user, uuid4(), storage)


@pytest.mark.asyncio
async def test_delete_rehearsal_removes_row_and_audio_file(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user)
    storage = LocalStorage(tmp_path / "store")

    rehearsal = await rehearsal_service.create_rehearsal(
        db_session,
        user=user,
        review_id=review.id,
        audio=_audio(),
        slide_timings=_timings(),
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
    )
    audio_file = storage.root / rehearsal.audio_path
    assert audio_file.is_file()

    await rehearsal_service.delete_rehearsal(db_session, user, rehearsal.id, storage)

    assert not audio_file.is_file()
    remaining = (await db_session.execute(select(Rehearsal))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_rehearsal_not_owner_raises_and_keeps_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    owner = await _seed_user(db_session)
    other = await _seed_user(db_session)
    review = await _seed_review(db_session, owner)
    storage = LocalStorage(tmp_path / "store")

    rehearsal = await rehearsal_service.create_rehearsal(
        db_session,
        user=owner,
        review_id=review.id,
        audio=_audio(),
        slide_timings=_timings(),
        storage=storage,
        queue=FakeQueue(),  # type: ignore[arg-type]
    )

    with pytest.raises(RehearsalNotFoundError):
        await rehearsal_service.delete_rehearsal(db_session, other, rehearsal.id, storage)

    remaining = (await db_session.execute(select(Rehearsal))).scalars().all()
    assert [r.id for r in remaining] == [rehearsal.id]


@pytest.mark.asyncio
async def test_delete_rehearsal_missing_id_raises(db_session: AsyncSession, tmp_path: Path) -> None:
    user = await _seed_user(db_session)
    storage = LocalStorage(tmp_path / "store")

    with pytest.raises(RehearsalNotFoundError):
        await rehearsal_service.delete_rehearsal(db_session, user, uuid4(), storage)
