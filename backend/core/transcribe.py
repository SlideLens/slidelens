"""Deterministic delivery metrics from a transcript.

Transcription itself goes through ``LLMClient.transcribe_audio`` (same OpenAI-compatible
provider as everything else — no local model to download). ``compute_delivery`` stays a
pure function here since it needs no LLM.
"""

from __future__ import annotations

import re

from core.constants import FILLER_WORDS, LONG_PAUSE_SECONDS
from core.schemas import DeliveryMetrics, TranscriptSegment

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def compute_delivery(segments: list[TranscriptSegment]) -> DeliveryMetrics:
    """Pure function: words/min, filler-word counts (RU/EN), pauses > 3s. No I/O."""
    if not segments:
        return DeliveryMetrics(words_per_minute=0.0, filler_words={}, long_pauses=[])

    full_text_lower = " ".join(seg.text for seg in segments).lower()
    total_words = len(_WORD_RE.findall(full_text_lower))

    filler_words: dict[str, int] = {}
    for filler in FILLER_WORDS:
        pattern = rf"(?<!\w){re.escape(filler)}(?!\w)"
        count = len(re.findall(pattern, full_text_lower))
        if count:
            filler_words[filler] = count

    duration_minutes = (segments[-1].end - segments[0].start) / 60.0
    words_per_minute = total_words / duration_minutes if duration_minutes > 0 else 0.0

    long_pauses = [
        segments[i].end
        for i in range(len(segments) - 1)
        if segments[i + 1].start - segments[i].end > LONG_PAUSE_SECONDS
    ]

    return DeliveryMetrics(
        words_per_minute=words_per_minute,
        filler_words=filler_words,
        long_pauses=long_pauses,
    )
