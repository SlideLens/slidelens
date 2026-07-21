"""``SlideAnalyzer`` — per-slide hierarchy/typography/readability pass.

PNG + extracted text are sent together (the model reads small text poorly
from the image alone); ``has_chart`` feeds Я4's ``ChartChecker``.
"""

from __future__ import annotations

import asyncio

from core.analyzers.base import BaseAnalyzer
from core.analyzers.schemas import SlideAnalysisResponse
from core.context import ReviewContext
from core.llm import LLMClient, PromptRegistry, default_registry
from core.schemas import Finding

_NO_TEXT_PLACEHOLDER = "(текст слайда не извлечён)"


class SlideAnalyzer(BaseAnalyzer):
    """Per-slide VLM pass, ``asyncio.Semaphore(4)``-bounded."""

    name = "slide_analyzer"

    def __init__(
        self,
        llm: LLMClient,
        *,
        prompts: PromptRegistry | None = None,
        concurrency: int = 4,
    ) -> None:
        self._llm = llm
        self._prompts = prompts or default_registry()
        self._semaphore = asyncio.Semaphore(concurrency)

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        slide_nums = sorted(ctx.slide_pngs.keys())
        results = await asyncio.gather(
            *(self._analyze_slide(ctx, slide_num) for slide_num in slide_nums)
        )

        findings: list[Finding] = []
        has_chart_by_slide: dict[int, bool] = {}
        for slide_num, slide_findings, has_chart in results:
            findings.extend(slide_findings)
            has_chart_by_slide[slide_num] = has_chart

        if has_chart_by_slide:
            ctx.meta.setdefault("has_chart", {}).update(has_chart_by_slide)
        return findings

    async def _analyze_slide(
        self, ctx: ReviewContext, slide_num: int
    ) -> tuple[int, list[Finding], bool]:
        async with self._semaphore:
            png = ctx.slide_png(slide_num)
            slide_text = ctx.meta.get("slide_texts", {}).get(slide_num) or _NO_TEXT_PLACEHOLDER
            system_prompt = self._prompts.get("slide_analysis").body
            user_prompt = f"Текст слайда:\n{slide_text}"

            response = await self._llm.complete_vision_structured(
                [png],
                user_prompt,
                SlideAnalysisResponse,
                system=system_prompt,
                tier="full",
                ctx=ctx,
            )

        findings = [
            Finding.model_validate({**item.as_finding_fields(), "slide_num": slide_num})
            for item in response.findings
        ]
        return slide_num, findings, response.has_chart
