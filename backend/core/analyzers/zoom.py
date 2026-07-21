"""``ZoomAgent`` — cheap screening → crop ×2 → full re-analysis.

Raises recall on small text/tables that the fixed-resolution ``SlideAnalyzer``
pass misses, capped at 3 zooms/slide for cost (ADR 0002).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image

from core.analyzers.base import BaseAnalyzer
from core.analyzers.schemas import ScreeningResponse, SlideAnalysisResponse, SuspiciousRegionIn
from core.constants import (
    DEDUP_IOU_THRESHOLD,
    MAX_ZOOMS_PER_SLIDE,
    ZOOM_UPSCALE_FACTOR,
)
from core.context import ReviewContext
from core.geometry import iou, project_into
from core.llm import LLMClient, PromptRegistry, default_registry
from core.schemas import BBox, Finding


def _is_duplicate(finding: Finding, existing: list[Finding], threshold: float) -> bool:
    if finding.bbox is None:
        return False
    for other in existing:
        if other.bbox is None:
            continue
        if iou(finding.bbox, other.bbox) > threshold:
            return True
    return False


class ZoomAgent(BaseAnalyzer):
    """Screening (cheap) → crop + upscale ×2 → full re-analysis, capped 3/slide."""

    name = "zoom_agent"

    def __init__(
        self,
        llm: LLMClient,
        *,
        prompts: PromptRegistry | None = None,
        max_zooms_per_slide: int = MAX_ZOOMS_PER_SLIDE,
        upscale_factor: int = ZOOM_UPSCALE_FACTOR,
        dedup_iou_threshold: float = DEDUP_IOU_THRESHOLD,
    ) -> None:
        self._llm = llm
        self._prompts = prompts or default_registry()
        self._max_zooms_per_slide = max_zooms_per_slide
        self._upscale_factor = upscale_factor
        self._dedup_iou_threshold = dedup_iou_threshold

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        slide_nums = sorted(ctx.slide_pngs.keys())
        results = await asyncio.gather(*(self._process_slide(ctx, n) for n in slide_nums))
        return [finding for slide_findings in results for finding in slide_findings]

    async def _process_slide(self, ctx: ReviewContext, slide_num: int) -> list[Finding]:
        png = ctx.slide_png(slide_num)
        regions = await self._screen(ctx, png, slide_num)
        regions = regions[: self._max_zooms_per_slide]

        existing = [f for f in ctx.findings if f.slide_num == slide_num]
        accepted: list[Finding] = []
        for index, region in enumerate(regions, start=1):
            region_bbox = region.as_bbox()
            if region_bbox is None:
                # Кроп во весь слайд — это просто повтор обычного прохода, толку нет.
                continue
            crop_path, crop_bbox = self._crop_and_upscale(
                png, region_bbox, ctx.workdir, slide_num, index
            )
            zoom_findings = await self._analyze_zoom(ctx, crop_path, slide_num)
            for finding in zoom_findings:
                # Модель видела только кроп и меряла от его угла — переносим рамку
                # в координаты слайда, иначе она укажет не туда (и дедуп ниже
                # сравнивал бы несопоставимые системы координат).
                if finding.bbox is not None:
                    finding = finding.model_copy(
                        update={"bbox": project_into(crop_bbox, finding.bbox)}
                    )
                if _is_duplicate(finding, existing + accepted, self._dedup_iou_threshold):
                    continue
                accepted.append(finding)
        return accepted

    async def _screen(
        self, ctx: ReviewContext, png: Path, slide_num: int
    ) -> list[SuspiciousRegionIn]:
        system_prompt = self._prompts.get("zoom_screening").body
        response = await self._llm.complete_vision_structured(
            [png],
            f"Слайд {slide_num}.",
            ScreeningResponse,
            system=system_prompt,
            tier="screening",
            ctx=ctx,
        )
        return response.regions

    def _crop_and_upscale(
        self, png: Path, bbox: BBox, workdir: Path, slide_num: int, index: int
    ) -> tuple[Path, BBox]:
        """Кроп ×N плюс область, которую он реально накрыл (нормированная, для переноса рамок)."""
        with Image.open(png) as image:
            width, height = image.size
            left = max(0, min(width, round(bbox.x * width)))
            top = max(0, min(height, round(bbox.y * height)))
            right = max(0, min(width, round((bbox.x + bbox.w) * width)))
            bottom = max(0, min(height, round((bbox.y + bbox.h) * height)))
            if right <= left or bottom <= top:
                left, top, right, bottom = 0, 0, width, height

            cropped = image.convert("RGB").crop((left, top, right, bottom))
            upscaled = cropped.resize(
                (
                    max(1, cropped.width * self._upscale_factor),
                    max(1, cropped.height * self._upscale_factor),
                ),
                Image.LANCZOS,
            )
            out_path = workdir / f"slide_{slide_num:03d}_zoom_{index:02d}.png"
            upscaled.save(out_path, "PNG")
            # Именно фактические границы после клампа/фолбэка, а не запрошенный
            # bbox — по ним потом переносятся рамки Находок.
            actual = BBox(
                x=left / width,
                y=top / height,
                w=(right - left) / width,
                h=(bottom - top) / height,
            )
            return out_path, actual

    async def _analyze_zoom(
        self, ctx: ReviewContext, crop_path: Path, slide_num: int
    ) -> list[Finding]:
        system_prompt = self._prompts.get("slide_analysis").body
        response = await self._llm.complete_vision_structured(
            [crop_path],
            "Увеличенный фрагмент слайда для детального анализа. "
            "bbox указывай относительно ЭТОГО фрагмента (0..1 от его ширины и высоты), "
            "а не всего слайда — пересчёт в координаты слайда сделаем сами.",
            SlideAnalysisResponse,
            system=system_prompt,
            tier="full",
            ctx=ctx,
        )
        return [
            Finding.model_validate({**item.as_finding_fields(), "slide_num": slide_num})
            for item in response.findings
        ]
