"""Files HTTP routes under ``/api/v1/files``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user_optional, get_storage
from app.models import FileAsset, Review, User
from app.security import decode_file_token
from app.services.downloads import content_disposition_headers
from app.services.storage import StorageBackend

router = APIRouter(prefix="/files", tags=["files"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
_BAD_SIGNATURE = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Ссылка недействительна или истекла"
)


@router.get("/{asset_id}")
async def get_file(
    asset_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[StorageBackend, Depends(get_storage)],
    user: Annotated[User | None, Depends(get_current_user_optional)],
    sig: str | None = None,
) -> Response:
    result = await session.execute(
        select(FileAsset).where(
            FileAsset.id == asset_id, FileAsset.expires_at >= datetime.now(UTC)
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise _NOT_FOUND

    if sig is not None:
        try:
            signed_asset_id = decode_file_token(sig, settings)
        except ValueError as exc:
            raise _BAD_SIGNATURE from exc
        if signed_asset_id != asset_id:
            raise _BAD_SIGNATURE
    else:
        review = await session.get(Review, asset.review_id)
        if review is None or user is None or user.id != review.user_id:
            raise _NOT_FOUND

    data = await storage.open(asset.storage_path)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers=content_disposition_headers(asset.storage_path),
    )
