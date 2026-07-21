"""Unit tests for app.services.langfuse_scoring.score_finding_flag."""

from __future__ import annotations

from uuid import uuid4

import pytest

import app.services.langfuse_scoring as langfuse_scoring
from app.config import Settings, get_settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    get_settings.cache_clear()
    return get_settings()


def test_noop_when_keys_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    settings = get_settings()

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("Langfuse client should not be constructed when keys are unset")

    monkeypatch.setattr(langfuse_scoring, "Langfuse", boom)

    langfuse_scoring.score_finding_flag(
        settings,
        finding_id=uuid4(),
        review_id=uuid4(),
        category="TYPOGRAPHY",
        source="slide_analyzer",
    )


def test_calls_create_score_when_configured(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    class FakeLangfuse:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def create_score(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(langfuse_scoring, "Langfuse", FakeLangfuse)

    langfuse_scoring.score_finding_flag(
        settings,
        finding_id=uuid4(),
        review_id=uuid4(),
        category="TYPOGRAPHY",
        source="slide_analyzer",
    )
    assert len(calls) == 1
    assert calls[0]["name"] == "finding_flagged"


def test_langfuse_exception_is_swallowed(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BoomingLangfuse:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def create_score(self, **kwargs: object) -> None:
            raise RuntimeError("network down")

    monkeypatch.setattr(langfuse_scoring, "Langfuse", BoomingLangfuse)

    # Must not raise.
    langfuse_scoring.score_finding_flag(
        settings,
        finding_id=uuid4(),
        review_id=uuid4(),
        category="TYPOGRAPHY",
        source="slide_analyzer",
    )
