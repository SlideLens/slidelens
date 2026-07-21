"""``ReportOut`` — pydantic view-model for ``core.report``.

Mirrors ``api/openapi.yaml``'s ``ReportOut`` schema (source of truth) minus the
DB-only asset-id/user-flag fields on ``Finding`` (both optional there, so a
core ``Finding`` without them still validates). Asset-id fields on
``ReportOut`` itself stay ``None`` until the (future) worker persists a Review.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from core.schemas import DeliveryMetrics, Finding


class ReportOut(BaseModel):
    """View-model matching ``api/openapi.yaml``'s ``ReportOut`` schema."""

    review_id: UUID
    score: int = Field(ge=0, le=100)
    n_slides: int
    findings: list[Finding] = Field(default_factory=list)
    delivery: DeliveryMetrics | None = None
    auto_fixed_count: int = 0
    pdf_asset_id: UUID | None = None
    fixed_pptx_asset_id: UUID | None = None
