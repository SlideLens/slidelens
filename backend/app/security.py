"""Password hashing and JWT helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.config import Settings

_password_hash = PasswordHash.recommended()

TokenType = Literal["access", "refresh", "file"]


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_token(
    *,
    user_id: UUID,
    token_type: TokenType,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        if token_type == "access":
            expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
        elif token_type == "refresh":
            expires_delta = timedelta(days=settings.refresh_token_expire_days)
        else:
            expires_delta = timedelta(days=2)

    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "typ": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm="HS256")


def decode_token(token: str, settings: Settings, *, expected_type: TokenType) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exc:
        msg = "Invalid or expired token"
        raise ValueError(msg) from exc

    if payload.get("typ") != expected_type:
        msg = "Invalid token type"
        raise ValueError(msg)

    sub = payload.get("sub")
    if not sub:
        msg = "Token missing subject"
        raise ValueError(msg)
    return UUID(str(sub))


def create_file_token(asset_id: UUID, settings: Settings) -> str:
    """Short-lived signed token scoped to one FileAsset (for ``?sig=`` <img> access)."""
    expires_delta = timedelta(minutes=settings.file_signature_expire_minutes)
    return create_token(
        user_id=asset_id,
        token_type="file",
        settings=settings,
        expires_delta=expires_delta,
    )


def decode_file_token(token: str, settings: Settings) -> UUID:
    """Inverse of ``create_file_token`` — returns the signed ``asset_id``."""
    return decode_token(token, settings, expected_type="file")
