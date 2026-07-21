"""Unit tests for ``tests.golden.eval`` (matching, aggregation, quality-log)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "golden"))

from eval import (  # noqa: E402
    DeckEvalResult,
    EvalSummary,
    GoldenExpectedFinding,
    append_quality_log,
    load_golden_set,
    match_findings,
    summarize,
)

from core.aggregate_schemas import SameIssueResponse  # noqa: E402
from core.schemas import Category, Finding, Severity  # noqa: E402


def _finding(**overrides: Any) -> Finding:
    payload: dict[str, Any] = {
        "slide_num": 1,
        "category": Category.TYPOGRAPHY,
        "severity": Severity.MINOR,
        "title": "t",
        "description": "d",
        "fix_suggestion": "f",
    }
    payload.update(overrides)
    return Finding(**payload)


class _FakeJudgeLLM:
    def __init__(self, *, verdicts: list[bool] | None = None) -> None:
        self._verdicts = verdicts if verdicts is not None else []
        self.calls = 0

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[Any],
        *,
        system: str | None = None,
        tier: str = "full",
        prompt_version: str | None = None,
        ctx: Any = None,
    ) -> Any:
        verdict = self._verdicts[self.calls] if self.calls < len(self._verdicts) else False
        self.calls += 1
        return response_model.model_validate({"same_issue": verdict})


def test_load_golden_set_parses_expected(tmp_path: Path) -> None:
    (tmp_path / "decks").mkdir()
    (tmp_path / "expected").mkdir()
    (tmp_path / "decks" / "deck_a.pptx").write_bytes(b"")
    (tmp_path / "expected" / "deck_a.yaml").write_text(
        "- slide_num: 2\n  category: CHART\n  description: test\n", encoding="utf-8"
    )
    (tmp_path / "decks" / "deck_b.pptx").write_bytes(b"")

    golden = load_golden_set(tmp_path)

    assert [d.name for d in golden] == ["deck_a", "deck_b"]
    assert golden[0].expected == [
        GoldenExpectedFinding(slide_num=2, category=Category.CHART, description="test")
    ]
    assert golden[1].expected == []


@pytest.mark.asyncio
async def test_match_findings_requires_slide_and_category_candidate() -> None:
    expected = [GoldenExpectedFinding(slide_num=1, category=Category.CHART, description="d")]
    actual = [_finding(slide_num=1, category=Category.TYPOGRAPHY)]
    fake_llm = _FakeJudgeLLM()

    matched, junk = await match_findings(fake_llm, expected, actual)

    assert matched == 0
    assert junk == 1
    assert fake_llm.calls == 0


@pytest.mark.asyncio
async def test_match_findings_judge_confirms() -> None:
    expected = [GoldenExpectedFinding(slide_num=1, category=Category.CHART, description="d")]
    actual = [_finding(slide_num=1, category=Category.CHART)]
    fake_llm = _FakeJudgeLLM(verdicts=[True])

    matched, junk = await match_findings(fake_llm, expected, actual)

    assert matched == 1
    assert junk == 0
    assert fake_llm.calls == 1


@pytest.mark.asyncio
async def test_match_findings_judge_rejects_counts_as_junk() -> None:
    expected = [GoldenExpectedFinding(slide_num=1, category=Category.CHART, description="d")]
    actual = [_finding(slide_num=1, category=Category.CHART)]
    fake_llm = _FakeJudgeLLM(verdicts=[False])

    matched, junk = await match_findings(fake_llm, expected, actual)

    assert matched == 0
    assert junk == 1


@pytest.mark.asyncio
async def test_match_findings_one_actual_cannot_satisfy_two_expected() -> None:
    expected = [
        GoldenExpectedFinding(slide_num=1, category=Category.CHART, description="d1"),
        GoldenExpectedFinding(slide_num=1, category=Category.CHART, description="d2"),
    ]
    actual = [_finding(slide_num=1, category=Category.CHART)]
    fake_llm = _FakeJudgeLLM(verdicts=[True, True])

    matched, junk = await match_findings(fake_llm, expected, actual)

    assert matched == 1
    assert junk == 0


def test_summarize_zero_expected_gives_zero_recall() -> None:
    results = [DeckEvalResult("d", n_expected=0, n_matched=0, n_actual=3, n_junk=3, cost_usd=0.1)]
    summary = summarize(results)
    assert summary.recall == 0.0
    assert summary.junk_rate == 1.0


def test_summarize_zero_actual_gives_zero_junk_rate() -> None:
    results = [DeckEvalResult("d", n_expected=2, n_matched=0, n_actual=0, n_junk=0, cost_usd=0.0)]
    summary = summarize(results)
    assert summary.junk_rate == 0.0
    assert summary.recall == 0.0


def test_summarize_aggregates_across_decks() -> None:
    results = [
        DeckEvalResult("a", n_expected=2, n_matched=2, n_actual=2, n_junk=0, cost_usd=0.1),
        DeckEvalResult("b", n_expected=2, n_matched=1, n_actual=3, n_junk=2, cost_usd=0.3),
    ]
    summary = summarize(results)
    assert summary.recall == pytest.approx(3 / 4)
    assert summary.junk_rate == pytest.approx(2 / 5)
    assert summary.avg_cost_usd == pytest.approx(0.2)
    assert summary.n_decks == 2


def test_append_quality_log_creates_header_then_appends(tmp_path: Path) -> None:
    log_path = tmp_path / "quality-log.md"
    summary = EvalSummary(
        recall=0.75, junk_rate=0.1, total_cost_usd=1.0, avg_cost_usd=0.2, n_decks=5
    )

    append_quality_log(
        log_path, prompt_version="v1", summary=summary, today=date(2026, 1, 1)
    )
    first_content = log_path.read_text(encoding="utf-8")
    assert first_content.count("| date |") == 1
    assert "2026-01-01" in first_content
    assert "75%" in first_content

    append_quality_log(
        log_path, prompt_version="v2", summary=summary, today=date(2026, 1, 2)
    )
    second_content = log_path.read_text(encoding="utf-8")
    assert second_content.count("| date |") == 1
    assert "2026-01-02" in second_content


def test_judge_response_defaults_false() -> None:
    assert SameIssueResponse.model_validate({}).same_issue is False
