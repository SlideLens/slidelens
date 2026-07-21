"""Helpers for ``LLMClient`` (no provider SDK imports)."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from core.llm.config import ModelPrice


def estimate_cost_rub(price: ModelPrice, input_tokens: int, output_tokens: int) -> float:
    """Стоимость одного вызова в рублях по ставкам конкретной модели."""
    return (
        max(0, input_tokens) * price.input_rub_per_mtok
        + max(0, output_tokens) * price.output_rub_per_mtok
    ) / 1_000_000


def estimate_asr_cost_rub(rub_per_minute: float, duration_seconds: float) -> float:
    return max(0.0, duration_seconds) / 60.0 * rub_per_minute


def image_url_part(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    media = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.standard_b64encode(data).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media};base64,{encoded}"},
    }


def is_rate_limit_error(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    if status in (429, 529):
        return True
    text = str(exc).lower()
    return "429" in text or "529" in text or "rate limit" in text

