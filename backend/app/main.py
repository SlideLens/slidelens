"""ASGI entrypoint: FastAPI application factory and ``app`` for uvicorn."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import ValidationError

from app.api.v1 import api_router
from app.api.v1.health import router as health_router
from app.config import Settings, get_settings
from app.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
from app.middleware import RequestLoggingMiddleware
from observability.setup import setup_logging, setup_metrics, setup_sentry

logger = structlog.get_logger(__name__)


def _resolve_static_dir(settings: Settings) -> Path | None:
    """Return SPA dist path if present (prod image), else None (API-only / Vite dev)."""
    static_dir = settings.static_dir
    if static_dir is None:
        return None
    if not static_dir.is_dir() or not (static_dir / "index.html").is_file():
        return None
    return static_dir


def _is_under(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _mount_spa(application: FastAPI, static_dir: Path) -> None:
    """Serve Vite build: assets + SPA fallback (ADR 0004 — single origin via Caddy→app)."""
    assets = static_dir / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="spa-assets")

    index = static_dir / "index.html"

    @application.get("/", include_in_schema=False)
    async def spa_index() -> FileResponse:
        return FileResponse(index)

    @application.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        target = static_dir / full_path
        if full_path and target.is_file() and _is_under(static_dir, target):
            return FileResponse(target)
        return FileResponse(index)


def _fastapi_kwargs(settings: Settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "title": settings.app_name,
        "description": settings.app_description,
        "version": settings.app_version,
    }
    if not settings.docs_enabled:
        kwargs["docs_url"] = None
        kwargs["redoc_url"] = None
        kwargs["openapi_url"] = None
    return kwargs


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(json_logs=settings.environment != "development")
    setup_sentry(settings.sentry_dsn, environment=settings.environment)
    setup_metrics()
    logger.info(
        "application_startup",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    try:
        yield
    finally:
        logger.info("application_shutdown", app=settings.app_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()

    application = FastAPI(lifespan=lifespan, **_fastapi_kwargs(settings))

    if settings.cors_origins and settings.environment != "production":
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.add_middleware(GZipMiddleware, minimum_size=1000)
    application.add_middleware(RequestLoggingMiddleware)

    instrumentator = Instrumentator()
    instrumentator.instrument(application)
    instrumentator.expose(application, endpoint="/metrics", include_in_schema=False)

    application.include_router(health_router)
    application.include_router(api_router, prefix="/api/v1")

    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    application.add_exception_handler(ValueError, validation_exception_handler)
    application.add_exception_handler(ValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unexpected_exception_handler)

    # SPA last so /api, /health, /metrics keep precedence (registered above).
    static_dir = _resolve_static_dir(settings)
    if static_dir is not None:
        _mount_spa(application, static_dir)
        logger.info("spa_static_mounted", path=str(static_dir))

    return application


app = create_app()
