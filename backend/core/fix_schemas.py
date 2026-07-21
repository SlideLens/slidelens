"""Pydantic result/log schemas for ``core.fix``."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class FixResult(BaseModel):
    applied: bool
    reason: str = ""


class FixLogEntry(BaseModel):
    finding_id: UUID
    rule: str | None = None
    status: str  # "applied" | "skipped"
    reason: str = ""
