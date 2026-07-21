"""Pydantic request DTOs for Events (mirrors OpenAPI)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
