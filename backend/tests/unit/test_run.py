"""Unit tests for ``core.run`` (PipelineOrchestrator + CLI)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from core.analyzers.base import BaseAnalyzer
from core.context import ReviewContext
from core.llm import LLMClient, LLMConfig
from core.run import PipelineOrchestrator, default_steps, main
from core.schemas import Category, Finding, Severity


def _make_pdf(path: Path, n_pages: int) -> None:
    images = [Image.new("RGB", (200, 150), "white") for _ in range(n_pages)]
    images[0].save(path, save_all=True, append_images=images[1:])


class _OkAnalyzer(BaseAnalyzer):
    name = "ok"

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        return [
            Finding(
                category=Category.TYPOGRAPHY,
                severity=Severity.MINOR,
                title="t",
                description="d",
                fix_suggestion="f",
            )
        ]


class _BadAnalyzer(BaseAnalyzer):
    name = "bad"

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        raise RuntimeError("boom")


def test_default_steps_order_is_slide_zoom_deck_chart_crossmodal() -> None:
    llm = LLMClient(LLMConfig(api_key="test-key"))
    steps = default_steps(llm)
    assert [type(step).__name__ for step in steps] == [
        "SlideAnalyzer",
        "ZoomAgent",
        "DeckAnalyzer",
        "ChartChecker",
        "CrossModalAnalyzer",
    ]


@pytest.mark.asyncio
async def test_orchestrator_continues_after_one_analyzer_fails(tmp_path: Path) -> None:
    ctx = ReviewContext(workdir=tmp_path)
    orchestrator = PipelineOrchestrator([_BadAnalyzer(), _OkAnalyzer()])

    await orchestrator.run(ctx)

    assert len(ctx.findings) == 1
    assert ctx.findings[0].source == "ok"


async def _fake_complete_vision_structured(
    self: Any,
    images: list[Path],
    prompt: str,
    response_model: type[Any],
    *,
    system: str | None = None,
    tier: str = "full",
    prompt_version: str | None = None,
    ctx: ReviewContext | None = None,
) -> Any:
    return response_model.model_validate({"findings": [], "has_chart": False})


def test_cli_writes_findings_and_pngs_for_valid_deck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "core.llm.client.LLMClient.complete_vision_structured",
        _fake_complete_vision_structured,
    )
    monkeypatch.setattr(
        "core.report._weasyprint_html_to_pdf", lambda html: b"%PDF-fake%"
    )
    deck = tmp_path / "deck.pdf"
    _make_pdf(deck, 2)
    out_dir = tmp_path / "out"

    exit_code = main(["--deck", str(deck), "--out", str(out_dir)])

    assert exit_code == 0
    findings_path = out_dir / "findings.json"
    assert findings_path.is_file()
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert (out_dir / "slide_001.png").is_file()
    assert (out_dir / "slide_002.png").is_file()
    assert (out_dir / "report.html").is_file()
    assert (out_dir / "report.pdf").read_bytes() == b"%PDF-fake%"
    assert "slides=2" in capsys.readouterr().out


def test_cli_exits_nonzero_on_corrupted_deck(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deck = tmp_path / "bad.pptx"
    deck.write_bytes(b"not a real pptx")
    out_dir = tmp_path / "out"

    exit_code = main(["--deck", str(deck), "--out", str(out_dir)])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert "Traceback" not in err
