"""Unit tests for ``core.analyzers.slide.SlideAnalyzer``."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from core.analyzers.slide import SlideAnalyzer
from core.context import ReviewContext


class _FakeLLM:
    def __init__(self, *, response_for: dict[int, dict[str, Any]] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response_for = response_for or {}
        self._concurrent = 0
        self.max_concurrent = 0

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
        self._concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self._concurrent)
        await asyncio.sleep(0.01)
        slide_num = int(Path(images[0]).stem.split("_")[1])
        self.calls.append(
            {
                "slide_num": slide_num,
                "prompt": prompt,
                "system": system,
                "prompt_version": prompt_version,
            }
        )
        self._concurrent -= 1
        payload = self._response_for.get(slide_num, {"findings": [], "has_chart": False})
        return response_model.model_validate(payload)


def _ctx_with_slides(
    tmp_path: Path, n: int, texts: dict[int, str] | None = None
) -> ReviewContext:
    ctx = ReviewContext(workdir=tmp_path)
    for i in range(1, n + 1):
        png = tmp_path / f"slide_{i:03d}.png"
        png.write_bytes(b"fake png")
        ctx.slide_pngs[i] = png
    if texts:
        ctx.meta["slide_texts"] = texts
    return ctx


@pytest.mark.asyncio
async def test_slide_analyzer_sets_slide_num_and_has_chart(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 2, {1: "Первый слайд", 2: "Второй слайд"})
    fake_llm = _FakeLLM(
        response_for={
            1: {
                "findings": [
                    {
                        "category": "TYPOGRAPHY",
                        "severity": "MINOR",
                        "title": "Мелкий кегль на слайде 1",
                        "description": "Основной текст слишком мелкий.",
                        "fix_suggestion": "Увеличьте кегль основного текста.",
                    }
                ],
                "has_chart": False,
            },
            2: {
                "findings": [
                    {
                        "category": "HIERARCHY",
                        "severity": "MAJOR",
                        "title": "Слабая иерархия на слайде 2",
                        "description": "Заголовок не выделяется среди текста.",
                        "fix_suggestion": "Усильте визуальный вес заголовка.",
                    }
                ],
                "has_chart": True,
            },
        }
    )

    findings = await SlideAnalyzer(fake_llm).analyze(ctx)

    by_slide = {f.slide_num: f for f in findings}
    assert by_slide[1].title == "Мелкий кегль на слайде 1"
    assert by_slide[2].title == "Слабая иерархия на слайде 2"
    assert ctx.meta["has_chart"] == {1: False, 2: True}


@pytest.mark.asyncio
async def test_slide_analyzer_missing_text_uses_placeholder(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 1)
    fake_llm = _FakeLLM()

    await SlideAnalyzer(fake_llm).analyze(ctx)

    assert "не извлечён" in fake_llm.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_slide_analyzer_respects_concurrency_cap(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 10)
    fake_llm = _FakeLLM()

    await SlideAnalyzer(fake_llm, concurrency=4).analyze(ctx)

    assert fake_llm.max_concurrent <= 4
    assert len(fake_llm.calls) == 10


@pytest.mark.asyncio
async def test_slide_analyzer_uses_system_prompt(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 1, {1: "text"})
    fake_llm = _FakeLLM()

    await SlideAnalyzer(fake_llm).analyze(ctx)

    call = fake_llm.calls[0]
    assert call["system"] is not None
    assert "сеньор-дизайнер" in call["system"]
