"""Request-scoped identifiers for logs / Langfuse / metrics."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

_review_id: ContextVar[str | None] = ContextVar("review_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)


def get_review_id() -> str | None:
    return _review_id.get()


def get_user_id() -> str | None:
    return _user_id.get()


def bind_context(*, review_id: str | UUID | None = None, user_id: str | UUID | None = None) -> None:
    if review_id is not None:
        _review_id.set(str(review_id))
    if user_id is not None:
        _user_id.set(str(user_id))


def clear_context() -> None:
    _review_id.set(None)
    _user_id.set(None)


@contextmanager
def review_context(
    *,
    review_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
) -> Iterator[None]:
    tokens = []
    if review_id is not None:
        tokens.append(_review_id.set(str(review_id)))
    if user_id is not None:
        tokens.append(_user_id.set(str(user_id)))
    try:
        yield
    finally:
        clear_context()
