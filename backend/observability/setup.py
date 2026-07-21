"""Initialize logging, tracing exporters, and custom metrics."""

from __future__ import annotations

import logging
from typing import Any

import structlog
from prometheus_client import Counter, Gauge, Histogram

from observability.context import get_review_id, get_user_id

PIPELINE_STEP_DURATION = Histogram(
    "pipeline_step_duration_seconds",
    "Duration of a review pipeline step",
    labelnames=("step",),
)
REVIEW_COST_RUB = Counter(
    "review_cost_rub",
    "Accumulated estimated VLM cost in RUB",
)
QUEUE_DEPTH = Gauge(
    "queue_depth",
    "Current review queue depth",
)
REVIEWS_TOTAL = Counter(
    "reviews_total",
    "Reviews by terminal/status label",
    labelnames=("status",),
)


def _add_contextvars(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    rid = get_review_id()
    uid = get_user_id()
    if rid:
        event_dict["review_id"] = rid
    if uid:
        event_dict["user_id"] = uid
    return event_dict


def setup_logging(*, json_logs: bool = True) -> None:
    """Configure structlog JSON logging with contextvars processors."""
    shared = [
        structlog.contextvars.merge_contextvars,
        _add_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_logs:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def setup_sentry(dsn: str, *, environment: str = "development") -> bool:
    """Init Sentry when DSN is set. Returns True if initialized."""
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(dsn=dsn, environment=environment, traces_sample_rate=0.0)
    return True


def setup_metrics() -> None:
    """Ensure custom collectors are registered (import side-effect)."""
    _ = (
        PIPELINE_STEP_DURATION,
        REVIEW_COST_RUB,
        QUEUE_DEPTH,
        REVIEWS_TOTAL,
    )


def observe_review_cost(rub: float) -> None:
    REVIEW_COST_RUB.inc(max(0.0, rub))


def observe_pipeline_step(step: str, duration_seconds: float) -> None:
    PIPELINE_STEP_DURATION.labels(step=step).observe(max(0.0, duration_seconds))


def set_queue_depth(depth: int) -> None:
    QUEUE_DEPTH.set(max(0, depth))


def observe_review_status(status: str) -> None:
    REVIEWS_TOTAL.labels(status=status).inc()
