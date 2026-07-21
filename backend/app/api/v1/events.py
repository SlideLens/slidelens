"""Events HTTP routes under ``/api/v1/events``."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user, get_event_tracker
from app.models import User
from app.schemas import EventIn
from app.services.events import EventTracker

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def track_events(
    events: list[EventIn],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    event_tracker: Annotated[EventTracker, Depends(get_event_tracker)],
) -> None:
    for event in events:
        try:
            await event_tracker.track(session, user.id, event.name, **event.properties)
        except TypeError:
            # `properties` is client-controlled and may collide with track()'s own
            # parameter names (e.g. {"session": ...}) — drop that one event, not the batch.
            logger.warning("event_track_skipped", name=event.name)
    await session.commit()
