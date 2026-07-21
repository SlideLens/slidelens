"""Rehearsal HTTP routes (П2-П4) — record a pitch attempt against a done Review's deck."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from arq import ArqRedis
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user, get_storage
from app.models import User
from app.queue import get_queue
from app.schemas.rehearsals import RehearsalOut, RehearsalReportOut, SlideTimingIn
from app.services import rehearsal_service
from app.services.downloads import content_disposition_headers
from app.services.exceptions import (
    RehearsalNotFoundError,
    RehearsalNotReadyError,
    RehearsalValidationError,
    ReviewNotFoundError,
    ReviewNotReadyError,
)
from app.services.storage import StorageBackend

router = APIRouter(tags=["rehearsals"])

_SlideTimingsAdapter = TypeAdapter(list[SlideTimingIn])

_RehearsalServiceError = (
    RehearsalNotFoundError
    | RehearsalNotReadyError
    | RehearsalValidationError
    | ReviewNotFoundError
    | ReviewNotReadyError
)


def _raise(exc: _RehearsalServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/reviews/{review_id}/rehearsals",
    response_model=RehearsalOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_rehearsal(
    review_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    queue: Annotated[ArqRedis, Depends(get_queue)],
    audio: Annotated[UploadFile, File()],
    slide_timings: Annotated[str, Form()],
) -> RehearsalOut:
    try:
        timings = _SlideTimingsAdapter.validate_json(slide_timings)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail="Некорректный формат тайминга слайдов"
        ) from exc

    try:
        rehearsal = await rehearsal_service.create_rehearsal(
            session,
            user=user,
            review_id=review_id,
            audio=audio,
            slide_timings=timings,
            storage=storage,
            queue=queue,
        )
    except (RehearsalValidationError, ReviewNotFoundError, ReviewNotReadyError) as exc:
        _raise(exc)
        raise  # pragma: no cover
    return RehearsalOut.model_validate(rehearsal)


@router.get("/reviews/{review_id}/rehearsals", response_model=list[RehearsalOut])
async def list_rehearsals(
    review_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[RehearsalOut]:
    try:
        rehearsals = await rehearsal_service.list_rehearsals(session, user, review_id)
    except ReviewNotFoundError as exc:
        _raise(exc)
        raise  # pragma: no cover
    return [RehearsalOut.model_validate(r) for r in rehearsals]


@router.get("/rehearsals/{rehearsal_id}", response_model=RehearsalOut)
async def get_rehearsal(
    rehearsal_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RehearsalOut:
    try:
        rehearsal = await rehearsal_service.get_rehearsal(session, user, rehearsal_id)
    except RehearsalNotFoundError as exc:
        _raise(exc)
        raise  # pragma: no cover
    return RehearsalOut.model_validate(rehearsal)


@router.get("/rehearsals/{rehearsal_id}/report", response_model=RehearsalReportOut)
async def get_rehearsal_report(
    rehearsal_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RehearsalReportOut:
    try:
        return await rehearsal_service.get_rehearsal_report(session, user, rehearsal_id)
    except (RehearsalNotFoundError, RehearsalNotReadyError) as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.get("/rehearsals/{rehearsal_id}/audio")
async def get_rehearsal_audio(
    rehearsal_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> Response:
    try:
        data, storage_path = await rehearsal_service.get_rehearsal_audio(
            session, user, rehearsal_id, storage
        )
    except RehearsalNotFoundError as exc:
        _raise(exc)
        raise  # pragma: no cover
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers=content_disposition_headers(storage_path),
    )


@router.delete("/rehearsals/{rehearsal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rehearsal(
    rehearsal_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> None:
    try:
        await rehearsal_service.delete_rehearsal(session, user, rehearsal_id, storage)
    except RehearsalNotFoundError as exc:
        _raise(exc)
        raise  # pragma: no cover
