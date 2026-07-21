"""Auth HTTP routes under ``/api/v1/auth``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthError, authenticate_user, refresh_tokens, register_user
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user, get_event_tracker
from app.models import User
from app.schemas import AuthTokens, LoginRequest, RefreshRequest, RegisterRequest, UserOut
from app.services.events import EventTracker

router = APIRouter(prefix="/auth", tags=["auth"])


def _raise_auth(exc: AuthError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/register", response_model=AuthTokens, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    event_tracker: Annotated[EventTracker, Depends(get_event_tracker)],
) -> AuthTokens:
    try:
        return await register_user(
            session,
            email=str(body.email),
            password=body.password,
            settings=settings,
            event_tracker=event_tracker,
        )
    except AuthError as exc:
        _raise_auth(exc)
        raise  # pragma: no cover


@router.post("/login", response_model=AuthTokens)
async def login(
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthTokens:
    try:
        return await authenticate_user(
            session,
            email=str(body.email),
            password=body.password,
            settings=settings,
        )
    except AuthError as exc:
        _raise_auth(exc)
        raise  # pragma: no cover


@router.post("/refresh", response_model=AuthTokens)
async def refresh(
    body: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthTokens:
    try:
        return await refresh_tokens(session, refresh_token=body.refresh_token, settings=settings)
    except AuthError as exc:
        _raise_auth(exc)
        raise  # pragma: no cover


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(user)
