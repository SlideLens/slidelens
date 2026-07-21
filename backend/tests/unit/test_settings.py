"""Tests for Settings fail-fast behaviour and DB URL assembly."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_missing_required_env_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    for key in (
        "DATABASE_URL",
        "DB_PASSWORD",
        "REDIS_URL",
        "SECRET_KEY",
        "LLM_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("LLM_API_KEY", "x")
    # DB_PASSWORD intentionally missing; ignore on-disk .env
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "db_password" in str(exc.value).lower()


def test_settings_load_with_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "db.internal")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "slidelens")
    monkeypatch.setenv("DB_USER", "slidelens")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "key")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.llm_model_full
    assert settings.file_expire_days == 7
    assert (
        settings.database_url.get_secret_value()
        == "postgresql+asyncpg://slidelens:secret@db.internal:5433/slidelens"
    )


def test_database_url_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DB_PASSWORD", "ignored")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "key")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url.get_secret_value() == "sqlite+aiosqlite:///:memory:"


def test_database_url_encodes_special_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "slidelens")
    monkeypatch.setenv("DB_USER", "user@name")
    monkeypatch.setenv("DB_PASSWORD", "p@ss/word")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "key")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    url = settings.database_url.get_secret_value()
    assert url == "postgresql+asyncpg://user%40name:p%40ss%2Fword@localhost:5432/slidelens"
