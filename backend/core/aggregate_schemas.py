"""Pydantic response schema(s) for ``core.aggregate``."""

from __future__ import annotations

from pydantic import BaseModel


class SameIssueResponse(BaseModel):
    same_issue: bool = False
