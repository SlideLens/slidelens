"""Prompt registry — plain markdown files under ``core/prompts/``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from core.llm.schemas import Prompt

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptRegistry:
    """Load prompts from ``core/prompts/{name}.md``."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or PROMPTS_DIR

    def get(self, name: str) -> Prompt:
        path = self._dir / f"{name}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt not found: {path}")
        body = path.read_text(encoding="utf-8").strip()
        return Prompt(name=name, body=body)


@lru_cache
def default_registry() -> PromptRegistry:
    return PromptRegistry()
