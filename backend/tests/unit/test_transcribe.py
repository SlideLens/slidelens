"""Unit tests for ``core.transcribe`` (compute_delivery). Transcription itself is tested
in ``test_llm_client.py`` (``LLMClient.transcribe_audio``)."""

from __future__ import annotations

from core.schemas import TranscriptSegment
from core.transcribe import compute_delivery


def test_compute_delivery_empty_segments() -> None:
    metrics = compute_delivery([])
    assert metrics.words_per_minute == 0.0
    assert metrics.filler_words == {}
    assert metrics.long_pauses == []


def test_compute_delivery_counts_filler_words() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=2.0, text="ну короче это важная функция"),
        TranscriptSegment(start=2.0, end=4.0, text="ну и в общем всё готово"),
    ]
    metrics = compute_delivery(segments)

    assert metrics.filler_words["ну"] == 2
    assert metrics.filler_words["короче"] == 1
    assert metrics.filler_words["в общем"] == 1


def test_compute_delivery_counts_english_filler_words() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=2.0, text="So um I mean this is kind of important"),
        TranscriptSegment(start=2.0, end=4.0, text="you know basically uh the same idea"),
    ]
    metrics = compute_delivery(segments)

    assert metrics.filler_words["um"] == 1
    assert metrics.filler_words["uh"] == 1
    assert metrics.filler_words["i mean"] == 1
    assert metrics.filler_words["kind of"] == 1
    assert metrics.filler_words["you know"] == 1
    assert metrics.filler_words["basically"] == 1


def test_compute_delivery_detects_long_pause() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=2.0, text="первая фраза"),
        TranscriptSegment(start=6.5, end=8.0, text="вторая фраза после паузы"),
    ]
    metrics = compute_delivery(segments)

    assert metrics.long_pauses == [2.0]


def test_compute_delivery_no_pause_below_threshold() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=2.0, text="первая"),
        TranscriptSegment(start=4.0, end=5.0, text="вторая"),
    ]
    metrics = compute_delivery(segments)

    assert metrics.long_pauses == []


def test_compute_delivery_words_per_minute() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=60.0, text="один два три четыре пять"),
    ]
    metrics = compute_delivery(segments)

    assert metrics.words_per_minute == 5.0
