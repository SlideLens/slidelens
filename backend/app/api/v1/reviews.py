"""Reviews HTTP routes under ``/api/v1/reviews``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from arq import ArqRedis
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user, get_event_tracker, get_storage
from app.models import User
from app.queue import get_queue
from app.schemas.reviews import ReportOut, ReviewOut, SlideOut
from app.services import review_service
from app.services.events import EventTracker
from app.services.exceptions import (
    LimitExceededError,
    ReviewNotFoundError,
    ReviewNotReadyError,
    ReviewTooLargeError,
    ReviewValidationError,
)
from app.services.storage import StorageBackend

router = APIRouter(prefix="/reviews", tags=["reviews"])

_ReviewServiceError = (
    LimitExceededError
    | ReviewNotFoundError
    | ReviewNotReadyError
    | ReviewTooLargeError
    | ReviewValidationError
)


def _raise_review(exc: _ReviewServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[ReviewOut])
async def list_reviews(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ReviewOut]:
    reviews = await review_service.list_reviews(session, user)
    return [ReviewOut.model_validate(review) for review in reviews]


@router.post("", response_model=ReviewOut, status_code=status.HTTP_202_ACCEPTED)
async def create_review(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    queue: Annotated[ArqRedis, Depends(get_queue)],
    event_tracker: Annotated[EventTracker, Depends(get_event_tracker)],
    deck: Annotated[UploadFile, File()],
    audio: Annotated[UploadFile | None, File()] = None,
    data: Annotated[UploadFile | None, File()] = None,
) -> ReviewOut:
    try:
        review = await review_service.create_review(
            session,
            user=user,
            deck=deck,
            audio=audio,
            data=data,
            storage=storage,
            queue=queue,
            settings=settings,
            event_tracker=event_tracker,
        )
    except (LimitExceededError, ReviewTooLargeError, ReviewValidationError) as exc:
        _raise_review(exc)
        raise  # pragma: no cover
    return ReviewOut.model_validate(review)


@router.get("/{review_id}", response_model=ReviewOut)
async def get_review(
    review_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewOut:
    try:
        review = await review_service.get_review(session, user, review_id)
    except ReviewNotFoundError as exc:
        _raise_review(exc)
        raise  # pragma: no cover
    return ReviewOut.model_validate(review)


@router.get("/{review_id}/report", response_model=ReportOut)
async def get_report(
    review_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReportOut:
    try:
        return await review_service.get_report(session, user, review_id, settings)
    except (ReviewNotFoundError, ReviewNotReadyError) as exc:
        _raise_review(exc)
        raise  # pragma: no cover


@router.get("/{review_id}/slides", response_model=list[SlideOut])
async def get_slides(
    review_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> list[SlideOut]:
    try:
        return await review_service.get_slides(session, user, review_id, storage, settings)
    except (ReviewNotFoundError, ReviewNotReadyError) as exc:
        _raise_review(exc)
        raise  # pragma: no cover


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
) -> None:
    try:
        await review_service.delete_review(session, user, review_id, storage)
    except ReviewNotFoundError as exc:
        _raise_review(exc)
        raise  # pragma: no cover
