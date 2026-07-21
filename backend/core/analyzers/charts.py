"""``ChartChecker`` — chart honesty checks for slides flagged ``has_chart``.

Structured chart reading is one VLM call (``ChartReading``); axis/pie/Excel
checks are deterministic code, not the model, per ADR 0002 / docs/PROMPTS.md §4.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import openpyxl

from core.analyzers.base import BaseAnalyzer
from core.analyzers.schemas import LabelConsistencyResponse, SlideFindingIn
from core.constants import (
    AXIS_MANIPULATION_RATIO_THRESHOLD,
    EXCEL_VALUE_RELATIVE_TOLERANCE,
    PIE_SUM_TOLERANCE,
)
from core.context import ReviewContext
from core.llm import LLMClient, PromptRegistry, default_registry
from core.schemas import Category, ChartReading, Finding, Severity


def _check_truncated_axis(reading: ChartReading) -> SlideFindingIn | None:
    if reading.y_axis_starts_at_zero:
        return None
    values = [v for series in reading.series for v in series.values if v > 0]
    if len(values) < 2:
        return None
    ratio = max(values) / min(values)
    if ratio >= AXIS_MANIPULATION_RATIO_THRESHOLD:
        return None
    return SlideFindingIn(
        category=Category.CHART,
        severity=Severity.MAJOR,
        title="Обрезанная ось Y",
        description=(
            f"Ось Y не начинается с нуля при разбросе значений менее "
            f"{AXIS_MANIPULATION_RATIO_THRESHOLD:.0f}×, что визуально преувеличивает разницу."
        ),
        fix_suggestion="Начать ось Y с нуля или явно указать разрыв оси.",
    )


def _check_pie_sum(reading: ChartReading) -> SlideFindingIn | None:
    if reading.chart_type.strip().lower() != "pie":
        return None
    total = sum(v for series in reading.series for v in series.values)
    if abs(total - 100) <= PIE_SUM_TOLERANCE:
        return None
    return SlideFindingIn(
        category=Category.CHART,
        severity=Severity.MAJOR,
        title="Доли круговой диаграммы не суммируются в 100%",
        description=f"Сумма долей равна {total:.1f}%, что отклоняется от 100%.",
        fix_suggestion="Проверить и скорректировать значения долей диаграммы.",
    )


def load_excel_values(xlsx_path: Path) -> set[float]:
    workbook = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    values: set[float] = set()
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, int | float) and not isinstance(cell, bool):
                    values.add(round(float(cell), 6))
    return values


def _check_against_excel(reading: ChartReading, excel_values: set[float]) -> SlideFindingIn | None:
    chart_values = [v for series in reading.series for v in series.values]
    if not chart_values or not excel_values:
        return None
    def _matches(value: float, cell: float) -> bool:
        tolerance = max(EXCEL_VALUE_RELATIVE_TOLERANCE, abs(cell) * EXCEL_VALUE_RELATIVE_TOLERANCE)
        return abs(value - cell) <= tolerance

    unmatched = [
        value for value in chart_values if not any(_matches(value, cell) for cell in excel_values)
    ]
    if not unmatched:
        return None
    return SlideFindingIn(
        category=Category.CHART,
        severity=Severity.MAJOR,
        title="Данные графика не подтверждаются Excel",
        description=f"Значения графика {unmatched} не найдены в приложенном файле данных.",
        fix_suggestion="Сверить значения графика с источником и исправить расхождения.",
    )


class ChartChecker(BaseAnalyzer):
    """Reads has_chart slides into ``ChartReading``, runs honesty checks."""

    name = "chart_checker"

    def __init__(self, llm: LLMClient, *, prompts: PromptRegistry | None = None) -> None:
        self._llm = llm
        self._prompts = prompts or default_registry()

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        has_chart = ctx.meta.get("has_chart", {})
        chart_slides = sorted(n for n, flag in has_chart.items() if flag)
        if not chart_slides:
            return []

        excel_values = load_excel_values(ctx.xlsx_path) if ctx.xlsx_path else None
        results = await asyncio.gather(
            *(self._check_slide(ctx, slide_num, excel_values) for slide_num in chart_slides)
        )
        return [finding for slide_findings in results for finding in slide_findings]

    async def _check_slide(
        self, ctx: ReviewContext, slide_num: int, excel_values: set[float] | None
    ) -> list[Finding]:
        png = ctx.slide_png(slide_num)
        reading = await self._read_chart(ctx, png, slide_num)

        candidates: list[SlideFindingIn] = []
        for check in (_check_truncated_axis, _check_pie_sum):
            finding = check(reading)
            if finding is not None:
                candidates.append(finding)
        if excel_values is not None:
            excel_finding = _check_against_excel(reading, excel_values)
            if excel_finding is not None:
                candidates.append(excel_finding)

        label_finding = await self._check_label_consistency(ctx, reading, slide_num)
        if label_finding is not None:
            candidates.append(label_finding)

        return [
            Finding.model_validate({**c.as_finding_fields(), "slide_num": slide_num})
            for c in candidates
        ]

    async def _read_chart(self, ctx: ReviewContext, png: Path, slide_num: int) -> ChartReading:
        system_prompt = self._prompts.get("chart_reading").body
        return await self._llm.complete_vision_structured(
            [png],
            f"Слайд {slide_num}.",
            ChartReading,
            system=system_prompt,
            tier="full",
            ctx=ctx,
        )

    async def _check_label_consistency(
        self, ctx: ReviewContext, reading: ChartReading, slide_num: int
    ) -> SlideFindingIn | None:
        slide_text = ctx.meta.get("slide_texts", {}).get(slide_num) or ""
        if not slide_text.strip():
            return None

        system_prompt = self._prompts.get("chart_label_check").body
        chart_json = reading.model_dump_json()
        prompt = f"Текст слайда:\n{slide_text}\n\nДанные графика (JSON):\n{chart_json}"
        response = await self._llm.complete_structured(
            prompt,
            LabelConsistencyResponse,
            system=system_prompt,
            tier="full",
            ctx=ctx,
        )
        return response.finding if response.contradicts else None
