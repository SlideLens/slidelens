"""Pydantic request/response DTOs for Reviews (mirrors OpenAPI)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import ReviewStatus
from core.schemas import BBox, Category, DeliveryMetrics, Severity


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ReviewStatus
    score: int | None = None
    fail_reason: str | None = None
    deck_filename: str
    n_slides: int | None = None
    has_audio: bool
    has_data: bool
    created_at: datetime
    finished_at: datetime | None = None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slide_num: int | None
    category: Category
    severity: Severity
    title: str
    description: str
    fix_suggestion: str
    bbox: BBox | None
    screenshot_asset_id: UUID | None
    screenshot_url: str | None = None
    auto_fixable: bool
    auto_fixed: bool
    source: str | None
    user_flag: bool
    user_like: bool


class SlideOut(BaseModel):
    slide_num: int
    url: str


class ReportOut(BaseModel):
    review_id: UUID
    score: int = Field(ge=0, le=100)
    n_slides: int
    findings: list[FindingOut] = Field(default_factory=list)
    delivery: DeliveryMetrics | None = None
    auto_fixed_count: int = 0
    pdf_asset_id: UUID | None = None
    fixed_pptx_asset_id: UUID | None = None
    fixed_pptx_filename: str | None = None
