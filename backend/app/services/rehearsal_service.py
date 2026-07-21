"""Rehearsal domain logic: create/list/status/report (П2-П4, ADR 0005)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from arq import ArqRedis
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rehearsal, RehearsalStatus, Review, ReviewStatus, User
from app.schemas.rehearsals import (
    RehearsalDeltaOut,
    RehearsalFindingOut,
    RehearsalReportOut,
    SlideTimingIn,
    TimingMapEntryOut,
)
from app.services.exceptions import (
    RehearsalNotFoundError,
    RehearsalNotReadyError,
    RehearsalValidationError,
    ReviewNotFoundError,
    ReviewNotReadyError,
)
from app.services.storage import StorageBackend
from core.analyzers.crossmodal import classify_slide_pacing
from core.schemas import DeliveryMetrics

ALLOWED_REHEARSAL_AUDIO_EXTENSIONS = frozenset(
    {".mp4", ".mov", ".mp3", ".m4a", ".wav", ".webm", ".ogg"}
)


def _extension(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


async def _get_owned_review(session: AsyncSession, user: User, review_id: UUID) -> Review:
    result = await session.execute(
        select(Review).where(Review.id == review_id, Review.user_id == user.id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise ReviewNotFoundError()
    return review


async def create_rehearsal(
    session: AsyncSession,
    *,
    user: User,
    review_id: UUID,
    audio: UploadFile,
    slide_timings: list[SlideTimingIn],
    storage: StorageBackend,
    queue: ArqRedis,
) -> Rehearsal:
    """Validate, persist the recording, and enqueue ``process_rehearsal``."""
    review = await _get_owned_review(session, user, review_id)
    if review.status != ReviewStatus.DONE.value:
        raise ReviewNotReadyError("Разбор ещё не готов — дождитесь его завершения перед репетицией")

    if _extension(audio.filename) not in ALLOWED_REHEARSAL_AUDIO_EXTENSIONS:
        raise RehearsalValidationError("Запись должна быть аудио- или видеофайлом")
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise RehearsalValidationError("Аудиозапись пуста")
    if not slide_timings:
        raise RehearsalValidationError("Не удалось определить тайминг слайдов записи")

    max_attempt_result = await session.execute(
        select(func.max(Rehearsal.attempt_num)).where(Rehearsal.review_id == review_id)
    )
    attempt_num = (max_attempt_result.scalar() or 0) + 1

    rehearsal = Rehearsal(
        review_id=review.id,
        status=RehearsalStatus.QUEUED.value,
        slide_timings=[t.model_dump() for t in slide_timings],
        attempt_num=attempt_num,
    )
    session.add(rehearsal)
    await session.flush()

    rehearsal.audio_path = await storage.save(
        review.id, rehearsal.id, audio.filename or "rehearsal.webm", audio_bytes
    )
    await queue.enqueue_job("process_rehearsal", str(rehearsal.id))
    await session.commit()
    return rehearsal


async def list_rehearsals(
    session: AsyncSession, user: User, review_id: UUID
) -> list[Rehearsal]:
    await _get_owned_review(session, user, review_id)
    result = await session.execute(
        select(Rehearsal)
        .where(Rehearsal.review_id == review_id)
        .order_by(Rehearsal.attempt_num)
    )
    return list(result.scalars().all())


async def get_rehearsal(session: AsyncSession, user: User, rehearsal_id: UUID) -> Rehearsal:
    result = await session.execute(
        select(Rehearsal)
        .join(Review, Rehearsal.review_id == Review.id)
        .where(Rehearsal.id == rehearsal_id, Review.user_id == user.id)
    )
    rehearsal = result.scalar_one_or_none()
    if rehearsal is None:
        raise RehearsalNotFoundError()
    return rehearsal


async def get_rehearsal_audio(
    session: AsyncSession,
    user: User,
    rehearsal_id: UUID,
    storage: StorageBackend,
) -> tuple[bytes, str]:
    """Return the raw recording bytes and its storage path (for the download filename)."""
    rehearsal = await get_rehearsal(session, user, rehearsal_id)
    if not rehearsal.audio_path:
        raise RehearsalNotFoundError()
    data = await storage.open(rehearsal.audio_path)
    return data, rehearsal.audio_path


async def delete_rehearsal(
    session: AsyncSession,
    user: User,
    rehearsal_id: UUID,
    storage: StorageBackend,
) -> None:
    rehearsal = await get_rehearsal(session, user, rehearsal_id)
    if rehearsal.audio_path:
        await storage.delete(rehearsal.audio_path)
    await session.delete(rehearsal)
    await session.commit()


def _delta(current: Rehearsal, previous: Rehearsal) -> RehearsalDeltaOut | None:
    if not current.delivery_metrics or not previous.delivery_metrics:
        return None
    cur = DeliveryMetrics.model_validate(current.delivery_metrics)
    prev = DeliveryMetrics.model_validate(previous.delivery_metrics)
    return RehearsalDeltaOut(
        previous_attempt_num=previous.attempt_num,
        words_per_minute_delta=cur.words_per_minute - prev.words_per_minute,
        filler_words_delta=sum(cur.filler_words.values()) - sum(prev.filler_words.values()),
        long_pauses_delta=len(cur.long_pauses) - len(prev.long_pauses),
    )


async def get_rehearsal_report(
    session: AsyncSession, user: User, rehearsal_id: UUID
) -> RehearsalReportOut:
    rehearsal = await get_rehearsal(session, user, rehearsal_id)
    if rehearsal.status != RehearsalStatus.DONE.value:
        raise RehearsalNotReadyError()

    timing_map = [
        TimingMapEntryOut(
            slide_num=t["slide_num"],
            start=t["start"],
            end=t["end"],
            duration=t["end"] - t["start"],
            pacing=classify_slide_pacing(t["end"] - t["start"]),
        )
        for t in (rehearsal.slide_timings or [])
    ]
    timing_map.sort(key=lambda entry: entry.slide_num)

    findings = [RehearsalFindingOut.model_validate(f) for f in (rehearsal.findings or [])]

    delta: RehearsalDeltaOut | None = None
    if rehearsal.attempt_num > 1:
        prev_result = await session.execute(
            select(Rehearsal)
            .where(
                Rehearsal.review_id == rehearsal.review_id,
                Rehearsal.attempt_num < rehearsal.attempt_num,
                Rehearsal.status == RehearsalStatus.DONE.value,
            )
            .order_by(Rehearsal.attempt_num.desc())
            .limit(1)
        )
        previous = prev_result.scalar_one_or_none()
        if previous is not None:
            delta = _delta(rehearsal, previous)

    return RehearsalReportOut(
        rehearsal_id=rehearsal.id,
        review_id=rehearsal.review_id,
        attempt_num=rehearsal.attempt_num,
        status=RehearsalStatus(rehearsal.status),
        fail_reason=rehearsal.fail_reason,
        delivery=DeliveryMetrics.model_validate(rehearsal.delivery_metrics)
        if rehearsal.delivery_metrics
        else None,
        timing_map=timing_map,
        findings=findings,
        delta=delta,
    )
