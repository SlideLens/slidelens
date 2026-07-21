"""Unit tests for ``core.analyzers.deck.DeckAnalyzer``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from core.analyzers.deck import DeckAnalyzer
from core.context import ReviewContext


class _FakeDeckLLM:
    def __init__(self, *, findings: list[dict[str, Any]] | None = None) -> None:
        self._findings = findings or []
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append({"images": list(images), "prompt": prompt, "system": system})
        return response_model.model_validate({"findings": self._findings})


def _ctx_with_slides(tmp_path: Path, n: int, texts: dict[int, str] | None = None) -> ReviewContext:
    ctx = ReviewContext(workdir=tmp_path)
    for i in range(1, n + 1):
        png = tmp_path / f"slide_{i:03d}.png"
        Image.new("RGB", (100, 75), "white").save(png, "PNG")
        ctx.slide_pngs[i] = png
    if texts:
        ctx.meta["slide_texts"] = texts
    return ctx


@pytest.mark.asyncio
async def test_small_deck_uses_one_contact_sheet(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 5)
    fake_llm = _FakeDeckLLM()

    await DeckAnalyzer(fake_llm).analyze(ctx)

    assert len(fake_llm.calls) == 1
    assert len(fake_llm.calls[0]["images"]) == 1


@pytest.mark.asyncio
async def test_large_deck_splits_into_two_sheets_never_more(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 40)
    fake_llm = _FakeDeckLLM()

    await DeckAnalyzer(fake_llm).analyze(ctx)

    assert len(fake_llm.calls[0]["images"]) == 2


@pytest.mark.asyncio
async def test_deck_level_finding_keeps_slide_num_none(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 3)
    fake_llm = _FakeDeckLLM(
        findings=[
            {
                "slide_num": None,
                "category": "NARRATIVE",
                "severity": "MAJOR",
                "title": "Провал структуры истории",
                "description": "Нет перехода от проблемы к решению.",
                "fix_suggestion": "Добавьте явный слайд с решением после проблемы.",
            }
        ]
    )

    findings = await DeckAnalyzer(fake_llm).analyze(ctx)

    assert findings[0].slide_num is None


@pytest.mark.asyncio
async def test_slide_attributed_finding_keeps_its_slide_num(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 3)
    fake_llm = _FakeDeckLLM(
        findings=[
            {
                "slide_num": 2,
                "category": "CONSISTENCY",
                "severity": "MINOR",
                "title": "Разные шрифты заголовков",
                "description": "На слайде 2 заголовок другой гарнитуры.",
                "fix_suggestion": "Унифицируйте гарнитуру заголовков.",
            }
        ]
    )

    findings = await DeckAnalyzer(fake_llm).analyze(ctx)

    assert findings[0].slide_num == 2


@pytest.mark.asyncio
async def test_font_mismatch_and_duplicate_slide_findings_both_present(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(
        tmp_path, 3, texts={1: "Проблема", 2: "Проблема", 3: "Решение и доказательства"}
    )
    fake_llm = _FakeDeckLLM(
        findings=[
            {
                "slide_num": 2,
                "category": "CONSISTENCY",
                "severity": "MINOR",
                "title": "Разные шрифты заголовков",
                "description": "Слайд 2 использует другой шрифт",
                "fix_suggestion": "Унифицируйте гарнитуру заголовков.",
            },
            {
                "slide_num": None,
                "category": "CONSISTENCY",
                "severity": "MAJOR",
                "title": "Дублирующие слайды",
                "description": "Слайды 1 и 2 дублируют друг друга",
                "fix_suggestion": "Объедините или удалите один из дублей.",
            },
        ]
    )

    findings = await DeckAnalyzer(fake_llm).analyze(ctx)

    titles = {f.title for f in findings}
    assert titles == {"Разные шрифты заголовков", "Дублирующие слайды"}


@pytest.mark.asyncio
async def test_no_slides_returns_no_findings_without_llm_call(tmp_path: Path) -> None:
    ctx = ReviewContext(workdir=tmp_path)
    fake_llm = _FakeDeckLLM()

    findings = await DeckAnalyzer(fake_llm).analyze(ctx)

    assert findings == []
    assert fake_llm.calls == []
