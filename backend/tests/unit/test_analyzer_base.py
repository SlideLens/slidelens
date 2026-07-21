"""Unit tests for ``core.analyzers.base.BaseAnalyzer`` graceful degradation."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.analyzers.base import BaseAnalyzer
from core.context import ReviewContext
from core.schemas import Category, Finding, Severity


def _finding(title: str) -> Finding:
    return Finding(
        category=Category.TYPOGRAPHY,
        severity=Severity.MINOR,
        title=title,
        description="d",
        fix_suggestion="f",
    )


class _OkAnalyzer(BaseAnalyzer):
    name = "ok_analyzer"

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        return [_finding("ok")]


class _FailingAnalyzer(BaseAnalyzer):
    name = "failing_analyzer"

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def _no_op_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.analyzers.base.observe_pipeline_step", lambda *a, **k: None)


@pytest.mark.asyncio
async def test_run_returns_findings_and_sets_source(tmp_path: Path) -> None:
    ctx = ReviewContext(workdir=tmp_path)

    findings = await _OkAnalyzer().run(ctx)

    assert len(findings) == 1
    assert ctx.findings[0].source == "ok_analyzer"


@pytest.mark.asyncio
async def test_run_isolates_exception(tmp_path: Path) -> None:
    ctx = ReviewContext(workdir=tmp_path)

    findings = await _FailingAnalyzer().run(ctx)

    assert findings == []
    assert ctx.findings == []


@pytest.mark.asyncio
async def test_run_observes_duration_on_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, float]] = []
    monkeypatch.setattr(
        "core.analyzers.base.observe_pipeline_step",
        lambda name, duration: calls.append((name, duration)),
    )
    ctx = ReviewContext(workdir=tmp_path)

    await _OkAnalyzer().run(ctx)
    await _FailingAnalyzer().run(ctx)

    assert [c[0] for c in calls] == ["ok_analyzer", "failing_analyzer"]
    assert all(c[1] >= 0 for c in calls)
