"""OpenAI-compatible async LLM client — the only module that imports the provider SDK."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from core.context import ReviewContext
from core.llm.config import LLMConfig
from core.llm.tracing import build_tracer
from core.llm.utils import (
    estimate_asr_cost_rub,
    estimate_cost_rub,
    image_url_part,
    is_rate_limit_error,
)
from core.schemas import TranscriptSegment

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Single async entry for all LLM / VLM calls via an OpenAI-compatible API."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        openai_client: Any | None = None,
        tracer: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._config = config
        self._client = openai_client or AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )
        self._tracer = tracer or build_tracer()
        self._sleep = sleep or asyncio.sleep
        self._owns_client = openai_client is None

    async def aclose(self) -> None:
        """Close the underlying HTTP client when this instance created it."""
        if self._owns_client:
            await self._client.close()

    async def complete_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tier: str = "full",
        prompt_version: str | None = None,
        ctx: ReviewContext | None = None,
    ) -> str:
        """Text-only completion — returns raw assistant text."""
        return await self._complete(
            prompt,
            system=system,
            images=None,
            response_model=None,
            tier=tier,
            prompt_version=prompt_version,
            ctx=ctx,
            span_name="llm.complete_text",
        )

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[T],
        *,
        system: str | None = None,
        tier: str = "full",
        prompt_version: str | None = None,
        ctx: ReviewContext | None = None,
    ) -> T:
        """Text-only completion validated against a pydantic schema."""
        return await self._complete(
            prompt,
            system=system,
            images=None,
            response_model=response_model,
            tier=tier,
            prompt_version=prompt_version,
            ctx=ctx,
            span_name="llm.complete_structured",
        )

    async def complete_vision_text(
        self,
        images: list[Path],
        prompt: str,
        *,
        system: str | None = None,
        tier: str = "full",
        prompt_version: str | None = None,
        ctx: ReviewContext | None = None,
    ) -> str:
        """Vision completion — image(s) + prompt, raw text only (no JSON schema)."""
        if not images:
            raise ValueError("complete_vision_text requires at least one image")
        return await self._complete(
            prompt,
            system=system,
            images=images,
            response_model=None,
            tier=tier,
            prompt_version=prompt_version,
            ctx=ctx,
            span_name="llm.complete_vision_text",
        )

    async def complete_vision_structured(
        self,
        images: list[Path],
        prompt: str,
        response_model: type[T],
        *,
        system: str | None = None,
        tier: str = "full",
        prompt_version: str | None = None,
        ctx: ReviewContext | None = None,
    ) -> T:
        """Vision completion validated against a pydantic schema."""
        if not images:
            raise ValueError("complete_vision_structured requires at least one image")
        return await self._complete(
            prompt,
            system=system,
            images=images,
            response_model=response_model,
            tier=tier,
            prompt_version=prompt_version,
            ctx=ctx,
            span_name="llm.complete_vision_structured",
        )

    async def transcribe_audio(
        self,
        audio_path: Path,
        *,
        language: str = "ru",
        ctx: ReviewContext | None = None,
    ) -> list[TranscriptSegment]:
        """Speech-to-text via the same OpenAI-compatible provider — no local model/download.

        Uses ``response_format="verbose_json"`` for per-segment timestamps, which the rest
        of the pipeline (``compute_delivery``, cross-modal window matching) depends on.
        """
        metadata = {"model": self._config.model_transcription, "mode": "llm.transcribe_audio"}
        if ctx and ctx.review_id:
            metadata["review_id"] = str(ctx.review_id)

        with self._tracer.span("llm.transcribe_audio", metadata=metadata) as span:
            span.input = {"audio_path": str(audio_path), "language": language}
            with audio_path.open("rb") as audio_file:
                response = await self._client.audio.transcriptions.create(
                    model=self._config.model_transcription,
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                )
            segments = [
                TranscriptSegment(start=float(seg.start), end=float(seg.end), text=seg.text.strip())
                for seg in (response.segments or [])
            ]
            duration_seconds = float(getattr(response, "duration", 0.0) or 0.0)
            cost = estimate_asr_cost_rub(
                self._config.asr_price_for(self._config.model_transcription), duration_seconds
            )
            span.output = response.text
            span.usage = {"duration_seconds": duration_seconds, "cost_rub": cost}
            if ctx is not None:
                ctx.add_cost(cost)
            return segments

    async def _complete(
        self,
        prompt: str,
        *,
        system: str | None,
        images: list[Path] | None,
        response_model: type[BaseModel] | None,
        tier: str,
        prompt_version: str | None,
        ctx: ReviewContext | None,
        span_name: str,
    ) -> Any:
        model = self._config.model_for_tier(tier)
        metadata = {
            "tier": tier,
            "model": model,
            "prompt_version": prompt_version or "",
            "mode": span_name,
        }
        if ctx and ctx.review_id:
            metadata["review_id"] = str(ctx.review_id)

        messages = self._build_messages(prompt, system=system, images=images)

        with self._tracer.span(span_name, metadata=metadata) as span:
            span.input = {
                "prompt": prompt,
                "n_images": len(images or []),
                "structured": response_model is not None,
            }
            raw_text, usage = await self._chat_with_retries(
                model=model,
                messages=messages,
                response_model=response_model,
            )
            if response_model is not None:
                try:
                    parsed = response_model.model_validate_json(raw_text)
                except (ValidationError, json.JSONDecodeError) as first_err:
                    repair_messages = self._build_messages(
                        f"{prompt}\n\nPrevious response failed validation:\n{first_err}\n"
                        "Reply with corrected JSON only.",
                        system=system,
                        images=images,
                    )
                    raw_text, usage2 = await self._chat_with_retries(
                        model=model,
                        messages=repair_messages,
                        response_model=response_model,
                    )
                    usage = {
                        "input_tokens": usage.get("input_tokens", 0)
                        + usage2.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0)
                        + usage2.get("output_tokens", 0),
                    }
                    parsed = response_model.model_validate_json(raw_text)
                result = parsed
            else:
                result = raw_text.strip()

            # Ставки берём по фактически вызванной модели: full и screening
            # тарифицируются по-разному, и разница между ними кратная.
            cost = estimate_cost_rub(
                self._config.price_for(model),
                int(usage.get("input_tokens", 0)),
                int(usage.get("output_tokens", 0)),
            )
            span.output = raw_text
            span.usage = {**usage, "cost_rub": cost}
            if ctx is not None:
                ctx.add_cost(cost)
            return result

    def _build_messages(
        self,
        prompt: str,
        *,
        system: str | None,
        images: list[Path] | None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        if images:
            content: list[dict[str, Any]] = [image_url_part(p) for p in images]
            content.append({"type": "text", "text": prompt})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})
        return messages

    async def _chat_with_retries(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        response_model: type[BaseModel] | None,
    ) -> tuple[str, dict[str, int]]:
        last_exc: BaseException | None = None
        attempts = self._config.max_retries_rate_limit + 1
        for attempt in range(attempts):
            try:
                if response_model is not None:
                    # SDK builds a strict JSON schema (incl. additionalProperties: false).
                    # Do not pass model_json_schema() manually — providers reject it.
                    response = await self._client.chat.completions.parse(
                        model=model,
                        messages=messages,
                        temperature=0,
                        response_format=response_model,
                    )
                    message = response.choices[0].message
                    if getattr(message, "refusal", None):
                        raise ValueError(f"Model refused: {message.refusal}")
                    parsed = getattr(message, "parsed", None)
                    if parsed is not None:
                        text = message.content or parsed.model_dump_json()
                    else:
                        text = message.content or ""
                else:
                    response = await self._client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0,
                    )
                    text = response.choices[0].message.content or ""
                if not text.strip():
                    raise ValueError("Empty model response")
                usage_obj = response.usage
                usage = {
                    "input_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
                    "output_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
                }
                return text, usage
            except Exception as exc:  # noqa: BLE001 — classified below
                last_exc = exc
                if is_rate_limit_error(exc) and attempt < attempts - 1:
                    await self._sleep(2**attempt)
                    continue
                raise
        assert last_exc is not None
        raise last_exc
