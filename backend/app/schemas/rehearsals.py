"""Pydantic request/response DTOs for Rehearsals (П2-П4, mirrors OpenAPI)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import RehearsalStatus
from core.schemas import Category, DeliveryMetrics, Severity


class SlideTimingIn(BaseModel):
    """One slide's (start, end) in seconds, captured by the browser recorder."""

    slide_num: int = Field(ge=1)
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)


class RehearsalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    review_id: UUID
    status: RehearsalStatus
    fail_reason: str | None = None
    attempt_num: int
    created_at: datetime
    finished_at: datetime | None = None


class TimingMapEntryOut(BaseModel):
    """One slide's window in the rehearsal timing map, with pacing classification (П3)."""

    slide_num: int
    start: float
    end: float
    duration: float
    pacing: Literal["swamp", "stub"] | None = None


class RehearsalFindingOut(BaseModel):
    """Rehearsal-only Находка (pacing / SPEECH_MISMATCH) — plain, not a DB FindingRow."""

    id: UUID
    slide_num: int | None
    category: Category
    severity: Severity
    title: str
    description: str
    fix_suggestion: str


class RehearsalDeltaOut(BaseModel):
    """Delta vs. the previous *done* attempt on the same Review (П4)."""

    previous_attempt_num: int
    words_per_minute_delta: float
    filler_words_delta: int
    long_pauses_delta: int


class RehearsalReportOut(BaseModel):
    rehearsal_id: UUID
    review_id: UUID
    attempt_num: int
    status: RehearsalStatus
    fail_reason: str | None = None
    delivery: DeliveryMetrics | None = None
    timing_map: list[TimingMapEntryOut] = Field(default_factory=list)
    findings: list[RehearsalFindingOut] = Field(default_factory=list)
    delta: RehearsalDeltaOut | None = None
