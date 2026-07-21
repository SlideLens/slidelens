"""Product analytics events (ADR 0007 layer 1)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event


class EventTracker:
    """Inserts ``Event`` rows. Call from services, not routes."""

    async def track(
        self,
        session: AsyncSession,
        user_id: UUID | None,
        name: str,
        **props: Any,
    ) -> Event:
        event = Event(user_id=user_id, name=name, properties=dict(props))
        session.add(event)
        await session.flush()
        return event
