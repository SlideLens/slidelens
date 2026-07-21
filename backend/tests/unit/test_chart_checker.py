"""Unit tests for ``core.analyzers.charts.ChartChecker``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl
import pytest
from PIL import Image

from core.analyzers.charts import ChartChecker
from core.analyzers.schemas import LabelConsistencyResponse
from core.context import ReviewContext
from core.schemas import ChartReading


class _FakeChartLLM:
    def __init__(
        self,
        *,
        readings: dict[int, dict[str, Any]] | None = None,
        label_response: dict[str, Any] | None = None,
    ) -> None:
        self._readings = readings or {}
        self._label_response = label_response or {"contradicts": False}
        self.vision_calls: list[int] = []
        self.structured_calls: int = 0

    async def complete_vision_structured(
        self,
        images: list[Path],
        prompt: str,
        response_model: type[Any],
        *,
        system: str | None = None,
        tier: str = "full",
        prompt_version: str | None = None,
        ctx: ReviewContext | None = None,
    ) -> Any:
        slide_num = int(Path(images[0]).stem.split("_")[1])
        self.vision_calls.append(slide_num)
        payload = self._readings.get(
            slide_num,
            {
                "chart_type": "bar",
                "y_axis_starts_at_zero": True,
                "series": [],
                "value_labels_present": False,
            },
        )
        return response_model.model_validate(payload)

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[Any],
        *,
        system: str | None = None,
        tier: str = "full",
        prompt_version: str | None = None,
        ctx: ReviewContext | None = None,
    ) -> Any:
        self.structured_calls += 1
        return response_model.model_validate(self._label_response)


def _ctx_with_chart_slide(
    tmp_path: Path, slide_num: int = 1, *, text: str | None = None
) -> ReviewContext:
    ctx = ReviewContext(workdir=tmp_path)
    png = tmp_path / f"slide_{slide_num:03d}.png"
    Image.new("RGB", (100, 75), "white").save(png, "PNG")
    ctx.slide_pngs[slide_num] = png
    ctx.meta["has_chart"] = {slide_num: True}
    if text is not None:
        ctx.meta["slide_texts"] = {slide_num: text}
    return ctx


@pytest.mark.asyncio
async def test_no_chart_slides_makes_no_calls(tmp_path: Path) -> None:
    ctx = ReviewContext(workdir=tmp_path)
    ctx.meta["has_chart"] = {1: False}
    fake_llm = _FakeChartLLM()

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert findings == []
    assert fake_llm.vision_calls == []
    assert fake_llm.structured_calls == 0


@pytest.mark.asyncio
async def test_truncated_axis_with_small_spread_is_flagged(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path)
    fake_llm = _FakeChartLLM(
        readings={
            1: {
                "chart_type": "bar",
                "y_axis_starts_at_zero": False,
                "series": [{"label": "s", "values": [10, 15]}],
                "value_labels_present": True,
            }
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert any("ось Y" in f.title.lower() or "ось" in f.title.lower() for f in findings)


@pytest.mark.asyncio
async def test_nonzero_axis_with_large_spread_is_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path)
    fake_llm = _FakeChartLLM(
        readings={
            1: {
                "chart_type": "bar",
                "y_axis_starts_at_zero": False,
                "series": [{"label": "s", "values": [10, 30]}],
                "value_labels_present": True,
            }
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert findings == []


@pytest.mark.asyncio
async def test_zero_axis_never_flagged_regardless_of_spread(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path)
    fake_llm = _FakeChartLLM(
        readings={
            1: {
                "chart_type": "bar",
                "y_axis_starts_at_zero": True,
                "series": [{"label": "s", "values": [1, 100]}],
                "value_labels_present": True,
            }
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert findings == []


@pytest.mark.asyncio
async def test_pie_sum_not_100_is_flagged(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path)
    fake_llm = _FakeChartLLM(
        readings={
            1: {
                "chart_type": "pie",
                "y_axis_starts_at_zero": True,
                "series": [{"label": "s", "values": [40, 40, 12]}],
                "value_labels_present": True,
            }
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert any("100" in f.description for f in findings)


@pytest.mark.asyncio
async def test_pie_sum_within_tolerance_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path)
    fake_llm = _FakeChartLLM(
        readings={
            1: {
                "chart_type": "pie",
                "y_axis_starts_at_zero": True,
                "series": [{"label": "s", "values": [40, 40, 20]}],
                "value_labels_present": True,
            }
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert findings == []


def _write_workbook(path: Path, values: list[float]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    for i, value in enumerate(values, start=1):
        ws.cell(row=i, column=1, value=value)
    wb.save(path)


@pytest.mark.asyncio
async def test_excel_cross_check_flags_unmatched_value(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path)
    ctx.xlsx_path = tmp_path / "data.xlsx"
    _write_workbook(ctx.xlsx_path, [10.0, 20.0, 30.0])
    fake_llm = _FakeChartLLM(
        readings={
            1: {
                "chart_type": "bar",
                "y_axis_starts_at_zero": True,
                "series": [{"label": "s", "values": [10, 20, 999]}],
                "value_labels_present": True,
            }
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert any("Excel" in f.title for f in findings)


@pytest.mark.asyncio
async def test_excel_cross_check_passes_when_values_match(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path)
    ctx.xlsx_path = tmp_path / "data.xlsx"
    _write_workbook(ctx.xlsx_path, [10.0, 20.0, 30.0])
    fake_llm = _FakeChartLLM(
        readings={
            1: {
                "chart_type": "bar",
                "y_axis_starts_at_zero": True,
                "series": [{"label": "s", "values": [10, 20, 30]}],
                "value_labels_present": True,
            }
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert findings == []


@pytest.mark.asyncio
async def test_no_excel_attached_skips_cross_check(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path)
    assert ctx.xlsx_path is None
    fake_llm = _FakeChartLLM(
        readings={
            1: {
                "chart_type": "bar",
                "y_axis_starts_at_zero": True,
                "series": [{"label": "s", "values": [10, 20, 999]}],
                "value_labels_present": True,
            }
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert findings == []


@pytest.mark.asyncio
async def test_label_contradiction_is_included(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path, text="Продажи растут каждый квартал")
    fake_llm = _FakeChartLLM(
        label_response={
            "contradicts": True,
            "finding": {
                "category": "CHART",
                "severity": "MAJOR",
                "title": "Подпись противоречит данным",
                "description": "Текст утверждает рост, график показывает падение",
                "fix_suggestion": "Исправить текст или график",
            },
        }
    )

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert fake_llm.structured_calls == 1
    assert any(f.title == "Подпись противоречит данным" for f in findings)


@pytest.mark.asyncio
async def test_label_no_contradiction_produces_no_finding(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path, text="Продажи растут каждый квартал")
    fake_llm = _FakeChartLLM(label_response={"contradicts": False})

    findings = await ChartChecker(fake_llm).analyze(ctx)

    assert fake_llm.structured_calls == 1
    assert findings == []


@pytest.mark.asyncio
async def test_label_check_skipped_without_slide_text(tmp_path: Path) -> None:
    ctx = _ctx_with_chart_slide(tmp_path, text=None)
    fake_llm = _FakeChartLLM()

    await ChartChecker(fake_llm).analyze(ctx)

    assert fake_llm.structured_calls == 0


def test_label_consistency_response_defaults() -> None:
    response = LabelConsistencyResponse.model_validate({"contradicts": False})
    assert response.finding is None


def test_chart_reading_reused_directly() -> None:
    reading = ChartReading.model_validate(
        {
            "chart_type": "bar",
            "y_axis_starts_at_zero": True,
            "series": [{"label": "a", "values": [1, 2]}],
            "value_labels_present": True,
        }
    )
    assert reading.chart_type == "bar"
