"""Shared pytest fixtures and ENV defaults for app imports."""

from __future__ import annotations

import os

import pytest


def pytest_configure() -> None:
    """Set required ENV before test modules import ``app.main``."""
    os.environ.setdefault("DB_PASSWORD", "p")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("LLM_API_KEY", "test-key")
    os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(autouse=True)
def _default_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "db")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("ENVIRONMENT", "test")

    from app.config import get_settings

    get_settings.cache_clear()
