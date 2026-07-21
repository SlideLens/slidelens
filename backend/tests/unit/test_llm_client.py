"""Unit tests for LLMClient with a mocked OpenAI-compatible async SDK."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from pydantic import BaseModel

from core.context import ReviewContext
from core.llm.client import LLMClient
from core.llm.config import LLMConfig
from core.llm.tracing import RecordingTracer
from core.schemas import TranscriptSegment


class TinyOut(BaseModel):
    ok: bool


class RateLimitError(Exception):
    status_code = 429


class FakeCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.last_kwargs: dict | None = None

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls += 1
        self.last_kwargs = dict(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[return-value]

    async def parse(self, **kwargs: object) -> SimpleNamespace:
        """Mimic OpenAI ``chat.completions.parse`` (sets ``message.parsed``)."""
        response_format = kwargs.get("response_format")
        result = await self.create(**kwargs)
        message = result.choices[0].message
        content = message.content or ""
        parsed = None
        if (
            isinstance(response_format, type)
            and issubclass(response_format, BaseModel)
            and content.strip()
        ):
            try:
                parsed = response_format.model_validate_json(content)
            except Exception:  # noqa: BLE001 — mirror SDK leaving parsed=None
                parsed = None
        message.parsed = parsed
        message.refusal = None
        return result


class FakeTranscriptions:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls = 0
        self.last_kwargs: dict | None = None

    async def create(self, **kwargs: object) -> object:
        self.calls += 1
        self.last_kwargs = dict(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeOpenAI:
    def __init__(self, responses: list[object], *, transcription_response: object = None) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))
        self.audio = SimpleNamespace(transcriptions=FakeTranscriptions(transcription_response))


def _transcription_response(
    text: str, segments: list[tuple[float, float, str]], *, duration: float
) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        duration=duration,
        segments=[SimpleNamespace(start=s, end=e, text=t) for s, e, t in segments],
    )


def _text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text, parsed=None, refusal=None)
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def _json_response(payload: dict) -> SimpleNamespace:
    return _text_response(json.dumps(payload))


def _png(tmp_path: Path) -> Path:
    path = tmp_path / "slide.png"
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
    )
    return path


async def test_complete_text_returns_raw_string() -> None:
    fake = FakeOpenAI([_text_response("  hello world  ")])
    client = LLMClient(LLMConfig(api_key="test"), openai_client=fake, tracer=RecordingTracer())
    assert await client.complete_text("say hi") == "hello world"
    assert fake.chat.completions.last_kwargs is not None
    assert "response_format" not in fake.chat.completions.last_kwargs


async def test_complete_structured_valid_json() -> None:
    fake = FakeOpenAI([_json_response({"ok": True})])
    client = LLMClient(LLMConfig(api_key="test"), openai_client=fake, tracer=RecordingTracer())
    out = await client.complete_structured("prompt", TinyOut)
    assert out.ok is True
    assert fake.chat.completions.last_kwargs["response_format"] is TinyOut


async def test_complete_structured_invalid_then_retry() -> None:
    fake = FakeOpenAI(
        [
            _json_response({"ok": "nope"}),
            _json_response({"ok": True}),
        ]
    )
    client = LLMClient(LLMConfig(api_key="test"), openai_client=fake, tracer=RecordingTracer())
    out = await client.complete_structured("prompt", TinyOut)
    assert out.ok is True
    assert fake.chat.completions.calls == 2


async def test_complete_vision_text_returns_raw_string(tmp_path: Path) -> None:
    fake = FakeOpenAI([_text_response("slide looks fine")])
    client = LLMClient(LLMConfig(api_key="test"), openai_client=fake, tracer=RecordingTracer())
    text = await client.complete_vision_text([_png(tmp_path)], "describe")
    assert text == "slide looks fine"
    content = fake.chat.completions.last_kwargs["messages"][-1]["content"]
    assert any(part.get("type") == "image_url" for part in content)
    assert "response_format" not in fake.chat.completions.last_kwargs


async def test_complete_vision_structured(tmp_path: Path) -> None:
    fake = FakeOpenAI([_json_response({"ok": True})])
    client = LLMClient(LLMConfig(api_key="test"), openai_client=fake, tracer=RecordingTracer())
    out = await client.complete_vision_structured([_png(tmp_path)], "prompt", TinyOut)
    assert out.ok is True


async def test_rate_limit_backoff_on_structured() -> None:
    fake = FakeOpenAI(
        [
            RateLimitError("429"),
            _json_response({"ok": True}),
        ]
    )
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = LLMClient(
        LLMConfig(api_key="test", max_retries_rate_limit=2),
        openai_client=fake,
        tracer=RecordingTracer(),
        sleep=record_sleep,
    )
    out = await client.complete_structured("prompt", TinyOut)
    assert out.ok is True
    assert sleeps == [1.0]
    assert fake.chat.completions.calls == 2


async def test_span_includes_review_id_and_cost(tmp_path: Path) -> None:
    tracer = RecordingTracer()
    ctx = ReviewContext(workdir=tmp_path, review_id=UUID("123e4567-e89b-12d3-a456-426614174000"))
    client = LLMClient(
        LLMConfig(api_key="test"),
        openai_client=FakeOpenAI([_json_response({"ok": True})]),
        tracer=tracer,
    )
    await client.complete_vision_structured(
        [_png(tmp_path)],
        "prompt",
        TinyOut,
        prompt_version="1",
        ctx=ctx,
    )
    assert tracer.spans[0].metadata["review_id"] == str(ctx.review_id)
    assert tracer.spans[0].metadata["prompt_version"] == "1"
    assert ctx.total_cost_rub > 0


async def test_transcribe_audio_returns_segments_and_strips_text(tmp_path: Path) -> None:
    audio_path = tmp_path / "a.wav"
    audio_path.write_bytes(b"fake-audio")
    fake = FakeOpenAI(
        [],
        transcription_response=_transcription_response(
            "привет мир",
            [(0.0, 1.5, " привет "), (1.5, 3.0, "мир")],
            duration=3.0,
        ),
    )
    client = LLMClient(LLMConfig(api_key="test"), openai_client=fake, tracer=RecordingTracer())

    segments = await client.transcribe_audio(audio_path)

    assert segments == [
        TranscriptSegment(start=0.0, end=1.5, text="привет"),
        TranscriptSegment(start=1.5, end=3.0, text="мир"),
    ]
    assert fake.audio.transcriptions.last_kwargs["model"] == "whisper-1"
    assert fake.audio.transcriptions.last_kwargs["language"] == "ru"
    assert fake.audio.transcriptions.last_kwargs["response_format"] == "verbose_json"


async def test_transcribe_audio_uses_configured_model(tmp_path: Path) -> None:
    audio_path = tmp_path / "a.wav"
    audio_path.write_bytes(b"fake-audio")
    fake = FakeOpenAI([], transcription_response=_transcription_response("hi", [], duration=1.0))
    client = LLMClient(
        LLMConfig(api_key="test", model_transcription="custom-whisper"),
        openai_client=fake,
        tracer=RecordingTracer(),
    )

    await client.transcribe_audio(audio_path)

    assert fake.audio.transcriptions.last_kwargs["model"] == "custom-whisper"


async def test_transcribe_audio_tracks_cost_on_ctx(tmp_path: Path) -> None:
    audio_path = tmp_path / "a.wav"
    audio_path.write_bytes(b"fake-audio")
    ctx = ReviewContext(workdir=tmp_path)
    fake = FakeOpenAI(
        [], transcription_response=_transcription_response("hi", [(0.0, 60.0, "hi")], duration=60.0)
    )
    client = LLMClient(LLMConfig(api_key="test"), openai_client=fake, tracer=RecordingTracer())

    await client.transcribe_audio(audio_path, ctx=ctx)

    assert ctx.total_cost_rub > 0


def test_openai_import_only_in_client() -> None:
    root = Path(__file__).resolve().parents[2] / "core"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "client.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "import openai" in text or "from openai" in text:
            offenders.append(str(path))
    assert offenders == []
