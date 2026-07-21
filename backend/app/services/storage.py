"""File storage backends (LocalStorage for MVP; S3 later)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FileAsset


class StorageBackend(ABC):
    """Abstract storage for review file assets."""

    @abstractmethod
    async def save(
        self,
        review_id: UUID,
        asset_id: UUID,
        filename: str,
        data: bytes,
    ) -> str:
        """Persist bytes; return relative ``storage_path`` for DB."""

    @abstractmethod
    async def open(self, storage_path: str) -> bytes:
        """Read file bytes by relative storage path."""

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Delete one file by relative storage path (no-op if already gone)."""

    @abstractmethod
    async def url(self, storage_path: str, *, expires_seconds: int = 3600) -> str:
        """Return a URL or local path suitable for serving (MVP: file path)."""

    @abstractmethod
    async def delete_expired(self, session: AsyncSession, *, now: datetime | None = None) -> int:
        """Delete expired FileAsset rows and their files; return count removed."""


class LocalStorage(StorageBackend):
    """Filesystem storage under ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _absolute(self, storage_path: str) -> Path:
        path = (self.root / storage_path).resolve()
        if not str(path).startswith(str(self.root)):
            msg = "Invalid storage path"
            raise ValueError(msg)
        return path

    async def save(
        self,
        review_id: UUID,
        asset_id: UUID,
        filename: str,
        data: bytes,
    ) -> str:
        safe_name = Path(filename).name
        relative = f"{review_id}/{asset_id}_{safe_name}"
        absolute = self._absolute(relative)
        absolute.parent.mkdir(parents=True, exist_ok=True)

        def _write() -> None:
            absolute.write_bytes(data)

        await asyncio.to_thread(_write)
        return relative

    async def open(self, storage_path: str) -> bytes:
        absolute = self._absolute(storage_path)

        def _read() -> bytes:
            return absolute.read_bytes()

        return await asyncio.to_thread(_read)

    async def delete(self, storage_path: str) -> None:
        absolute = self._absolute(storage_path)

        def _unlink() -> None:
            absolute.unlink(missing_ok=True)

        await asyncio.to_thread(_unlink)

    async def url(self, storage_path: str, *, expires_seconds: int = 3600) -> str:
        del expires_seconds  # local paths are not signed in MVP
        return str(self._absolute(storage_path))

    async def delete_expired(self, session: AsyncSession, *, now: datetime | None = None) -> int:
        cutoff = now or datetime.now(UTC)
        result = await session.execute(select(FileAsset).where(FileAsset.expires_at < cutoff))
        assets = list(result.scalars().all())
        removed = 0
        for asset in assets:
            absolute = self.root / asset.storage_path
            if absolute.is_file():

                def _unlink(p: Path = absolute) -> None:
                    p.unlink(missing_ok=True)

                await asyncio.to_thread(_unlink)
            await session.delete(asset)
            removed += 1
        await session.flush()
        return removed


class S3Storage(StorageBackend):
    """Placeholder for phase-2 object storage."""

    def __init__(self) -> None:
        msg = "S3Storage is not implemented in MVP"
        raise NotImplementedError(msg)

    async def save(
        self,
        review_id: UUID,
        asset_id: UUID,
        filename: str,
        data: bytes,
    ) -> str:
        raise NotImplementedError

    async def open(self, storage_path: str) -> bytes:
        raise NotImplementedError

    async def delete(self, storage_path: str) -> None:
        raise NotImplementedError

    async def url(self, storage_path: str, *, expires_seconds: int = 3600) -> str:
        raise NotImplementedError

    async def delete_expired(self, session: AsyncSession, *, now: datetime | None = None) -> int:
        raise NotImplementedError
