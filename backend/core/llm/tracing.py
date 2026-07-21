"""Langfuse span helper — no-op when keys are missing (keeps core testable)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langfuse import Langfuse  # type: ignore

from core.llm.schemas import FakeSpan


class RecordingTracer:
    """In-memory tracer used in unit tests."""

    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []

    @contextmanager
    def span(self, name: str, *, metadata: dict[str, Any] | None = None) -> Iterator[FakeSpan]:
        s = FakeSpan(name=name, metadata=dict(metadata or {}))
        self.spans.append(s)
        try:
            yield s
        finally:
            s.end()


class NullTracer:
    @contextmanager
    def span(self, name: str, *, metadata: dict[str, Any] | None = None) -> Iterator[FakeSpan]:
        s = FakeSpan(name=name, metadata=dict(metadata or {}))
        try:
            yield s
        finally:
            s.end()


def build_tracer(
    *,
    public_key: str = "",
    secret_key: str = "",
    host: str = "",
    recording: RecordingTracer | None = None,
) -> RecordingTracer | NullTracer:
    if recording is not None:
        return recording
    if not (public_key and secret_key):
        return NullTracer()

    client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host or None,
    )

    class LangfuseTracer:
        @contextmanager
        def span(
            self, name: str, *, metadata: dict[str, Any] | None = None
        ) -> Iterator[FakeSpan]:
            # Prefer generation/span API if available; wrap as FakeSpan-compatible.
            generation = None
            try:
                generation = client.start_generation(
                    name=name, metadata=metadata or {}
                )
            except Exception:
                generation = None
            s = FakeSpan(name=name, metadata=dict(metadata or {}))
            try:
                yield s
            finally:
                if generation is not None:
                    try:
                        if s.usage:
                            generation.update(usage=s.usage)
                        if s.output is not None:
                            generation.update(output=s.output)
                        generation.end()
                    except Exception:
                        pass
                s.end()

    return LangfuseTracer()  # type: ignore[return-value]
