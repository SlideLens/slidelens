"""Резервирование и возврат Разборов: бесплатные пробные + купленный пакет."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.exceptions import LimitExceededError


class CreditSource(StrEnum):
    """Кошелёк, из которого списан Разбор (``reviews.credit_source``)."""

    FREE = "free"
    BALANCE = "balance"
    ADMIN = "admin"


class LimitService:
    """Атомарная проверка/резерв/возврат Разборов по двум кошелькам."""

    async def check_and_reserve(self, session: AsyncSession, user_id: UUID) -> tuple[User, str]:
        """Списывает один Разбор и возвращает пользователя и кошелёк списания.

        Порядок важен: сначала тратим бесплатные пробные, и только потом купленные —
        иначе пользователь, купивший пакет, потеряет неиспользованный триал.
        """
        result = await session.execute(select(User).where(User.id == user_id).with_for_update())
        user = result.scalar_one()
        if user.is_admin:
            return user, CreditSource.ADMIN.value

        for source, column in (
            (CreditSource.FREE, User.free_reviews_left),
            (CreditSource.BALANCE, User.balance_reviews),
        ):
            # Условный декремент одним запросом — гонка двух параллельных загрузок
            # не может увести счётчик в минус ни на Postgres, ни на SQLite.
            updated = await session.execute(
                update(User)
                .where(User.id == user_id, column > 0)
                .values({column: column - 1})
                .returning(User)
            )
            reserved = updated.scalar_one_or_none()
            if reserved is not None:
                await session.refresh(reserved)
                return reserved, source.value

        raise LimitExceededError()

    async def refund(self, session: AsyncSession, user_id: UUID, source: str | None) -> User:
        """Возвращает Разбор в тот же кошелёк, из которого он был списан."""
        result = await session.execute(select(User).where(User.id == user_id).with_for_update())
        user = result.scalar_one()
        if source == CreditSource.FREE.value:
            user.free_reviews_left += 1
        elif source == CreditSource.BALANCE.value:
            user.balance_reviews += 1
        # ADMIN и None ничего не списывали — возвращать нечего.
        await session.flush()
        return user
