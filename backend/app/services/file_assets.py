"""Shared ``FileAsset`` creation helper (Storage write + DB row)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FileAsset, FileAssetKind
from app.services.storage import StorageBackend


async def save_file_asset(
    storage: StorageBackend,
    session: AsyncSession,
    *,
    review_id: UUID,
    kind: FileAssetKind,
    filename: str,
    data: bytes,
    expires_at: datetime,
    version: int = 1,
) -> FileAsset:
    """Insert a ``FileAsset`` row (for its id) then write bytes under it."""
    asset = FileAsset(
        review_id=review_id,
        kind=kind.value,
        storage_path="",
        size_bytes=len(data),
        version=version,
        expires_at=expires_at,
    )
    session.add(asset)
    await session.flush()
    asset.storage_path = await storage.save(review_id, asset.id, filename, data)
    return asset
