"""FastAPI dependencies (current user, DB session, shared services)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_user_by_id
from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
from app.security import decode_token
from app.services.email import EmailService
from app.services.events import EventTracker
from app.services.storage import LocalStorage, StorageBackend

_bearer = HTTPBearer(auto_error=False)


def get_email_service(settings: Annotated[Settings, Depends(get_settings)]) -> EmailService:
    return EmailService(settings)


def get_event_tracker() -> EventTracker:
    return EventTracker()


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> StorageBackend:
    return LocalStorage(settings.storage_root)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    try:
        user_id = decode_token(credentials.credentials, settings, expected_type="access")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    return user


async def get_current_user_optional(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    """Like ``get_current_user``, but returns ``None`` instead of raising 401."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        user_id = decode_token(credentials.credentials, settings, expected_type="access")
    except ValueError:
        return None
    return await get_user_by_id(session, user_id)
