"""Best-effort, free-standing Langfuse scores (no per-Finding trace id — see design.md #4).

No-ops when Langfuse keys are unset (same pattern as ``core.llm.tracing.build_tracer``),
and never raises — a Langfuse outage must not fail the request that triggered the score.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from langfuse import Langfuse

from app.config import Settings

logger = structlog.get_logger(__name__)


def _score(
    settings: Settings,
    *,
    name: str,
    finding_id: UUID,
    review_id: UUID,
    category: str,
    source: str | None,
) -> None:
    secret = settings.langfuse_secret_key.get_secret_value() if settings.langfuse_secret_key else ""
    if not (settings.langfuse_public_key and secret):
        return
    try:
        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=secret,
            host=settings.langfuse_host or None,
        )
        client.create_score(
            name=name,
            value=1,
            data_type="CATEGORICAL",
            comment=(
                f"category={category} source={source or 'unknown'} "
                f"finding_id={finding_id} review_id={review_id}"
            ),
        )
    except Exception as exc:  # noqa: BLE001 - best-effort telemetry, never fail the request
        logger.warning("langfuse_score_failed", finding_id=str(finding_id), error=str(exc))


def score_finding_flag(
    settings: Settings,
    *,
    finding_id: UUID,
    review_id: UUID,
    category: str,
    source: str | None,
) -> None:
    _score(
        settings,
        name="finding_flagged",
        finding_id=finding_id,
        review_id=review_id,
        category=category,
        source=source,
    )


def score_finding_like(
    settings: Settings,
    *,
    finding_id: UUID,
    review_id: UUID,
    category: str,
    source: str | None,
) -> None:
    _score(
        settings,
        name="finding_liked",
        finding_id=finding_id,
        review_id=review_id,
        category=category,
        source=source,
    )
