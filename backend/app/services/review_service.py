"""Reviews domain logic: upload validation, credit reservation, status/report reads."""

from __future__ import annotations

import asyncio
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from arq import ArqRedis
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import FileAsset, FileAssetKind, FindingRow, Rehearsal, Review, ReviewStatus, User
from app.schemas.reviews import FindingOut, ReportOut, SlideOut
from app.security import create_file_token
from app.services.events import EventTracker
from app.services.exceptions import (
    ReviewNotFoundError,
    ReviewNotReadyError,
    ReviewTooLargeError,
    ReviewValidationError,
)
from app.services.file_assets import save_file_asset
from app.services.limits import LimitService
from app.services.storage import StorageBackend
from core.constants import MAX_AUDIO_SIZE_MB, MAX_DECK_SIZE_MB, AllowedDeckFormat
from core.context import ReviewContext
from core.ingest import DeckIngestor
from core.ingest_errors import IngestError

_SLIDE_FILENAME_RE = re.compile(r"slide_(\d+)\.png$")

ALLOWED_AUDIO_EXTENSIONS = frozenset({".mp4", ".mov", ".mp3", ".m4a", ".wav"})
ALLOWED_DATA_EXTENSIONS = frozenset({".xlsx"})
MAX_DECK_SIZE_BYTES = MAX_DECK_SIZE_MB * 1024 * 1024
MAX_AUDIO_SIZE_BYTES = MAX_AUDIO_SIZE_MB * 1024 * 1024


def _extension(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


async def create_review(
    session: AsyncSession,
    *,
    user: User,
    deck: UploadFile,
    audio: UploadFile | None,
    data: UploadFile | None,
    storage: StorageBackend,
    queue: ArqRedis,
    settings: Settings,
    event_tracker: EventTracker,
) -> Review:
    """Validate, reserve a credit, persist files, create the Review, and enqueue it."""
    user_id = user.id  # captured before any commit/rollback can expire the attribute
    deck_bytes = await deck.read()
    if len(deck_bytes) > MAX_DECK_SIZE_BYTES:
        raise ReviewTooLargeError(f"Дека больше {MAX_DECK_SIZE_MB} МБ")
    if _extension(deck.filename) not in {fmt.value for fmt in AllowedDeckFormat}:
        raise ReviewValidationError("Дека должна быть в формате PPTX или PDF")

    audio_bytes: bytes | None = None
    audio_filename = ""
    if audio is not None:
        audio_bytes = await audio.read()
        audio_filename = audio.filename or "audio"
        if _extension(audio_filename) not in ALLOWED_AUDIO_EXTENSIONS:
            raise ReviewValidationError("Запись питча должна быть mp4/mov/mp3/m4a/wav")
        # Грубый отсев на входе; точный потолок по минутам — в AudioExtractor,
        # потому что размер файла о длительности почти ничего не говорит.
        if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
            raise ReviewTooLargeError(f"Запись питча больше {MAX_AUDIO_SIZE_MB} МБ")

    data_bytes: bytes | None = None
    data_filename = ""
    if data is not None:
        data_bytes = await data.read()
        data_filename = data.filename or "data.xlsx"
        if _extension(data_filename) not in ALLOWED_DATA_EXTENSIONS:
            raise ReviewValidationError("Файл с данными должен быть в формате XLSX")

    limits = LimitService()
    _user, credit_source = await limits.check_and_reserve(session, user_id)
    # Commit the reservation as its own transaction: a later rollback (below) must not
    # silently undo the decrement, or the refund on top of it would double-credit the user.
    await session.commit()

    try:
        review = Review(
            user_id=user_id,
            status=ReviewStatus.QUEUED.value,
            deck_filename=deck.filename or "deck",
            has_audio=audio_bytes is not None,
            has_data=data_bytes is not None,
            credit_source=credit_source,
        )
        session.add(review)
        await session.flush()

        expires_at = datetime.now(UTC) + timedelta(days=settings.file_expire_days)
        await save_file_asset(
            storage,
            session,
            review_id=review.id,
            kind=FileAssetKind.DECK_ORIGINAL,
            filename=deck.filename or "deck",
            data=deck_bytes,
            expires_at=expires_at,
        )
        if audio_bytes is not None:
            await save_file_asset(
                storage,
                session,
                review_id=review.id,
                kind=FileAssetKind.AUDIO,
                filename=audio_filename,
                data=audio_bytes,
                expires_at=expires_at,
            )
        if data_bytes is not None:
            await save_file_asset(
                storage,
                session,
                review_id=review.id,
                kind=FileAssetKind.DATA_XLSX,
                filename=data_filename,
                data=data_bytes,
                expires_at=expires_at,
            )

        await event_tracker.track(
            session,
            user_id,
            "review_created",
            has_audio=review.has_audio,
            has_data=review.has_data,
        )
        await queue.enqueue_job("process_review", str(review.id))
        await session.commit()
    except Exception:
        await session.rollback()
        await limits.refund(session, user_id, credit_source)
        await session.commit()
        raise

    return review


async def list_reviews(session: AsyncSession, user: User) -> list[Review]:
    result = await session.execute(
        select(Review).where(Review.user_id == user.id).order_by(Review.created_at.desc())
    )
    return list(result.scalars().all())


async def get_review(session: AsyncSession, user: User, review_id: UUID) -> Review:
    result = await session.execute(
        select(Review).where(Review.id == review_id, Review.user_id == user.id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise ReviewNotFoundError()
    return review


def _finding_out(row: FindingRow, settings: Settings) -> FindingOut:
    finding_out = FindingOut.model_validate(row)
    if row.screenshot_asset_id is not None:
        token = create_file_token(row.screenshot_asset_id, settings)
        url = f"/api/v1/files/{row.screenshot_asset_id}?sig={token}"
        finding_out = finding_out.model_copy(update={"screenshot_url": url})
    return finding_out


async def get_report(
    session: AsyncSession, user: User, review_id: UUID, settings: Settings
) -> ReportOut:
    review = await get_review(session, user, review_id)
    if review.status != ReviewStatus.DONE.value:
        raise ReviewNotReadyError()

    findings_result = await session.execute(
        select(FindingRow)
        .where(FindingRow.review_id == review.id)
        .order_by(FindingRow.severity, FindingRow.slide_num)
    )
    findings = list(findings_result.scalars().all())

    assets_result = await session.execute(select(FileAsset).where(FileAsset.review_id == review.id))
    assets = list(assets_result.scalars().all())
    pdf_asset_id = next((a.id for a in assets if a.kind == FileAssetKind.REPORT_PDF.value), None)
    fixed_pptx_asset = next(
        (a for a in assets if a.kind == FileAssetKind.FIXED_PPTX.value), None
    )
    fixed_pptx_filename = (
        Path(fixed_pptx_asset.storage_path).name.split("_", 1)[-1]
        if fixed_pptx_asset is not None
        else None
    )

    return ReportOut(
        review_id=review.id,
        score=review.score or 0,
        n_slides=review.n_slides or 0,
        findings=[_finding_out(f, settings) for f in findings],
        delivery=review.delivery_metrics,
        auto_fixed_count=sum(1 for f in findings if f.auto_fixed),
        pdf_asset_id=pdf_asset_id,
        fixed_pptx_asset_id=fixed_pptx_asset.id if fixed_pptx_asset is not None else None,
        fixed_pptx_filename=fixed_pptx_filename,
    )


def _slide_out(asset: FileAsset, settings: Settings) -> SlideOut | None:
    match = _SLIDE_FILENAME_RE.search(asset.storage_path)
    if match is None:
        return None
    token = create_file_token(asset.id, settings)
    return SlideOut(slide_num=int(match.group(1)), url=f"/api/v1/files/{asset.id}?sig={token}")


async def get_slides(
    session: AsyncSession,
    user: User,
    review_id: UUID,
    storage: StorageBackend,
    settings: Settings,
) -> list[SlideOut]:
    """Every rendered slide PNG for a *done* Review, in order.

    Unlike ``ANNOTATED_PNG`` (saved only for slides with a bbox-carrying Finding —
    ADR 0002), this covers every slide, which the rehearsal recorder needs to show
    while the user pages through the deck. Lazily backfilled once per Review from
    the still-retained original deck file, then cached as ``SLIDE_PNG`` assets.
    """
    review = await get_review(session, user, review_id)
    if review.status != ReviewStatus.DONE.value:
        raise ReviewNotReadyError()

    assets_result = await session.execute(
        select(FileAsset).where(
            FileAsset.review_id == review.id,
            FileAsset.kind == FileAssetKind.SLIDE_PNG.value,
        )
    )
    assets = list(assets_result.scalars().all())
    if not assets:
        assets = await _backfill_slide_assets(session, review, storage, settings)

    slides = [s for a in assets if (s := _slide_out(a, settings)) is not None]
    slides.sort(key=lambda s: s.slide_num)
    return slides


async def _backfill_slide_assets(
    session: AsyncSession,
    review: Review,
    storage: StorageBackend,
    settings: Settings,
) -> list[FileAsset]:
    deck_asset_result = await session.execute(
        select(FileAsset).where(
            FileAsset.review_id == review.id,
            FileAsset.kind == FileAssetKind.DECK_ORIGINAL.value,
        )
    )
    deck_asset = deck_asset_result.scalar_one_or_none()
    if deck_asset is None:
        raise ReviewNotFoundError("Исходный файл Деки больше недоступен (истёк срок хранения)")

    deck_bytes = await storage.open(deck_asset.storage_path)
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        deck_path = workdir / Path(deck_asset.storage_path).name
        await asyncio.to_thread(deck_path.write_bytes, deck_bytes)

        ctx = ReviewContext(workdir=workdir, review_id=review.id)
        try:
            await DeckIngestor().ingest(deck_path, workdir, ctx)
        except IngestError as exc:
            raise ReviewNotFoundError(f"Не удалось перерендерить слайды: {exc}") from exc

        expires_at = datetime.now(UTC) + timedelta(days=settings.file_expire_days)
        assets: list[FileAsset] = []
        for slide_num in sorted(ctx.slide_pngs):
            data = await asyncio.to_thread(ctx.slide_pngs[slide_num].read_bytes)
            asset = await save_file_asset(
                storage,
                session,
                review_id=review.id,
                kind=FileAssetKind.SLIDE_PNG,
                filename=f"slide_{slide_num:03d}.png",
                data=data,
                expires_at=expires_at,
            )
            assets.append(asset)
        await session.commit()
        return assets


async def delete_review(
    session: AsyncSession,
    user: User,
    review_id: UUID,
    storage: StorageBackend,
) -> None:
    """Delete a Review and everything tied to it: Находки, files (rows + bytes on
    disk), rehearsal attempts (rows + their audio). Explicit, not relying on the DB's
    ondelete=CASCADE — keeps this correct regardless of backend and easy to unit test.
    """
    review = await get_review(session, user, review_id)

    findings_result = await session.execute(
        select(FindingRow).where(FindingRow.review_id == review.id)
    )
    for finding in findings_result.scalars().all():
        await session.delete(finding)

    assets_result = await session.execute(select(FileAsset).where(FileAsset.review_id == review.id))
    for asset in assets_result.scalars().all():
        await storage.delete(asset.storage_path)
        await session.delete(asset)

    rehearsals_result = await session.execute(
        select(Rehearsal).where(Rehearsal.review_id == review.id)
    )
    for rehearsal in rehearsals_result.scalars().all():
        if rehearsal.audio_path:
            await storage.delete(rehearsal.audio_path)
        await session.delete(rehearsal)

    await session.delete(review)
    await session.commit()
