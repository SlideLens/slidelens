"""``DeckAnalyzer`` — contact sheet + all slide texts → cross-slide findings.

Catches what a per-slide pass structurally cannot: font/color drift, narrative
gaps, duplicate slides. Findings are deck-level (``slide_num=None``) or
slide-attributed, exactly as the model returns them.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from core.analyzers.base import BaseAnalyzer
from core.analyzers.schemas import DeckAnalysisResponse
from core.constants import (
    CONTACT_SHEET_GRID_COLUMNS,
    CONTACT_SHEET_MAX_IMAGES,
    CONTACT_SHEET_MAX_SLIDES_PER_SHEET,
    CONTACT_SHEET_THUMBNAIL_SIZE,
)
from core.context import ReviewContext
from core.llm import LLMClient, PromptRegistry, default_registry
from core.schemas import Finding


def _split_into_groups(items: list[int], max_groups: int, max_per_group: int) -> list[list[int]]:
    n_groups = min(max_groups, math.ceil(len(items) / max_per_group)) or 1
    chunk_size = math.ceil(len(items) / n_groups)
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


class DeckAnalyzer(BaseAnalyzer):
    """One VLM call over a contact sheet (≤ 2 images) + all slide texts."""

    name = "deck_analyzer"

    def __init__(
        self,
        llm: LLMClient,
        *,
        prompts: PromptRegistry | None = None,
        max_sheets: int = CONTACT_SHEET_MAX_IMAGES,
        max_slides_per_sheet: int = CONTACT_SHEET_MAX_SLIDES_PER_SHEET,
        thumbnail_size: tuple[int, int] = CONTACT_SHEET_THUMBNAIL_SIZE,
        grid_columns: int = CONTACT_SHEET_GRID_COLUMNS,
    ) -> None:
        self._llm = llm
        self._prompts = prompts or default_registry()
        self._max_sheets = max_sheets
        self._max_slides_per_sheet = max_slides_per_sheet
        self._thumbnail_size = thumbnail_size
        self._grid_columns = grid_columns

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        slide_nums = sorted(ctx.slide_pngs.keys())
        if not slide_nums:
            return []

        sheets = self._build_contact_sheets(ctx, slide_nums)
        texts = ctx.meta.get("slide_texts", {})
        texts_blob = "\n".join(f"Слайд {n}: {texts.get(n, '')}" for n in slide_nums)
        system_prompt = self._prompts.get("deck_analysis").body
        user_prompt = f"Тексты слайдов:\n{texts_blob}"

        response = await self._llm.complete_vision_structured(
            sheets,
            user_prompt,
            DeckAnalysisResponse,
            system=system_prompt,
            tier="full",
            ctx=ctx,
        )
        return [Finding.model_validate(item.model_dump()) for item in response.findings]  # bbox нет

    def _build_contact_sheets(self, ctx: ReviewContext, slide_nums: list[int]) -> list[Path]:
        groups = _split_into_groups(slide_nums, self._max_sheets, self._max_slides_per_sheet)
        sheets: list[Path] = []
        for index, group in enumerate(groups, start=1):
            sheet_path = ctx.workdir / f"contact_sheet_{index:02d}.png"
            self._render_grid(ctx, group, sheet_path)
            sheets.append(sheet_path)
        return sheets

    def _render_grid(self, ctx: ReviewContext, slide_nums: list[int], out_path: Path) -> None:
        tw, th = self._thumbnail_size
        thumbnails = []
        for slide_num in slide_nums:
            with Image.open(ctx.slide_png(slide_num)) as image:
                thumbnails.append(image.convert("RGB").resize((tw, th)))

        columns = self._grid_columns
        rows = math.ceil(len(thumbnails) / columns)
        sheet = Image.new("RGB", (tw * columns, th * rows), "white")
        for idx, thumbnail in enumerate(thumbnails):
            x = (idx % columns) * tw
            y = (idx // columns) * th
            sheet.paste(thumbnail, (x, y))
        sheet.save(out_path, "PNG")
