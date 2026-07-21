"""``BaseAnalyzer`` — template method for graceful-degradation analyzers.

Every concrete analyzer implements ``analyze()``; ``run()`` supplies the
timing, logging, and exception isolation every analyzer needs identically
(ADR 0002: a failing analyzer is skipped and logged, the Review continues).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import ClassVar

import structlog

from core.context import ReviewContext
from core.schemas import Finding
from observability.setup import observe_pipeline_step

logger = structlog.get_logger(__name__)


class BaseAnalyzer(ABC):
    """One independent analysis step over a ``ReviewContext``."""

    name: ClassVar[str]

    @abstractmethod
    async def analyze(self, ctx: ReviewContext) -> list[Finding]:
        """Subclass logic. May raise — ``run()`` isolates failures."""

    async def run(self, ctx: ReviewContext) -> list[Finding]:
        start = time.monotonic()
        logger.info("analyzer.start", analyzer=self.name)
        try:
            findings = await self.analyze(ctx)
        except Exception as exc:  # noqa: BLE001 — graceful degradation by design
            duration = time.monotonic() - start
            observe_pipeline_step(self.name, duration)
            logger.error(
                "analyzer.failed",
                analyzer=self.name,
                error=str(exc),
                duration_seconds=duration,
            )
            return []

        duration = time.monotonic() - start
        observe_pipeline_step(self.name, duration)
        ctx.add_findings(findings, source=self.name)
        logger.info(
            "analyzer.done",
            analyzer=self.name,
            n_findings=len(findings),
            duration_seconds=duration,
        )
        return findings
