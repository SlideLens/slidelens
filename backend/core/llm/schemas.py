"""Pydantic data models shared by ``core.llm`` modules (no provider SDK, no I/O)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Prompt(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    body: str


class FakeSpan(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    input: Any = None
    output: Any = None
    usage: dict[str, Any] = Field(default_factory=dict)
    ended: bool = False

    def end(self) -> None:
        self.ended = True
