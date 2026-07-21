"""Pydantic response/finding-in schemas shared across analyzer modules.

Kept separate from the analyzer classes themselves so each analyzer file only
holds behavior; schemas that started in one analyzer and got reused by
another (``SlideAnalysisResponse``, ``LabelConsistencyResponse``) now have one
home instead of a cross-module import from whichever analyzer defined them.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from core.geometry import box_2d_to_bbox
from core.schemas import BBox, Category, Severity

_BOX_2D_FIELD = Field(
    default=None,
    description="[ymin, xmin, ymax, xmax], целые 0..1000 — родной формат рамок Gemini",
)


class SlideFindingIn(BaseModel):
    """One finding as emitted by the VLM — slide_num/id/source filled in by us.

    Shared by ``SlideAnalyzer``, ``ZoomAgent`` (re-analyzes crops with this
    same schema) and ``ChartChecker``/``CrossModalAnalyzer`` (contradiction
    checks via ``LabelConsistencyResponse``).

    Рамку модель отдаёт как ``box_2d`` — это её родной формат, а не наш ``BBox``;
    пересчёт делает :func:`core.geometry.box_2d_to_bbox` в ``as_finding_fields``.
    """

    category: Category
    severity: Severity
    title: str = Field(max_length=80)
    description: str
    fix_suggestion: str
    box_2d: list[int] | None = _BOX_2D_FIELD
    auto_fixable: bool = False

    def as_bbox(self) -> BBox | None:
        return box_2d_to_bbox(self.box_2d)

    def as_finding_fields(self) -> dict[str, Any]:
        """Поля для ``Finding.model_validate`` — с рамкой уже в координатах слайда."""
        return {**self.model_dump(exclude={"box_2d"}), "bbox": self.as_bbox()}


class SlideAnalysisResponse(BaseModel):
    findings: list[SlideFindingIn] = Field(default_factory=list)
    has_chart: bool = False


class SuspiciousRegionIn(BaseModel):
    box_2d: list[int] | None = _BOX_2D_FIELD
    reason: str

    def as_bbox(self) -> BBox | None:
        return box_2d_to_bbox(self.box_2d)


class ScreeningResponse(BaseModel):
    regions: list[SuspiciousRegionIn] = Field(default_factory=list)


class DeckFindingIn(BaseModel):
    """One finding as emitted by the VLM — the model supplies its own slide_num.

    Рамки здесь нет намеренно: DeckAnalyzer судит о Деке целиком и о связях между
    слайдами, показать пальцем на область одного слайда он не может.
    """

    slide_num: int | None = None
    category: Category
    severity: Severity
    title: str = Field(max_length=80)
    description: str
    fix_suggestion: str
    auto_fixable: bool = False


class DeckAnalysisResponse(BaseModel):
    findings: list[DeckFindingIn] = Field(default_factory=list)


class LabelConsistencyResponse(BaseModel):
    """``{contradicts, finding}`` — reused by ``ChartChecker`` and ``CrossModalAnalyzer``."""

    contradicts: bool = False
    finding: SlideFindingIn | None = None


__all__ = [
    "DeckAnalysisResponse",
    "DeckFindingIn",
    "LabelConsistencyResponse",
    "ScreeningResponse",
    "SlideAnalysisResponse",
    "SlideFindingIn",
    "SuspiciousRegionIn",
]
