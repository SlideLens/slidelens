"""Unit tests for ``core.aggregate`` (Aggregator, DeckScorer)."""

from __future__ import annotations

from typing import Any

import pytest

from core.aggregate import Aggregator, DeckScorer
from core.schemas import BBox, Category, Finding, Severity


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


class _FakeSameIssueLLM:
    def __init__(self, *, verdict: bool = False) -> None:
        self._verdict = verdict
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
        self.calls += 1
        return response_model.model_validate({"same_issue": self._verdict})


_BBOX_A = BBox(x=0.1, y=0.1, w=0.2, h=0.2)
_BBOX_B = BBox(x=0.7, y=0.7, w=0.1, h=0.1)


@pytest.mark.asyncio
async def test_confirmed_duplicate_is_dropped() -> None:
    findings = [
        _finding(title="a", bbox=_BBOX_A),
        _finding(title="b", bbox=_BBOX_A),
    ]
    llm = _FakeSameIssueLLM(verdict=True)

    result = await Aggregator(llm).run(findings)

    assert len(result) == 1
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_judge_rejection_keeps_both() -> None:
    findings = [
        _finding(title="a", bbox=_BBOX_A),
        _finding(title="b", bbox=_BBOX_A),
    ]
    llm = _FakeSameIssueLLM(verdict=False)

    result = await Aggregator(llm).run(findings)

    assert len(result) == 2
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_non_overlapping_bboxes_skip_judge_call() -> None:
    findings = [
        _finding(title="a", bbox=_BBOX_A),
        _finding(title="b", bbox=_BBOX_B),
    ]
    llm = _FakeSameIssueLLM(verdict=True)

    result = await Aggregator(llm).run(findings)

    assert len(result) == 2
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_findings_without_bbox_are_never_deduped() -> None:
    findings = [_finding(title=f"t{i}") for i in range(3)]
    llm = _FakeSameIssueLLM(verdict=True)

    result = await Aggregator(llm).run(findings)

    assert len(result) == 3
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_overflow_beyond_cap_becomes_one_misc_finding() -> None:
    findings = [
        _finding(title=f"t{i}", severity=Severity.MINOR, category=Category.READABILITY)
        for i in range(10)
    ]
    llm = _FakeSameIssueLLM(verdict=True)

    result = await Aggregator(llm, max_per_slide=7).run(findings)

    assert len(result) == 8
    assert result[-1].title == "Прочее"
    assert "3" in result[-1].description


@pytest.mark.asyncio
async def test_final_order_is_severity_then_slide_num() -> None:
    findings = [
        _finding(slide_num=3, severity=Severity.MINOR, title="minor-3"),
        _finding(slide_num=1, severity=Severity.CRITICAL, title="critical-1"),
        _finding(slide_num=2, severity=Severity.MAJOR, title="major-2"),
        _finding(slide_num=1, severity=Severity.MAJOR, title="major-1"),
    ]
    llm = _FakeSameIssueLLM(verdict=False)

    result = await Aggregator(llm).run(findings)

    assert [f.title for f in result] == ["critical-1", "major-1", "major-2", "minor-3"]


def test_deck_scorer_empty_findings_scores_100() -> None:
    assert DeckScorer().score([], n_slides=10) == 100


def test_deck_scorer_applies_weighted_formula() -> None:
    findings = [_finding(severity=Severity.CRITICAL), _finding(severity=Severity.MAJOR)]
    score = DeckScorer(weights={Severity.CRITICAL: 12, Severity.MAJOR: 5, Severity.MINOR: 1}).score(
        findings, n_slides=1
    )
    assert score == 100 - (12 + 5)


def test_deck_scorer_normalizes_by_slide_count() -> None:
    findings = [_finding(severity=Severity.CRITICAL)]
    score_few_slides = DeckScorer().score(findings, n_slides=1)
    score_many_slides = DeckScorer().score(findings, n_slides=12)
    assert score_many_slides > score_few_slides


def test_deck_scorer_floor_is_respected() -> None:
    findings = [_finding(severity=Severity.CRITICAL) for _ in range(50)]
    assert DeckScorer(floor=5).score(findings, n_slides=1) == 5


def test_deck_scorer_is_deterministic() -> None:
    findings = [_finding(severity=Severity.MAJOR), _finding(severity=Severity.MINOR)]
    scorer = DeckScorer()
    assert scorer.score(findings, n_slides=5) == scorer.score(findings, n_slides=5)
