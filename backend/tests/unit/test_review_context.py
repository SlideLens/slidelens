"""Unit tests for ReviewContext."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from core.context import ReviewContext
from core.schemas import Category, Finding, Severity


def test_dump_round_trip(tmp_path: Path) -> None:
    ctx = ReviewContext(
        workdir=tmp_path,
        deck_path=tmp_path / "deck.pptx",
        review_id=uuid4(),
    )
    ctx.add_cost(0.42)
    ctx.add_findings(
        [
            Finding(
                category=Category.TYPOGRAPHY,
                severity=Severity.MINOR,
                title="Мелкий текст",
                description="d",
                fix_suggestion="f",
            )
        ],
        source="SlideAnalyzer",
    )
    path = ctx.dump()
    restored = ReviewContext.load(path)
    assert restored.total_cost_rub == 0.42
    assert len(restored.findings) == 1
    assert restored.findings[0].source == "SlideAnalyzer"
    assert restored.deck_path == ctx.deck_path
    assert restored.review_id == ctx.review_id


def test_add_findings_sets_source() -> None:
    ctx = ReviewContext(workdir=Path("."))
    finding = Finding(
        category=Category.CHART,
        severity=Severity.MAJOR,
        title="Ось",
        description="d",
        fix_suggestion="f",
    )
    ctx.add_findings([finding], source="ChartChecker")
    assert ctx.findings[0].source == "ChartChecker"
