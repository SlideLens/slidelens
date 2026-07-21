"""Unit tests for ``core.analyzers.crossmodal.CrossModalAnalyzer``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.analyzers.crossmodal import (
    CrossModalAnalyzer,
    _align_slide_windows,
    _delivery_findings,
    _pacing_findings,
    analyze_rehearsal,
    classify_slide_pacing,
    windows_from_slide_timings,
)
from core.constants import SLIDE_TOO_LONG_SECONDS, SLIDE_TOO_SHORT_SECONDS
from core.context import ReviewContext
from core.schemas import Category, DeliveryMetrics, SlideTiming, TranscriptSegment


class _FakeAudioExtractor:
    def __init__(self, wav_path: Path) -> None:
        self._wav_path = wav_path
        self.calls = 0

    async def extract(self, media: Path, workdir: Path) -> Path:
        self.calls += 1
        return self._wav_path


class _FakeMismatchLLM:
    def __init__(
        self,
        *,
        response: dict[str, Any],
        transcribe_segments: list[TranscriptSegment] | None = None,
    ) -> None:
        self._response = response
        self._transcribe_segments = transcribe_segments or []
        self.calls = 0
        self.transcribe_calls = 0

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[Any],
        *,
        system: str | None = None,
        tier: str = "full",
        prompt_version: str | None = None,
        ctx: Any = None,
    ) -> Any:
        self.calls += 1
        return response_model.model_validate(self._response)

    async def transcribe_audio(
        self, audio_path: Path, *, language: str = "ru", ctx: Any = None
    ) -> list[TranscriptSegment]:
        self.transcribe_calls += 1
        return self._transcribe_segments


def _ctx_with_slide(tmp_path: Path, *, slide_text: str) -> ReviewContext:
    ctx = ReviewContext(workdir=tmp_path, audio_path=tmp_path / "pitch.mp4")
    png = tmp_path / "slide_001.png"
    png.write_bytes(b"fake")
    ctx.slide_pngs[1] = png
    ctx.meta["slide_texts"] = {1: slide_text}
    return ctx


@pytest.mark.asyncio
async def test_no_audio_returns_empty_without_calls(tmp_path: Path) -> None:
    ctx = ReviewContext(workdir=tmp_path)
    extractor = _FakeAudioExtractor(tmp_path / "a.wav")
    llm = _FakeMismatchLLM(response={"contradicts": False})

    findings = await CrossModalAnalyzer(llm, audio_extractor=extractor).analyze(ctx)

    assert findings == []
    assert extractor.calls == 0
    assert llm.calls == 0
    assert llm.transcribe_calls == 0


@pytest.mark.asyncio
async def test_speech_mismatch_found_on_contradiction(tmp_path: Path) -> None:
    ctx = _ctx_with_slide(tmp_path, slide_text="Выручка выросла на 30%")
    wav_path = tmp_path / "a.wav"
    segments = [TranscriptSegment(start=0.0, end=5.0, text="На самом деле мы теряем деньги")]
    llm = _FakeMismatchLLM(
        response={
            "contradicts": True,
            "finding": {
                "category": "TYPOGRAPHY",
                "severity": "MAJOR",
                "title": "Расхождение",
                "description": "Спикер утверждает обратное",
                "fix_suggestion": "Свериться с данными",
            },
        },
        transcribe_segments=segments,
    )

    findings = await CrossModalAnalyzer(
        llm, audio_extractor=_FakeAudioExtractor(wav_path)
    ).analyze(ctx)

    mismatches = [f for f in findings if f.category == Category.SPEECH_MISMATCH]
    assert len(mismatches) == 1
    assert mismatches[0].slide_num == 1
    assert mismatches[0].category == Category.SPEECH_MISMATCH  # forced, not TYPOGRAPHY
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_no_speech_mismatch_without_contradiction(tmp_path: Path) -> None:
    ctx = _ctx_with_slide(tmp_path, slide_text="Выручка выросла на 30%")
    segments = [TranscriptSegment(start=0.0, end=5.0, text="Всё верно, рост подтверждён")]
    llm = _FakeMismatchLLM(response={"contradicts": False}, transcribe_segments=segments)

    findings = await CrossModalAnalyzer(
        llm, audio_extractor=_FakeAudioExtractor(tmp_path / "a.wav")
    ).analyze(ctx)

    assert not any(f.category == Category.SPEECH_MISMATCH for f in findings)


@pytest.mark.asyncio
async def test_empty_transcript_returns_no_findings(tmp_path: Path) -> None:
    ctx = _ctx_with_slide(tmp_path, slide_text="Текст")
    llm = _FakeMismatchLLM(response={"contradicts": False})

    findings = await CrossModalAnalyzer(
        llm, audio_extractor=_FakeAudioExtractor(tmp_path / "a.wav")
    ).analyze(ctx)

    assert findings == []
    assert llm.calls == 0


def test_delivery_findings_flags_fast_pace() -> None:
    delivery = DeliveryMetrics(words_per_minute=220.0, filler_words={}, long_pauses=[])
    findings = _delivery_findings(delivery)
    assert any("быстрый" in f.title for f in findings)


def test_delivery_findings_flags_slow_pace() -> None:
    delivery = DeliveryMetrics(words_per_minute=60.0, filler_words={}, long_pauses=[])
    findings = _delivery_findings(delivery)
    assert any("медленный" in f.title for f in findings)


def test_delivery_findings_comfortable_pace_no_finding() -> None:
    delivery = DeliveryMetrics(words_per_minute=140.0, filler_words={}, long_pauses=[])
    findings = _delivery_findings(delivery)
    assert findings == []


def test_delivery_findings_zero_wpm_skips_pace_check() -> None:
    delivery = DeliveryMetrics(words_per_minute=0.0, filler_words={}, long_pauses=[])
    findings = _delivery_findings(delivery)
    assert findings == []


def test_delivery_findings_filler_threshold() -> None:
    delivery = DeliveryMetrics(
        words_per_minute=140.0, filler_words={"ну": 3, "короче": 3}, long_pauses=[]
    )
    findings = _delivery_findings(delivery)
    assert any("паразит" in f.title for f in findings)


def test_windows_from_slide_timings_maps_precisely() -> None:
    timings = [
        SlideTiming(slide_num=1, start=0.0, end=12.5),
        SlideTiming(slide_num=2, start=12.5, end=40.0),
    ]
    assert windows_from_slide_timings(timings) == {1: (0.0, 12.5), 2: (12.5, 40.0)}


def test_classify_slide_pacing_swamp_stub_and_normal() -> None:
    assert classify_slide_pacing(SLIDE_TOO_LONG_SECONDS) == "swamp"
    assert classify_slide_pacing(SLIDE_TOO_SHORT_SECONDS) == "stub"
    assert classify_slide_pacing((SLIDE_TOO_LONG_SECONDS + SLIDE_TOO_SHORT_SECONDS) / 2) is None


@pytest.mark.asyncio
async def test_analyze_rehearsal_uses_precise_windows_for_mismatch() -> None:
    segments = [TranscriptSegment(start=0.0, end=5.0, text="На самом деле мы теряем деньги")]
    timings = [SlideTiming(slide_num=1, start=0.0, end=5.0)]
    llm = _FakeMismatchLLM(
        response={
            "contradicts": True,
            "finding": {
                "category": "TYPOGRAPHY",
                "severity": "MAJOR",
                "title": "Расхождение",
                "description": "Спикер утверждает обратное",
                "fix_suggestion": "Свериться с данными",
            },
        }
    )

    delivery, findings = await analyze_rehearsal(
        llm,
        segments=segments,
        slide_timings=timings,
        slide_texts={1: "Выручка выросла на 30%"},
    )

    assert delivery.words_per_minute > 0
    mismatches = [f for f in findings if f.category == Category.SPEECH_MISMATCH]
    assert len(mismatches) == 1
    assert mismatches[0].slide_num == 1
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_analyze_rehearsal_flags_swamp_and_stub_as_findings() -> None:
    timings = [
        SlideTiming(slide_num=1, start=0.0, end=SLIDE_TOO_LONG_SECONDS + 10),
        SlideTiming(
            slide_num=2,
            start=SLIDE_TOO_LONG_SECONDS + 10,
            end=SLIDE_TOO_LONG_SECONDS + 10 + SLIDE_TOO_SHORT_SECONDS - 1,
        ),
    ]
    llm = _FakeMismatchLLM(response={"contradicts": False})

    _delivery, findings = await analyze_rehearsal(
        llm, segments=[], slide_timings=timings, slide_texts={}
    )

    assert any(f.slide_num == 1 and "много времени" in f.title for f in findings)
    assert any(f.slide_num == 2 and "быстро" in f.title for f in findings)


@pytest.mark.asyncio
async def test_analyze_rehearsal_isolates_per_slide_llm_failure() -> None:
    """One slide's LLM call raising must not drop pacing/delivery findings for the rest."""
    segments = [
        TranscriptSegment(start=0.0, end=5.0, text="Текст один"),
        TranscriptSegment(start=200.0, end=205.0, text="Текст два"),
    ]
    timings = [
        SlideTiming(slide_num=1, start=0.0, end=10.0),
        SlideTiming(slide_num=2, start=10.0, end=SLIDE_TOO_LONG_SECONDS + 20),
    ]

    class _FailingLLM(_FakeMismatchLLM):
        async def complete_structured(self, *args: object, **kwargs: object) -> object:
            self.calls += 1
            raise RuntimeError("402 budget exceeded")

    llm = _FailingLLM(response={"contradicts": False})

    delivery, findings = await analyze_rehearsal(
        llm,
        segments=segments,
        slide_timings=timings,
        slide_texts={1: "Слайд 1", 2: "Слайд 2"},
    )

    assert delivery.words_per_minute > 0
    assert not any(f.category == Category.SPEECH_MISMATCH for f in findings)
    assert any(f.slide_num == 2 and "много времени" in f.title for f in findings)


def test_delivery_findings_below_filler_threshold_no_finding() -> None:
    delivery = DeliveryMetrics(words_per_minute=140.0, filler_words={"ну": 1}, long_pauses=[])
    findings = _delivery_findings(delivery)
    assert not any("паразит" in f.title for f in findings)


def test_delivery_findings_long_pauses() -> None:
    delivery = DeliveryMetrics(words_per_minute=140.0, filler_words={}, long_pauses=[12.0])
    findings = _delivery_findings(delivery)
    assert any("паузы" in f.title.lower() for f in findings)


def test_pacing_findings_too_long_recommends_split() -> None:
    findings = _pacing_findings(3, 0.0, 200.0)
    assert findings[0].category == Category.NARRATIVE
    assert findings[0].slide_num == 3
    assert "раздел" in findings[0].description.lower()


def test_pacing_findings_too_short_recommends_cut() -> None:
    findings = _pacing_findings(5, 0.0, 5.0)
    assert findings[0].slide_num == 5
    assert "убер" in findings[0].fix_suggestion.lower()


def test_pacing_findings_comfortable_duration_no_finding() -> None:
    findings = _pacing_findings(2, 0.0, 60.0)
    assert findings == []


def test_align_slide_windows_uniform_baseline() -> None:
    segments = [TranscriptSegment(start=0.0, end=10.0, text="слово")]
    windows = _align_slide_windows(segments, [1, 2], {})
    assert windows[1] == (0.0, 5.0)
    assert windows[2] == (5.0, 10.0)


def test_align_slide_windows_keyword_snap_overrides_baseline() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=2.0, text="начало"),
        TranscriptSegment(start=8.0, end=9.0, text="упоминаем Ромашка"),
    ]
    windows = _align_slide_windows(segments, [1, 2], {2: "Компания Ромашка"})
    assert windows[2] == (8.0, 9.0)


def test_align_slide_windows_empty_segments_returns_empty() -> None:
    assert _align_slide_windows([], [1, 2], {}) == {}
