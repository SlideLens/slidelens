"""``Aggregator`` (dedup/order/cap) and ``DeckScorer`` (0-100 score formula)."""

from __future__ import annotations

from collections import defaultdict

from core.aggregate_schemas import SameIssueResponse
from core.constants import (
    DEDUP_IOU_THRESHOLD,
    MAX_FINDINGS_PER_SLIDE,
    SCORE_FLOOR,
    SEVERITY_WEIGHTS,
)
from core.geometry import iou
from core.llm import LLMClient, PromptRegistry, default_registry
from core.schemas import Category, Finding, Severity

SAME_ISSUE_PROMPT_NAME = "same_issue_judge"

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.MAJOR: 1,
    Severity.MINOR: 2,
}


def _misc_finding(slide_num: int | None, category: Category, overflow: int) -> Finding:
    return Finding(
        slide_num=slide_num,
        category=category,
        severity=Severity.MINOR,
        title="Прочее",
        description=f"Ещё {overflow} находок(и) на этом слайде не показаны в отчёте.",
        fix_suggestion="Полный список находок доступен в JSON-выгрузке разбора.",
        source="aggregator",
    )


class Aggregator:
    """Dedups (IoU + LLM confirmation), caps per slide, orders severity→slide_num."""

    def __init__(
        self,
        llm: LLMClient,
        *,
        prompts: PromptRegistry | None = None,
        iou_threshold: float = DEDUP_IOU_THRESHOLD,
        max_per_slide: int = MAX_FINDINGS_PER_SLIDE,
    ) -> None:
        self._llm = llm
        self._prompts = prompts or default_registry()
        self._iou_threshold = iou_threshold
        self._max_per_slide = max_per_slide

    async def run(self, findings: list[Finding]) -> list[Finding]:
        deduped = await self._dedup(findings)
        capped = self._cap_per_slide(deduped)
        capped.sort(
            key=lambda f: (
                _SEVERITY_ORDER[f.severity],
                f.slide_num if f.slide_num is not None else -1,
            )
        )
        return capped

    async def _dedup(self, findings: list[Finding]) -> list[Finding]:
        kept: list[Finding] = []
        for finding in findings:
            is_duplicate = False
            for other in kept:
                if (
                    finding.slide_num == other.slide_num
                    and finding.bbox is not None
                    and other.bbox is not None
                    and iou(finding.bbox, other.bbox) > self._iou_threshold
                    and await self._confirm_same_issue(finding, other)
                ):
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept.append(finding)
        return kept

    async def _confirm_same_issue(self, a: Finding, b: Finding) -> bool:
        system_prompt = self._prompts.get(SAME_ISSUE_PROMPT_NAME).body
        prompt = f"Описание А: {a.description}\nОписание Б: {b.description}"
        response = await self._llm.complete_structured(
            prompt, SameIssueResponse, system=system_prompt, tier="screening"
        )
        return response.same_issue

    def _cap_per_slide(self, findings: list[Finding]) -> list[Finding]:
        by_slide: dict[int | None, list[Finding]] = defaultdict(list)
        for finding in findings:
            by_slide[finding.slide_num].append(finding)

        result: list[Finding] = []
        for slide_num, group in by_slide.items():
            group.sort(key=lambda f: _SEVERITY_ORDER[f.severity])
            if len(group) <= self._max_per_slide:
                result.extend(group)
                continue
            kept = group[: self._max_per_slide]
            overflow = len(group) - self._max_per_slide
            result.extend(kept)
            result.append(_misc_finding(slide_num, kept[0].category, overflow))
        return result


class DeckScorer:
    """``100 − (Σ severity-weight / n_slides)``, floored, capped at 100."""

    def __init__(
        self,
        *,
        weights: dict[Severity, int] | None = None,
        floor: int = SCORE_FLOOR,
    ) -> None:
        self._weights = weights or {
            Severity(name): weight for name, weight in SEVERITY_WEIGHTS.items()
        }
        self._floor = floor

    def score(self, findings: list[Finding], n_slides: int) -> int:
        slides = max(1, n_slides)
        total_weight = sum(self._weights.get(f.severity, 0) for f in findings)
        raw_score = 100 - (total_weight / slides)
        return max(self._floor, min(100, round(raw_score)))
