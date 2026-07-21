"""Findings HTTP routes under ``/api/v1/findings``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user, get_storage
from app.models import User
from app.services import finding_service
from app.services.exceptions import FindingNotFoundError
from app.services.storage import StorageBackend

router = APIRouter(prefix="/findings", tags=["findings"])


@router.post("/{finding_id}/flag", status_code=status.HTTP_204_NO_CONTENT)
async def flag_finding(
    finding_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    try:
        await finding_service.flag_finding(session, user, finding_id, settings)
    except FindingNotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{finding_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_finding(
    finding_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    try:
        await finding_service.like_finding(session, user, finding_id, settings)
    except FindingNotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{finding_id}/apply_fix", status_code=status.HTTP_204_NO_CONTENT)
async def apply_finding_fix(
    finding_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    try:
        await finding_service.apply_finding_fix(
            session, user, finding_id, storage, settings
        )
    except FindingNotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
