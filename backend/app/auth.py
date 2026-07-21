"""Auth domain helpers: register, login, refresh, verify."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import User, UserPlan
from app.schemas import AuthTokens, UserOut
from app.security import create_token, hash_password, verify_password
from app.services.events import EventTracker


class AuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def tokens_for_user(user: User, settings: Settings) -> AuthTokens:
    return AuthTokens(
        access_token=create_token(user_id=user.id, token_type="access", settings=settings),
        refresh_token=create_token(user_id=user.id, token_type="refresh", settings=settings),
        user=UserOut.model_validate(user),
    )


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    settings: Settings,
    event_tracker: EventTracker,
) -> AuthTokens:
    existing = await session.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise AuthError("Email уже зарегистрирован", status_code=409)

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        plan=UserPlan.FREE.value,
        free_reviews_left=2,
        email_verified=True,
        is_admin=email.lower() in settings.admin_email_set,
    )
    session.add(user)
    await session.flush()

    await event_tracker.track(session, user.id, "signup")
    await session.commit()
    await session.refresh(user)
    return tokens_for_user(user, settings)


async def authenticate_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    settings: Settings,
) -> AuthTokens:
    result = await session.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Неверный email или пароль", status_code=401)

    # Self-heals accounts registered before ADMIN_EMAILS listed them (or after
    # the list changed) without needing a manual DB fix.
    should_be_admin = user.email in settings.admin_email_set
    if user.is_admin != should_be_admin:
        user.is_admin = should_be_admin
        await session.commit()
        await session.refresh(user)

    return tokens_for_user(user, settings)


async def refresh_tokens(
    session: AsyncSession,
    *,
    refresh_token: str,
    settings: Settings,
) -> AuthTokens:
    from app.security import decode_token

    try:
        user_id = decode_token(refresh_token, settings, expected_type="refresh")
    except ValueError as exc:
        raise AuthError(str(exc), status_code=401) from exc

    user = await session.get(User, user_id)
    if user is None:
        raise AuthError("Пользователь не найден", status_code=401)
    return tokens_for_user(user, settings)


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)
