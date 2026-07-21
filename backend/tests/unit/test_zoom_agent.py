"""Unit tests for ``core.analyzers.zoom.ZoomAgent``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from core.analyzers.schemas import ScreeningResponse
from core.analyzers.zoom import ZoomAgent
from core.context import ReviewContext
from core.schemas import BBox, Category, Finding, Severity


class _FakeZoomLLM:
    def __init__(
        self,
        *,
        regions: list[dict[str, Any]] | None = None,
        zoom_findings: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        self._regions = regions if regions is not None else []
        self._zoom_findings = zoom_findings or []
        self.screening_calls = 0
        self.analysis_calls = 0

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
        if response_model is ScreeningResponse:
            self.screening_calls += 1
            return response_model.model_validate({"regions": self._regions})

        idx = self.analysis_calls
        self.analysis_calls += 1
        findings = self._zoom_findings[idx] if idx < len(self._zoom_findings) else []
        return response_model.model_validate({"findings": findings, "has_chart": False})


def _ctx_with_one_slide(tmp_path: Path, size: tuple[int, int] = (400, 300)) -> ReviewContext:
    ctx = ReviewContext(workdir=tmp_path)
    png = tmp_path / "slide_001.png"
    Image.new("RGB", size, "white").save(png, "PNG")
    ctx.slide_pngs[1] = png
    return ctx


def _finding_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "category": "READABILITY",
        "severity": "MINOR",
        "title": "Мелкий текст в зоне",
        "description": "В выделенной области текст слишком мелкий для проекции.",
        "fix_suggestion": "Увеличьте кегль текста в этой зоне.",
        # Родной формат рамок модели: [ymin, xmin, ymax, xmax] в шкале 0..1000.
        "box_2d": [100, 100, 200, 300],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_zoom_cap_limits_full_tier_calls(tmp_path: Path) -> None:
    ctx = _ctx_with_one_slide(tmp_path)
    regions = [
        {"box_2d": [0, i * 100, 50, i * 100 + 50], "reason": "small_text"} for i in range(5)
    ]
    fake_llm = _FakeZoomLLM(regions=regions)

    await ZoomAgent(fake_llm).analyze(ctx)

    assert fake_llm.screening_calls == 1
    assert fake_llm.analysis_calls == 3


@pytest.mark.asyncio
async def test_crop_is_upscaled_2x(tmp_path: Path) -> None:
    ctx = _ctx_with_one_slide(tmp_path, size=(400, 300))
    regions = [{"box_2d": [0, 0, 500, 500], "reason": "small_text"}]
    fake_llm = _FakeZoomLLM(regions=regions)

    await ZoomAgent(fake_llm).analyze(ctx)

    crop_path = tmp_path / "slide_001_zoom_01.png"
    assert crop_path.is_file()
    with Image.open(crop_path) as img:
        assert img.size == (400, 300)  # (400*0.5)*2 x (300*0.5)*2


@pytest.mark.asyncio
async def test_overlapping_zoom_finding_is_dropped(tmp_path: Path) -> None:
    ctx = _ctx_with_one_slide(tmp_path)
    ctx.add_findings(
        [
            Finding(
                slide_num=1,
                category=Category.READABILITY,
                severity=Severity.MINOR,
                title="existing",
                description="d",
                fix_suggestion="f",
                bbox=BBox(x=0.1, y=0.1, w=0.2, h=0.1),
            )
        ],
        source="slide_analyzer",
    )
    # Кроп накрывает ровно ту же область слайда, что и уже найденная Находка,
    # а внутри кропа модель показывает почти весь фрагмент — после переноса в
    # координаты слайда рамки совпадут, и дубль должен отсеяться.
    regions = [{"box_2d": [100, 100, 200, 300], "reason": "small_text"}]
    fake_llm = _FakeZoomLLM(
        regions=regions,
        zoom_findings=[[_finding_payload(box_2d=[0, 0, 1000, 900])]],
    )

    findings = await ZoomAgent(fake_llm).analyze(ctx)

    assert findings == []


@pytest.mark.asyncio
async def test_nonoverlapping_zoom_finding_is_kept(tmp_path: Path) -> None:
    ctx = _ctx_with_one_slide(tmp_path)
    ctx.add_findings(
        [
            Finding(
                slide_num=1,
                category=Category.READABILITY,
                severity=Severity.MINOR,
                title="existing",
                description="d",
                fix_suggestion="f",
                bbox=BBox(x=0.1, y=0.1, w=0.2, h=0.1),
            )
        ],
        source="slide_analyzer",
    )
    regions = [{"box_2d": [600, 600, 700, 700], "reason": "small_text"}]
    fake_llm = _FakeZoomLLM(
        regions=regions,
        zoom_findings=[[_finding_payload(box_2d=[700, 700, 800, 900])]],
    )

    findings = await ZoomAgent(fake_llm).analyze(ctx)

    assert len(findings) == 1
    assert findings[0].slide_num == 1


@pytest.mark.asyncio
async def test_zoom_bbox_is_projected_from_crop_back_onto_the_slide(tmp_path: Path) -> None:
    """Модель видит только кроп и меряет от его угла — рамка должна вернуться на слайд."""
    ctx = _ctx_with_one_slide(tmp_path, size=(400, 300))
    # Кроп — правее и ниже центра, так что «сырые» координаты указали бы не туда.
    regions = [{"box_2d": [400, 500, 600, 900], "reason": "small_text"}]
    fake_llm = _FakeZoomLLM(
        regions=regions,
        zoom_findings=[[_finding_payload(box_2d=[500, 500, 1000, 1000])]],
    )

    findings = await ZoomAgent(fake_llm).analyze(ctx)

    assert len(findings) == 1
    bbox = findings[0].bbox
    assert bbox is not None
    assert bbox.x == pytest.approx(0.7)  # 0.5 + 0.5*0.4
    assert bbox.y == pytest.approx(0.5)  # 0.4 + 0.5*0.2
    assert bbox.w == pytest.approx(0.2)  # 0.5*0.4
    assert bbox.h == pytest.approx(0.1)  # 0.5*0.2


@pytest.mark.asyncio
async def test_degenerate_region_is_skipped_without_a_paid_call(tmp_path: Path) -> None:
    """Схлопнутая рамка не даёт зоны для зума — платный проход по ней не нужен."""
    ctx = _ctx_with_one_slide(tmp_path, size=(400, 300))
    regions = [{"box_2d": [300, 300, 300, 300], "reason": "small_text"}]
    fake_llm = _FakeZoomLLM(regions=regions, zoom_findings=[[_finding_payload()]])

    findings = await ZoomAgent(fake_llm).analyze(ctx)

    assert findings == []
    assert fake_llm.analysis_calls == 0


@pytest.mark.asyncio
async def test_zoom_finds_what_slide_pass_missed(tmp_path: Path) -> None:
    ctx = _ctx_with_one_slide(tmp_path)  # ctx.findings is empty: SlideAnalyzer found nothing
    regions = [{"box_2d": [0, 0, 200, 200], "reason": "small_text"}]
    fake_llm = _FakeZoomLLM(
        regions=regions, zoom_findings=[[_finding_payload(title="Пропущенная зона")]]
    )

    findings = await ZoomAgent(fake_llm).analyze(ctx)

    assert len(findings) == 1
    assert findings[0].title == "Пропущенная зона"
