"""``CrossModalAnalyzer`` — speech ↔ slides and Подача (delivery) feedback.

Skipped cleanly when no audio is attached. Alignment of transcript to slides is
an MVP heuristic (even distribution + keyword/number snapping); precise
``SlideTiming`` is phase 4 (ADR 0005).
"""

from __future__ import annotations

import asyncio
import re
from typing import Literal

from core.analyzers.base import BaseAnalyzer
from core.analyzers.schemas import LabelConsistencyResponse
from core.constants import (
    FILLER_COUNT_THRESHOLD,
    LONG_PAUSE_SECONDS,
    MAX_COMFORTABLE_WPM,
    MIN_COMFORTABLE_WPM,
    SLIDE_TOO_LONG_SECONDS,
    SLIDE_TOO_SHORT_SECONDS,
)
from core.context import ReviewContext
from core.ingest import AudioExtractor
from core.llm import LLMClient, PromptRegistry, default_registry
from core.schemas import (
    Category,
    DeliveryMetrics,
    Finding,
    Severity,
    SlideTiming,
    TranscriptSegment,
)
from core.transcribe import compute_delivery

_KEYWORD_RE = re.compile(r"\w+", re.UNICODE)


def _extract_keywords(text: str) -> set[str]:
    words = _KEYWORD_RE.findall(text)
    return {w for w in words if (w.isdigit() and len(w) >= 2) or (w[0].isupper() and len(w) > 3)}


def _align_slide_windows(
    segments: list[TranscriptSegment],
    slide_nums: list[int],
    slide_texts: dict[int, str],
) -> dict[int, tuple[float, float]]:
    if not segments or not slide_nums:
        return {}
    total_start = segments[0].start
    total_end = segments[-1].end
    duration = total_end - total_start
    if duration <= 0:
        return {}

    n = len(slide_nums)
    per_slide = duration / n
    windows = {
        slide_nums[i]: (total_start + i * per_slide, total_start + (i + 1) * per_slide)
        for i in range(n)
    }

    for slide_num in slide_nums:
        keywords = _extract_keywords(slide_texts.get(slide_num, ""))
        if not keywords:
            continue
        matches = [seg for seg in segments if _extract_keywords(seg.text) & keywords]
        if matches:
            windows[slide_num] = (
                min(seg.start for seg in matches),
                max(seg.end for seg in matches),
            )
    return windows


def _delivery_findings(delivery: DeliveryMetrics) -> list[Finding]:
    findings: list[Finding] = []
    wpm = delivery.words_per_minute
    if wpm > 0 and not (MIN_COMFORTABLE_WPM <= wpm <= MAX_COMFORTABLE_WPM):
        pace = "слишком быстрый" if wpm > MAX_COMFORTABLE_WPM else "слишком медленный"
        findings.append(
            Finding(
                category=Category.DELIVERY,
                severity=Severity.MINOR,
                title=f"Темп речи {pace}",
                description=(
                    f"Темп речи {wpm:.0f} слов/мин, комфортный диапазон "
                    f"{MIN_COMFORTABLE_WPM:.0f}-{MAX_COMFORTABLE_WPM:.0f}."
                ),
                fix_suggestion="Отрепетируйте темп речи, ориентируясь на комфортный диапазон.",
            )
        )

    total_fillers = sum(delivery.filler_words.values())
    if total_fillers >= FILLER_COUNT_THRESHOLD:
        top = sorted(delivery.filler_words.items(), key=lambda kv: -kv[1])[:3]
        top_str = ", ".join(f"{word} ({count})" for word, count in top)
        findings.append(
            Finding(
                category=Category.DELIVERY,
                severity=Severity.MINOR,
                title="Много слов-паразитов в речи",
                description=f"Всего {total_fillers} слов-паразитов, чаще всего: {top_str}.",
                fix_suggestion="Потренируйтесь делать паузу вместо слов-паразитов.",
            )
        )

    if delivery.long_pauses:
        findings.append(
            Finding(
                category=Category.DELIVERY,
                severity=Severity.MINOR,
                title="Длинные паузы в речи",
                description=(
                    f"Обнаружено {len(delivery.long_pauses)} пауз(ы) длиннее "
                    f"{LONG_PAUSE_SECONDS:.0f} с."
                ),
                fix_suggestion="Сократите паузы или замените их явным переходом к следующей мысли.",
            )
        )
    return findings


def windows_from_slide_timings(timings: list[SlideTiming]) -> dict[int, tuple[float, float]]:
    """Precise per-slide (start, end) windows from a browser-recorded rehearsal — replaces
    ``_align_slide_windows``'s heuristic when the exact timing is known (ADR 0005, phase 4)."""
    return {t.slide_num: (t.start, t.end) for t in timings}


def classify_slide_pacing(duration_seconds: float) -> Literal["swamp", "stub"] | None:
    """"Болото" (spent too long) / "заглушка" (skipped too fast) — same thresholds as
    ``_pacing_findings``, exposed standalone for the rehearsal timing-map view."""
    if duration_seconds >= SLIDE_TOO_LONG_SECONDS:
        return "swamp"
    if duration_seconds <= SLIDE_TOO_SHORT_SECONDS:
        return "stub"
    return None


def _pacing_findings(slide_num: int, start: float, end: float) -> list[Finding]:
    duration = end - start
    if duration >= SLIDE_TOO_LONG_SECONDS:
        return [
            Finding(
                slide_num=slide_num,
                category=Category.NARRATIVE,
                severity=Severity.MINOR,
                title="Слайду уделено слишком много времени",
                description=(
                    f"На слайде {slide_num} спикер провёл {duration / 60:.1f} мин — "
                    "стоит разделить его на несколько слайдов."
                ),
                fix_suggestion="Разбейте слайд на 2, чтобы облегчить подачу.",
            )
        ]
    if duration <= SLIDE_TOO_SHORT_SECONDS:
        return [
            Finding(
                slide_num=slide_num,
                category=Category.NARRATIVE,
                severity=Severity.MINOR,
                title="Слайд пролистан слишком быстро",
                description=(
                    f"Слайд {slide_num} показан {duration:.0f} с — возможно, он не нужен "
                    "или дублирует соседний."
                ),
                fix_suggestion="Уберите слайд или объедините его с соседним.",
            )
        ]
    return []


class CrossModalAnalyzer(BaseAnalyzer):
    """Speech↔slide mismatch + delivery/pacing feedback. No-op without audio."""

    name = "crossmodal_analyzer"

    def __init__(
        self,
        llm: LLMClient,
        *,
        prompts: PromptRegistry | None = None,
        audio_extractor: AudioExtractor | None = None,
    ) -> None:
        self._llm = llm
        self._prompts = prompts or default_registry()
        self._audio_extractor = audio_extractor or AudioExtractor()

    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        if ctx.audio_path is None:
            return []

        wav_path = await self._audio_extractor.extract(ctx.audio_path, ctx.workdir)
        segments = await self._llm.transcribe_audio(wav_path, ctx=ctx)
        if not segments:
            return []

        delivery = compute_delivery(segments)
        ctx.step_results["delivery"] = delivery
        findings = _delivery_findings(delivery)

        slide_nums = sorted(ctx.slide_pngs.keys())
        slide_texts = ctx.meta.get("slide_texts", {})
        windows = _align_slide_windows(segments, slide_nums, slide_texts)

        for slide_num, (start, end) in windows.items():
            findings.extend(_pacing_findings(slide_num, start, end))

        mismatch_findings = await asyncio.gather(
            *(
                self._check_speech_mismatch(ctx, slide_num, segments, window)
                for slide_num, window in windows.items()
            )
        )
        findings.extend(f for f in mismatch_findings if f is not None)
        return findings

    async def _check_speech_mismatch(
        self,
        ctx: ReviewContext,
        slide_num: int,
        segments: list[TranscriptSegment],
        window: tuple[float, float],
    ) -> Finding | None:
        slide_text = ctx.meta.get("slide_texts", {}).get(slide_num) or ""
        return await _check_speech_mismatch_text(
            self._llm,
            self._prompts,
            slide_num=slide_num,
            slide_text=slide_text,
            segments=segments,
            window=window,
            ctx=ctx,
        )


async def _check_speech_mismatch_text(
    llm: LLMClient,
    prompts: PromptRegistry,
    *,
    slide_num: int,
    slide_text: str,
    segments: list[TranscriptSegment],
    window: tuple[float, float],
    ctx: ReviewContext | None = None,
) -> Finding | None:
    start, end = window
    matched = [seg for seg in segments if start <= seg.start < end]
    if not matched:
        return None
    if not slide_text.strip():
        return None

    speech_text = " ".join(seg.text for seg in matched)
    system_prompt = prompts.get("crossmodal_check").body
    prompt = f"Текст слайда:\n{slide_text}\n\nРечь в этот момент:\n{speech_text}"
    response = await llm.complete_structured(
        prompt, LabelConsistencyResponse, system=system_prompt, tier="full", ctx=ctx
    )
    if not response.contradicts or response.finding is None:
        return None

    return Finding.model_validate(
        {
            **response.finding.as_finding_fields(),
            "slide_num": slide_num,
            "category": Category.SPEECH_MISMATCH,
        }
    )


async def analyze_rehearsal(
    llm: LLMClient,
    *,
    prompts: PromptRegistry | None = None,
    segments: list[TranscriptSegment],
    slide_timings: list[SlideTiming],
    slide_texts: dict[int, str],
    ctx: ReviewContext | None = None,
) -> tuple[DeliveryMetrics, list[Finding]]:
    """Rehearsal-flavored cross-modal pass (П3): precise ``SlideTiming`` from the browser
    recording instead of ``_align_slide_windows``'s MVP heuristic. Delivery metrics and
    pacing ("болота"/"заглушки") are deterministic; only the per-slide mismatch check calls
    the LLM, and a failure there is isolated per-slide so one bad call doesn't drop the rest.
    """
    prompts = prompts or default_registry()
    delivery = compute_delivery(segments)
    findings = _delivery_findings(delivery)

    windows = windows_from_slide_timings(slide_timings)
    for slide_num, window in windows.items():
        findings.extend(_pacing_findings(slide_num, *window))

    async def _safe_check(slide_num: int, window: tuple[float, float]) -> Finding | None:
        try:
            return await _check_speech_mismatch_text(
                llm,
                prompts,
                slide_num=slide_num,
                slide_text=slide_texts.get(slide_num, ""),
                segments=segments,
                window=window,
                ctx=ctx,
            )
        except Exception:  # noqa: BLE001 - one slide's LLM failure must not drop the rest
            return None

    mismatch_findings = await asyncio.gather(
        *(_safe_check(slide_num, window) for slide_num, window in windows.items())
    )
    findings.extend(f for f in mismatch_findings if f is not None)
    return delivery, findings
