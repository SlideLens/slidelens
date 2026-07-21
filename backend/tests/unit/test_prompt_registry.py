"""Unit tests for PromptRegistry."""

from __future__ import annotations

from core.llm.prompts import PromptRegistry


def test_prompt_registry_loads_slide_analysis() -> None:
    prompt = PromptRegistry().get("slide_analysis")
    assert "сеньор-дизайнер" in prompt.body
