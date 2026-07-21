"""Findings domain logic: 👎/👍 votes and point-apply autofix."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import FileAsset, FileAssetKind, FindingRow, Review, User
from app.services.exceptions import FindingNotFoundError
from app.services.file_assets import save_file_asset
from app.services.finding_mapper import row_to_finding
from app.services.langfuse_scoring import score_finding_flag, score_finding_like
from app.services.storage import StorageBackend
from core.fix import PptxFixer, fixed_deck_filename


async def _load_owned_finding(
    session: AsyncSession,
    user: User,
    finding_id: UUID,
) -> tuple[FindingRow, Review]:
    result = await session.execute(
        select(FindingRow, Review)
        .join(Review, Review.id == FindingRow.review_id)
        .where(FindingRow.id == finding_id, Review.user_id == user.id)
    )
    row = result.first()
    if row is None:
        raise FindingNotFoundError()
    return row[0], row[1]


async def flag_finding(
    session: AsyncSession,
    user: User,
    finding_id: UUID,
    settings: Settings,
) -> None:
    finding, review = await _load_owned_finding(session, user, finding_id)
    finding.user_flag = True
    finding.user_like = False
    await session.commit()

    score_finding_flag(
        settings,
        finding_id=finding.id,
        review_id=review.id,
        category=finding.category,
        source=finding.source,
    )


async def like_finding(
    session: AsyncSession,
    user: User,
    finding_id: UUID,
    settings: Settings,
) -> None:
    finding, review = await _load_owned_finding(session, user, finding_id)
    finding.user_like = True
    finding.user_flag = False
    await session.commit()

    score_finding_like(
        settings,
        finding_id=finding.id,
        review_id=review.id,
        category=finding.category,
        source=finding.source,
    )


async def apply_finding_fix(
    session: AsyncSession,
    user: User,
    finding_id: UUID,
    storage: StorageBackend,
    settings: Settings,
) -> None:
    """Regenerate ``fixed.pptx`` from the original using the applied-finding set.

    The set is all findings with ``auto_fixed=True`` plus this finding (idempotent
    if it was already applied). Always starts from ``deck_original``, never
    patches an already-edited file.
    """
    finding, review = await _load_owned_finding(session, user, finding_id)
    if not finding.auto_fixable:
        raise FindingNotFoundError()

    if finding.auto_fixed:
        return

    original = await session.execute(
        select(FileAsset).where(
            FileAsset.review_id == review.id,
            FileAsset.kind == FileAssetKind.DECK_ORIGINAL.value,
        )
    )
    original_asset = original.scalar_one_or_none()
    if original_asset is None or not original_asset.storage_path.lower().endswith(".pptx"):
        raise FindingNotFoundError()

    siblings = await session.execute(
        select(FindingRow).where(FindingRow.review_id == review.id)
    )
    rows = list(siblings.scalars().all())
    selected_rows = [row for row in rows if row.auto_fixed or row.id == finding.id]
    pipeline_findings = [row_to_finding(row) for row in selected_rows]

    original_bytes = await storage.open(original_asset.storage_path)

    with tempfile.TemporaryDirectory(prefix="slidelens-apply-") as tmp:
        workdir = Path(tmp)
        original_path = workdir / Path(original_asset.storage_path).name
        await asyncio.to_thread(original_path.write_bytes, original_bytes)
        fixed_path = await asyncio.to_thread(
            PptxFixer().fix,
            original_path,
            pipeline_findings,
            out_dir=workdir,
        )
        fixed_bytes = await asyncio.to_thread(fixed_path.read_bytes)

    id_to_row = {row.id: row for row in selected_rows}
    for pipeline_finding in pipeline_findings:
        row = id_to_row.get(pipeline_finding.id)
        if row is not None:
            row.auto_fixed = pipeline_finding.auto_fixed

    await upsert_fixed_pptx(
        session,
        storage,
        review_id=review.id,
        deck_filename=review.deck_filename,
        data=fixed_bytes,
        expire_days=settings.file_expire_days,
    )
    await session.commit()


async def upsert_fixed_pptx(
    session: AsyncSession,
    storage: StorageBackend,
    *,
    review_id: UUID,
    deck_filename: str,
    data: bytes,
    expire_days: int,
) -> FileAsset:
    """Create or replace the review's single Исправленная дека, bumping ``version``.

    Regenerated from scratch each call (never patches the previous file), so the
    public filename always reflects the current version number.
    """
    result = await session.execute(
        select(FileAsset).where(
            FileAsset.review_id == review_id,
            FileAsset.kind == FileAssetKind.FIXED_PPTX.value,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return await save_file_asset(
            storage,
            session,
            review_id=review_id,
            kind=FileAssetKind.FIXED_PPTX,
            filename=fixed_deck_filename(deck_filename, 1),
            data=data,
            expires_at=datetime.now(UTC) + timedelta(days=expire_days),
            version=1,
        )

    new_version = existing.version + 1
    existing.storage_path = await storage.save(
        review_id, existing.id, fixed_deck_filename(deck_filename, new_version), data
    )
    existing.size_bytes = len(data)
    existing.version = new_version
    return existing
