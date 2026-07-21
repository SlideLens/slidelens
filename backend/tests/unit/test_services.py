"""Unit tests for Storage, Email, EventTracker, LimitService."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.models import Base, Event, FileAsset, FileAssetKind, Review, User, UserPlan
from app.services.email import EmailService
from app.services.events import EventTracker
from app.services.exceptions import LimitExceededError
from app.services.limits import CreditSource, LimitService
from app.services.storage import LocalStorage
from worker.tasks import cleanup_expired_files


@pytest.fixture
async def db_session(tmp_path: Path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'services.db'}",
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
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    from app.config import get_settings

    get_settings.cache_clear()
    return get_settings()


async def _seed_user(
    session: AsyncSession,
    *,
    free_left: int = 2,
    balance: int = 0,
    plan: str = UserPlan.FREE.value,
) -> User:
    user = User(
        email=f"{uuid4()}@example.com",
        password_hash="x",
        plan=plan,
        free_reviews_left=free_left,
        balance_reviews=balance,
        email_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _seed_review(session: AsyncSession, user: User) -> Review:
    review = Review(user_id=user.id, status="queued", deck_filename="deck.pptx")
    session.add(review)
    await session.flush()
    return review


@pytest.mark.asyncio
async def test_local_storage_save_open(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "store")
    review_id, asset_id = uuid4(), uuid4()
    path = await storage.save(review_id, asset_id, "deck.pptx", b"hello-deck")
    assert await storage.open(path) == b"hello-deck"
    assert Path(await storage.url(path)).exists()


@pytest.mark.asyncio
async def test_delete_expired_removes_files_and_rows(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path / "store")
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user)

    expired_id, live_id = uuid4(), uuid4()
    expired_path = await storage.save(review.id, expired_id, "old.png", b"old")
    live_path = await storage.save(review.id, live_id, "new.png", b"new")

    past = datetime.now(UTC) - timedelta(days=1)
    future = datetime.now(UTC) + timedelta(days=7)
    db_session.add(
        FileAsset(
            id=expired_id,
            review_id=review.id,
            kind=FileAssetKind.SLIDE_PNG.value,
            storage_path=expired_path,
            size_bytes=3,
            expires_at=past,
        )
    )
    db_session.add(
        FileAsset(
            id=live_id,
            review_id=review.id,
            kind=FileAssetKind.SLIDE_PNG.value,
            storage_path=live_path,
            size_bytes=3,
            expires_at=future,
        )
    )
    await db_session.commit()

    removed = await storage.delete_expired(db_session)
    await db_session.commit()
    assert removed == 1
    assert not (tmp_path / "store" / expired_path).exists()
    assert (tmp_path / "store" / live_path).exists()
    assert await db_session.get(FileAsset, expired_id) is None
    assert await db_session.get(FileAsset, live_id) is not None


@pytest.mark.asyncio
async def test_cleanup_expired_files_task(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = tmp_path / "store"
    monkeypatch.setenv("STORAGE_ROOT", str(store))
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from app.config import get_settings

    get_settings.cache_clear()

    storage = LocalStorage(store)
    user = await _seed_user(db_session)
    review = await _seed_review(db_session, user)
    asset_id = uuid4()
    path = await storage.save(review.id, asset_id, "gone.png", b"x")
    db_session.add(
        FileAsset(
            id=asset_id,
            review_id=review.id,
            kind=FileAssetKind.SLIDE_PNG.value,
            storage_path=path,
            size_bytes=1,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.commit()

    removed = await cleanup_expired_files(db_session)
    await db_session.commit()
    assert removed == 1
    assert not (store / path).exists()


@pytest.mark.asyncio
async def test_email_report_ready_includes_score(settings: Settings) -> None:
    email = EmailService(settings)
    review_id = uuid4()
    await email.send_report_ready("user@example.com", review_id, score=74)
    msg = email.outbox[0]
    assert "74" in msg.subject
    assert "Скор" in msg.html
    assert "74" in msg.html
    assert str(review_id) in msg.html


@pytest.mark.asyncio
async def test_event_tracker_inserts(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    tracker = EventTracker()
    event = await tracker.track(db_session, user.id, "signup", source="test")
    await db_session.commit()
    loaded = await db_session.get(Event, event.id)
    assert loaded is not None
    assert loaded.name == "signup"
    assert loaded.properties == {"source": "test"}
    assert loaded.user_id == user.id


@pytest.mark.asyncio
async def test_limit_reserve_and_exhausted(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session, free_left=1)
    limits = LimitService()
    await limits.check_and_reserve(db_session, user.id)
    await db_session.refresh(user)
    assert user.free_reviews_left == 0
    with pytest.raises(LimitExceededError):
        await limits.check_and_reserve(db_session, user.id)


@pytest.mark.asyncio
async def test_refund_returns_the_credit_to_its_own_wallet(db_session: AsyncSession) -> None:
    """Купленный Разбор нельзя возвращать как бесплатный — это подарок за счёт кассы."""
    user = await _seed_user(db_session, free_left=0, balance=0)
    limits = LimitService()

    await limits.refund(db_session, user.id, CreditSource.BALANCE.value)
    await db_session.refresh(user)
    assert (user.free_reviews_left, user.balance_reviews) == (0, 1)

    await limits.refund(db_session, user.id, CreditSource.FREE.value)
    await db_session.refresh(user)
    assert (user.free_reviews_left, user.balance_reviews) == (1, 1)


@pytest.mark.asyncio
async def test_admin_run_refunds_nothing(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session, free_left=0, balance=0)
    user.is_admin = True
    await db_session.flush()

    _reserved, source = await LimitService().check_and_reserve(db_session, user.id)
    await LimitService().refund(db_session, user.id, source)
    await db_session.refresh(user)

    assert source == CreditSource.ADMIN.value
    assert (user.free_reviews_left, user.balance_reviews) == (0, 0)


@pytest.mark.asyncio
async def test_paid_plan_without_balance_is_blocked(db_session: AsyncSession) -> None:
    """Раньше plan='paid' проходил мимо учёта — один подписчик мог сжечь любую сумму."""
    user = await _seed_user(db_session, free_left=0, balance=0, plan=UserPlan.PAID.value)

    with pytest.raises(LimitExceededError):
        await LimitService().check_and_reserve(db_session, user.id)


@pytest.mark.asyncio
async def test_free_credits_are_spent_before_the_purchased_pack(db_session: AsyncSession) -> None:
    """Иначе купивший пакет теряет неиспользованный триал."""
    user = await _seed_user(db_session, free_left=1, balance=1)
    limits = LimitService()

    _u, first = await limits.check_and_reserve(db_session, user.id)
    await db_session.refresh(user)
    assert first == CreditSource.FREE.value
    assert (user.free_reviews_left, user.balance_reviews) == (0, 1)

    _u, second = await limits.check_and_reserve(db_session, user.id)
    await db_session.refresh(user)
    assert second == CreditSource.BALANCE.value
    assert (user.free_reviews_left, user.balance_reviews) == (0, 0)

    with pytest.raises(LimitExceededError):
        await limits.check_and_reserve(db_session, user.id)


@pytest.mark.asyncio
async def test_concurrent_reserve_does_not_oversell(tmp_path: Path) -> None:
    db_path = tmp_path / "race.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await _seed_user(session, free_left=1)
        await session.commit()
        user_id = user.id

    limits = LimitService()
    barrier = asyncio.Barrier(2)

    async def attempt() -> str:
        async with factory() as session:
            await barrier.wait()
            try:
                async with session.begin():
                    await limits.check_and_reserve(session, user_id)
                return "ok"
            except LimitExceededError:
                return "limit"
            except Exception as exc:  # noqa: BLE001 — surface lock contention as failure path
                await session.rollback()
                return f"err:{type(exc).__name__}"

    results = await asyncio.gather(attempt(), attempt())
    assert sorted(results) == ["limit", "ok"]

    async with factory() as session:
        final = await session.get(User, user_id)
        assert final is not None
        assert final.free_reviews_left == 0

    await engine.dispose()
