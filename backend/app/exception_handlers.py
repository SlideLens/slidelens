"""Centralized FastAPI exception handlers."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = structlog.get_logger(__name__)


def _format_validation_errors(errors: list[Any]) -> str:
    parts: list[str] = []
    for error in errors:
        loc = ".".join(str(item) for item in error.get("loc", ()))
        msg = error.get("msg", "")
        err_type = error.get("type", "")
        parts.append(f"{loc}: {msg} ({err_type})" if loc else f"{msg} ({err_type})")
    return "; ".join(parts) if parts else "Validation error"


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(
        "http_exception",
        path=request.url.path,
        status_code=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    message = _format_validation_errors(exc.errors())
    logger.warning(
        "request_validation_error",
        path=request.url.path,
        message=message,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": message, "errors": exc.errors()},
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, ValidationError):
        message = _format_validation_errors(exc.errors())
    else:
        message = str(exc)
    logger.warning(
        "validation_error",
        path=request.url.path,
        message=message,
        error_type=exc.__class__.__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": message},
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unexpected_error",
        path=request.url.path,
        error_type=exc.__class__.__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
