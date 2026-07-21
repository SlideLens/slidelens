"""REST API v1 routers under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.api.v1.files import router as files_router
from app.api.v1.findings import router as findings_router
from app.api.v1.rehearsals import router as rehearsals_router
from app.api.v1.reviews import router as reviews_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(reviews_router)
api_router.include_router(rehearsals_router)
api_router.include_router(files_router)
api_router.include_router(findings_router)
api_router.include_router(events_router)

__all__ = ["api_router"]
