"""Unit tests for app.security's file-signing helpers."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from app.config import Settings, get_settings
from app.security import create_file_token, create_token, decode_file_token, decode_token


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("FILE_SIGNATURE_EXPIRE_MINUTES", "15")
    get_settings.cache_clear()
    return get_settings()


def test_file_token_round_trips(settings: Settings) -> None:
    asset_id = uuid4()
    token = create_file_token(asset_id, settings)
    assert decode_file_token(token, settings) == asset_id


def test_file_token_expired_raises(settings: Settings) -> None:
    asset_id = uuid4()
    token = create_token(
        user_id=asset_id,
        token_type="file",
        settings=settings,
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(ValueError):
        decode_file_token(token, settings)


def test_file_token_rejected_by_access_decode(settings: Settings) -> None:
    asset_id = uuid4()
    token = create_file_token(asset_id, settings)
    with pytest.raises(ValueError):
        decode_token(token, settings, expected_type="access")


def test_access_token_rejected_by_file_decode(settings: Settings) -> None:
    user_id = uuid4()
    token = create_token(user_id=user_id, token_type="access", settings=settings)
    with pytest.raises(ValueError):
        decode_file_token(token, settings)
