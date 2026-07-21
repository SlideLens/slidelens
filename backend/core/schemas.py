"""Pydantic contracts for the review pipeline (pure data, no I/O or logic).

``Category`` / ``Severity`` are the single source of truth for taxonomy —
import them from here everywhere (ORM, API, UI generation). JSON Schema for
prompts: ``Model.model_json_schema()``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Category(StrEnum):
    """Finding taxonomy — exactly the CONTEXT.md set."""

    TYPOGRAPHY = "TYPOGRAPHY"
    HIERARCHY = "HIERARCHY"
    READABILITY = "READABILITY"
    CONSISTENCY = "CONSISTENCY"
    CHART = "CHART"
    NARRATIVE = "NARRATIVE"
    SPEECH_MISMATCH = "SPEECH_MISMATCH"
    DELIVERY = "DELIVERY"


class Severity(StrEnum):
    """Finding priority — drives score weights and annotation color."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class BBox(BaseModel):
    """Normalized slide region ``0..1`` (dpi-independent)."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(ge=0.0, le=1.0)
    h: float = Field(ge=0.0, le=1.0)


class Finding(BaseModel):
    """One problem found in the deck (analyzer / aggregate output)."""

    id: UUID = Field(default_factory=uuid4)
    slide_num: int | None = Field(
        default=None,
        description="1-based slide index; None = deck-level finding",
    )
    category: Category
    severity: Severity
    title: str = Field(max_length=80)
    description: str
    fix_suggestion: str
    bbox: BBox | None = None
    auto_fixable: bool = False
    auto_fixed: bool = False
    source: str | None = Field(
        default=None,
        description="Analyzer name (BaseAnalyzer.name)",
    )


class TranscriptSegment(BaseModel):
    """Timed speech fragment from faster-whisper."""

    start: float = Field(ge=0.0, description="Start time in seconds")
    end: float = Field(ge=0.0, description="End time in seconds")
    text: str


class SlideTiming(BaseModel):
    """When the speaker was on a given slide (rehearsal / alignment)."""

    slide_num: int = Field(ge=1)
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)


class DeliveryMetrics(BaseModel):
    """Delivery / presenting metrics derived from the transcript."""

    words_per_minute: float = Field(ge=0.0)
    filler_words: dict[str, int] = Field(default_factory=dict)
    long_pauses: list[float] = Field(
        default_factory=list,
        description="Timestamps (s) of pauses longer than 3 seconds",
    )


class ChartSeries(BaseModel):
    """One data series read from a chart image."""

    label: str
    values: list[float | int]


class ChartReading(BaseModel):
    """Structured reading of a chart before honesty checks."""

    chart_type: str
    y_axis_starts_at_zero: bool
    series: list[ChartSeries] = Field(default_factory=list)
    value_labels_present: bool = False


class SuspiciousRegion(BaseModel):
    """ZoomAgent screening hit — crop and re-analyze at full tier."""

    bbox: BBox
    reason: str


class ReviewResult(BaseModel):
    """Aggregate pipeline output for a single review run."""

    findings: list[Finding] = Field(default_factory=list)
    score: int | None = Field(default=None, ge=0, le=100)
    n_slides: int | None = Field(default=None, ge=0)
    delivery: DeliveryMetrics | None = None
    total_cost_rub: float | None = Field(default=None, ge=0.0)
    meta: dict[str, Any] = Field(default_factory=dict)
