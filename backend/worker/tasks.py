"""ARQ tasks: ``process_review``, ``cleanup_expired_files``, and ``WorkerSettings``."""

from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import sentry_sdk
import structlog
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.models import (
    FileAsset,
    FileAssetKind,
    Rehearsal,
    RehearsalStatus,
    Review,
    ReviewStatus,
    User,
)
from app.services.email import EmailService
from app.services.events import EventTracker
from app.services.file_assets import save_file_asset
from app.services.finding_mapper import finding_to_row
from app.services.finding_service import upsert_fixed_pptx
from app.services.limits import LimitService
from app.services.storage import LocalStorage, StorageBackend
from core.aggregate import Aggregator
from core.analyzers.crossmodal import analyze_rehearsal
from core.annotate import Annotator
from core.constants import MAX_AUDIO_MINUTES
from core.context import ReviewContext
from core.fix import FIXED_DECK_FILENAME
from core.ingest import AudioExtractor, DeckIngestor
from core.ingest_errors import (
    AudioTooLongError,
    CorruptedFileError,
    DeckTooLargeError,
    EmptyDeckError,
    NoAudioTrackError,
    PasswordProtectedError,
    RenderTimeoutError,
    UnsupportedDeckFormatError,
)
from core.llm import LLMClient, LLMConfig
from core.report import PdfExporter, ReportBuilder
from core.report_schemas import ReportOut
from core.run import PipelineOrchestrator, default_steps
from core.schemas import SlideTiming
from observability.setup import observe_review_cost, observe_review_status

logger = structlog.get_logger(__name__)

_FAIL_REASONS: dict[type[Exception], str] = {
    PasswordProtectedError: "Файл защищён паролем",
    UnsupportedDeckFormatError: "Неподдерживаемый формат файла — нужен PPTX или PDF",
    EmptyDeckError: "В файле не найдено ни одного слайда",
    DeckTooLargeError: "Дека превышает лимит размера или числа слайдов",
    NoAudioTrackError: "В записи питча не найдена звуковая дорожка",
    AudioTooLongError: f"Запись питча длиннее {MAX_AUDIO_MINUTES:.0f} минут",
    RenderTimeoutError: "Не удалось отрендерить файл за отведённое время",
    CorruptedFileError: "Файл повреждён или не открывается",
}
_GENERIC_FAIL_REASON = "Не удалось обработать Разбор — мы уже разбираемся"


def _fail_reason(exc: Exception) -> str:
    for exc_type, message in _FAIL_REASONS.items():
        if isinstance(exc, exc_type):
            return message
    return _GENERIC_FAIL_REASON


def _llm_config(settings: Settings) -> LLMConfig:
    return LLMConfig(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
        model_full=settings.llm_model_full,
        model_screening=settings.llm_model_screening,
        model_transcription=settings.llm_model_transcription,
        timeout_seconds=float(settings.llm_timeout_seconds),
    )


class _PipelineOutput:
    """Everything ``_persist_success`` needs, bundled from one pipeline run."""

    def __init__(
        self,
        *,
        ctx: ReviewContext,
        fixed_path: Path | None,
        annotations: dict[UUID, Path],
        report: ReportOut,
        pdf_bytes: bytes,
    ) -> None:
        self.ctx = ctx
        self.fixed_path = fixed_path
        self.annotations = annotations
        self.report = report
        self.pdf_bytes = pdf_bytes


async def cleanup_expired_files(session: AsyncSession | None = None) -> int:
    """Delete expired ``FileAsset`` rows and their files. Returns count removed."""
    settings = get_settings()
    storage = LocalStorage(Path(settings.storage_root))

    if session is not None:
        return await storage.delete_expired(session)

    engine = create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as owned:
            removed = await storage.delete_expired(owned)
            await owned.commit()
            return removed
    finally:
        await engine.dispose()


async def _download_inputs(
    session: AsyncSession,
    review: Review,
    storage: StorageBackend,
    workdir: Path,
) -> ReviewContext:
    workdir.mkdir(parents=True, exist_ok=True)
    result = await session.execute(select(FileAsset).where(FileAsset.review_id == review.id))
    assets = list(result.scalars().all())

    review_ctx = ReviewContext(workdir=workdir, review_id=review.id)
    for asset in assets:
        data = await storage.open(asset.storage_path)
        local_path = workdir / Path(asset.storage_path).name
        await asyncio.to_thread(local_path.write_bytes, data)
        if asset.kind == FileAssetKind.DECK_ORIGINAL.value:
            review_ctx.deck_path = local_path
        elif asset.kind == FileAssetKind.AUDIO.value:
            review_ctx.audio_path = local_path
        elif asset.kind == FileAssetKind.DATA_XLSX.value:
            review_ctx.xlsx_path = local_path

    if review_ctx.deck_path is None:
        raise CorruptedFileError(f"No deck_original FileAsset for review {review.id}")
    return review_ctx


async def _run_pipeline(review_ctx: ReviewContext, settings: Settings) -> _PipelineOutput:
    deck_path = review_ctx.deck_path
    assert deck_path is not None

    await DeckIngestor().ingest(deck_path, review_ctx.workdir, review_ctx)

    llm = LLMClient(_llm_config(settings))
    try:
        await PipelineOrchestrator(default_steps(llm)).run(review_ctx)
        review_ctx.findings = await Aggregator(llm).run(review_ctx.findings)
    finally:
        await llm.aclose()

    fixed_path: Path | None = None
    if deck_path.suffix.lower() == ".pptx":
        # Point-apply only (ticket П7): seed fixed.pptx as a copy of the original.
        # Users opt in via POST /findings/{id}/apply_fix — never batch-patch here.
        fixed_path = review_ctx.workdir / FIXED_DECK_FILENAME
        await asyncio.to_thread(shutil.copy2, deck_path, fixed_path)

    annotations = Annotator().annotate(review_ctx)
    report = ReportBuilder().build(review_ctx)
    _html, pdf_bytes = PdfExporter().export(report, annotations=annotations)

    return _PipelineOutput(
        ctx=review_ctx,
        fixed_path=fixed_path,
        annotations=annotations,
        report=report,
        pdf_bytes=pdf_bytes,
    )


async def _persist_success(
    session: AsyncSession,
    review: Review,
    output: _PipelineOutput,
    storage: StorageBackend,
    settings: Settings,
) -> None:
    review_ctx = output.ctx
    expires_at = datetime.now(UTC) + timedelta(days=settings.file_expire_days)

    # Сырые слайды: отчёт рисует рамки Находок поверх них вектором, поэтому нужны
    # все слайды, а не только те, где есть bbox. Файлы уже отрендерены пайплайном —
    # сохранить их здесь дешевле, чем потом перерендеривать Деку в бэкфилле
    # (``get_slides``), который к тому же ломается после протухания исходника.
    for slide_num in sorted(review_ctx.slide_pngs):
        slide_data = await asyncio.to_thread(review_ctx.slide_pngs[slide_num].read_bytes)
        await save_file_asset(
            storage,
            session,
            review_id=review.id,
            kind=FileAssetKind.SLIDE_PNG,
            filename=f"slide_{slide_num:03d}.png",
            data=slide_data,
            expires_at=expires_at,
        )

    path_to_asset_id: dict[Path, UUID] = {}
    finding_screenshot: dict[UUID, UUID] = {}
    for finding_id, path in output.annotations.items():
        if path not in path_to_asset_id:
            data = await asyncio.to_thread(path.read_bytes)
            asset = await save_file_asset(
                storage,
                session,
                review_id=review.id,
                kind=FileAssetKind.ANNOTATED_PNG,
                filename=path.name,
                data=data,
                expires_at=expires_at,
            )
            path_to_asset_id[path] = asset.id
        finding_screenshot[finding_id] = path_to_asset_id[path]

    if output.fixed_path is not None:
        fixed_data = await asyncio.to_thread(output.fixed_path.read_bytes)
        await upsert_fixed_pptx(
            session,
            storage,
            review_id=review.id,
            deck_filename=review.deck_filename,
            data=fixed_data,
            expire_days=settings.file_expire_days,
        )

    await save_file_asset(
        storage,
        session,
        review_id=review.id,
        kind=FileAssetKind.REPORT_PDF,
        filename="report.pdf",
        data=output.pdf_bytes,
        expires_at=expires_at,
    )

    for finding in review_ctx.findings:
        row = finding_to_row(finding, review_id=review.id)
        row.screenshot_asset_id = finding_screenshot.get(finding.id)
        session.add(row)

    delivery = review_ctx.step_results.get("delivery")
    review.delivery_metrics = delivery.model_dump(mode="json") if delivery is not None else None
    review.status = ReviewStatus.DONE.value
    review.score = output.report.score
    review.n_slides = output.report.n_slides
    review.finished_at = datetime.now(UTC)

    await EventTracker().track(
        session,
        review.user_id,
        "review_done",
        score=review.score,
        n_slides=review.n_slides,
        cost_rub=review_ctx.total_cost_rub,
    )

    observe_review_cost(review_ctx.total_cost_rub)
    observe_review_status(review.status)
    if review_ctx.total_cost_rub > settings.review_cost_alert_rub:
        logger.warning(
            "review.cost_alert",
            review_id=str(review.id),
            cost_rub=review_ctx.total_cost_rub,
            threshold_rub=settings.review_cost_alert_rub,
        )
        sentry_sdk.capture_message(
            f"Review {review.id} cost {review_ctx.total_cost_rub:.2f} RUB exceeds "
            f"the {settings.review_cost_alert_rub:.2f} RUB alert threshold",
            level="warning",
        )

    await session.commit()

    user = await session.get(User, review.user_id)
    if user is not None:
        await EmailService(settings).send_report_ready(user.email, review.id, review.score or 0)


async def _mark_failed(session: AsyncSession, review: Review, exc: Exception) -> None:
    logger.error(
        "process_review.failed",
        review_id=str(review.id),
        error_type=type(exc).__name__,
        error=str(exc),
    )
    sentry_sdk.capture_exception(exc)

    review.status = ReviewStatus.FAILED.value
    review.fail_reason = _fail_reason(exc)
    review.finished_at = datetime.now(UTC)
    await LimitService().refund(session, review.user_id, review.credit_source)
    await EventTracker().track(
        session, review.user_id, "review_failed", reason=type(exc).__name__
    )
    observe_review_status(review.status)
    await session.commit()


async def process_review(worker_ctx: dict[str, Any], review_id: str) -> None:
    """ARQ task: run the review pipeline end-to-end and persist the outcome."""
    settings: Settings = worker_ctx["settings"]
    session_factory: async_sessionmaker[AsyncSession] = worker_ctx["session_factory"]
    storage: StorageBackend = worker_ctx["storage"]

    async with session_factory() as session:
        review = await session.get(Review, UUID(review_id))
        if review is None:
            logger.error("process_review.review_not_found", review_id=review_id)
            return

        review.status = ReviewStatus.PROCESSING.value
        await session.commit()

        workdir = Path(settings.storage_root) / "tmp" / review_id
        try:
            try:
                review_ctx = await _download_inputs(session, review, storage, workdir)
                output = await _run_pipeline(review_ctx, settings)
            except Exception as exc:  # noqa: BLE001 - pipeline failure boundary, see design.md #6
                await _mark_failed(session, review, exc)
                return
            await _persist_success(session, review, output, storage, settings)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


async def _rehearsal_slide_texts(
    session: AsyncSession,
    review: Review,
    storage: StorageBackend,
    workdir: Path,
) -> dict[int, str]:
    """Re-ingest the still-retained original deck (no LLM cost) for its slide text."""
    result = await session.execute(
        select(FileAsset).where(
            FileAsset.review_id == review.id,
            FileAsset.kind == FileAssetKind.DECK_ORIGINAL.value,
        )
    )
    deck_asset = result.scalar_one_or_none()
    if deck_asset is None:
        raise CorruptedFileError(f"No deck_original FileAsset for review {review.id}")

    deck_bytes = await storage.open(deck_asset.storage_path)
    workdir.mkdir(parents=True, exist_ok=True)
    deck_path = workdir / Path(deck_asset.storage_path).name
    await asyncio.to_thread(deck_path.write_bytes, deck_bytes)

    ctx = ReviewContext(workdir=workdir, review_id=review.id)
    await DeckIngestor().ingest(deck_path, workdir, ctx)
    return ctx.meta.get("slide_texts", {})


async def _mark_rehearsal_failed(
    session: AsyncSession, rehearsal: Rehearsal, exc: Exception
) -> None:
    logger.error(
        "process_rehearsal.failed",
        rehearsal_id=str(rehearsal.id),
        error_type=type(exc).__name__,
        error=str(exc),
    )
    sentry_sdk.capture_exception(exc)
    rehearsal.status = RehearsalStatus.FAILED.value
    rehearsal.fail_reason = _fail_reason(exc)
    rehearsal.finished_at = datetime.now(UTC)
    await session.commit()


async def process_rehearsal(worker_ctx: dict[str, Any], rehearsal_id: str) -> None:
    """ARQ task: transcribe + precise cross-modal analysis for one rehearsal attempt (П2-П4).

    Unlike ``process_review``, only one LLM-calling step exists here (per-slide speech
    mismatch) and it's already isolated per slide inside ``analyze_rehearsal`` — a failure
    there is skipped, not fatal. Only deck/audio I/O failures fail the whole attempt.
    """
    settings: Settings = worker_ctx["settings"]
    session_factory: async_sessionmaker[AsyncSession] = worker_ctx["session_factory"]
    storage: StorageBackend = worker_ctx["storage"]

    async with session_factory() as session:
        rehearsal = await session.get(Rehearsal, UUID(rehearsal_id))
        if rehearsal is None:
            logger.error("process_rehearsal.not_found", rehearsal_id=rehearsal_id)
            return

        rehearsal.status = RehearsalStatus.PROCESSING.value
        await session.commit()

        workdir = Path(settings.storage_root) / "tmp" / f"rehearsal-{rehearsal_id}"
        try:
            try:
                review = await session.get(Review, rehearsal.review_id)
                if review is None:
                    raise CorruptedFileError(f"Review not found: {rehearsal.review_id}")

                slide_texts = await _rehearsal_slide_texts(session, review, storage, workdir)

                assert rehearsal.audio_path is not None
                audio_bytes = await storage.open(rehearsal.audio_path)
                audio_local = workdir / Path(rehearsal.audio_path).name
                await asyncio.to_thread(audio_local.write_bytes, audio_bytes)
                wav_path = await AudioExtractor().extract(audio_local, workdir)

                slide_timings = [
                    SlideTiming.model_validate(t) for t in (rehearsal.slide_timings or [])
                ]

                llm = LLMClient(_llm_config(settings))
                ctx = ReviewContext(workdir=workdir, review_id=review.id)
                try:
                    segments = await llm.transcribe_audio(wav_path, ctx=ctx)
                    delivery, findings = await analyze_rehearsal(
                        llm,
                        segments=segments,
                        slide_timings=slide_timings,
                        slide_texts=slide_texts,
                        ctx=ctx,
                    )
                finally:
                    await llm.aclose()
            except Exception as exc:  # noqa: BLE001 - pipeline failure boundary, see design.md #6
                await _mark_rehearsal_failed(session, rehearsal, exc)
                return

            rehearsal.status = RehearsalStatus.DONE.value
            rehearsal.delivery_metrics = delivery.model_dump(mode="json")
            rehearsal.findings = [f.model_dump(mode="json") for f in findings]
            rehearsal.finished_at = datetime.now(UTC)
            await session.commit()

            observe_review_cost(ctx.total_cost_rub)
            if ctx.total_cost_rub > settings.review_cost_alert_rub:
                logger.warning(
                    "rehearsal.cost_alert",
                    rehearsal_id=str(rehearsal.id),
                    cost_rub=ctx.total_cost_rub,
                    threshold_rub=settings.review_cost_alert_rub,
                )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


async def _startup(worker_ctx: dict[str, Any]) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
    worker_ctx["engine"] = engine
    worker_ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    worker_ctx["settings"] = settings
    worker_ctx["storage"] = LocalStorage(Path(settings.storage_root))


async def _shutdown(worker_ctx: dict[str, Any]) -> None:
    engine = worker_ctx.get("engine")
    if engine is not None:
        await engine.dispose()


class WorkerSettings:
    """``arq worker.tasks.WorkerSettings`` — process_review + the cleanup cron."""

    functions = [process_review, process_rehearsal, cleanup_expired_files]
    cron_jobs = [cron(cleanup_expired_files, hour=3, minute=0)]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 900
