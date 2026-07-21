"""CLI and ``PipelineOrchestrator`` — ordered review steps from config."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from core.aggregate import Aggregator
from core.analyzers.base import BaseAnalyzer
from core.analyzers.charts import ChartChecker
from core.analyzers.crossmodal import CrossModalAnalyzer
from core.analyzers.deck import DeckAnalyzer
from core.analyzers.slide import SlideAnalyzer
from core.analyzers.zoom import ZoomAgent
from core.annotate import Annotator
from core.context import ReviewContext
from core.fix import PptxFixer
from core.ingest import DeckIngestor
from core.ingest_errors import IngestError
from core.llm import LLMClient, LLMConfig
from core.report import PdfExporter, ReportBuilder


class PipelineOrchestrator:
    """Runs an ordered list of analyzers against a shared ``ReviewContext``."""

    def __init__(self, steps: list[BaseAnalyzer]) -> None:
        self._steps = steps

    async def run(self, ctx: ReviewContext) -> list[BaseAnalyzer]:
        for step in self._steps:
            await step.run(ctx)
        return self._steps


def default_steps(llm: LLMClient) -> list[BaseAnalyzer]:
    return [
        SlideAnalyzer(llm),
        ZoomAgent(llm),
        DeckAnalyzer(llm),
        ChartChecker(llm),
        CrossModalAnalyzer(llm),
    ]


def _llm_config_from_env() -> LLMConfig:
    kwargs: dict[str, object] = {"api_key": os.environ.get("LLM_API_KEY", "")}
    if base_url := os.environ.get("LLM_BASE_URL"):
        kwargs["base_url"] = base_url
    if model_full := os.environ.get("LLM_MODEL_FULL"):
        kwargs["model_full"] = model_full
    if model_screening := os.environ.get("LLM_MODEL_SCREENING"):
        kwargs["model_screening"] = model_screening
    if timeout := os.environ.get("LLM_TIMEOUT_SECONDS"):
        kwargs["timeout_seconds"] = float(timeout)
    return LLMConfig(**kwargs)  # type: ignore[arg-type]


async def run_cli(args: argparse.Namespace) -> int:
    deck = Path(args.deck)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ctx = ReviewContext(workdir=out_dir, deck_path=deck)
    if args.audio:
        ctx.audio_path = Path(args.audio)
    if args.data:
        ctx.xlsx_path = Path(args.data)

    start = time.monotonic()
    try:
        await DeckIngestor().ingest(deck, out_dir, ctx)
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    llm = LLMClient(_llm_config_from_env())
    try:
        await PipelineOrchestrator(default_steps(llm)).run(ctx)
        ctx.findings = await Aggregator(llm).run(ctx.findings)
    finally:
        await llm.aclose()

    if deck.suffix.lower() == ".pptx":
        PptxFixer().fix(deck, ctx.findings, out_dir=out_dir)

    annotations = Annotator().annotate(ctx)
    report = ReportBuilder().build(ctx)
    html, pdf_bytes = PdfExporter().export(report, annotations=annotations)
    (out_dir / "report.html").write_text(html, encoding="utf-8")
    (out_dir / "report.pdf").write_bytes(pdf_bytes)

    findings_path = out_dir / "findings.json"
    findings_path.write_text(
        json.dumps(
            [f.model_dump(mode="json") for f in ctx.findings],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    elapsed = time.monotonic() - start
    severity_counts = dict(Counter(f.severity.value for f in ctx.findings))
    print(
        f"slides={len(ctx.slide_pngs)} findings={len(ctx.findings)} score={report.score} "
        f"by_severity={severity_counts} elapsed_s={elapsed:.1f} "
        f"cost_rub={ctx.total_cost_rub:.2f}"
    )
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m core.run")
    parser.add_argument("--deck", required=True, help="Path to the PPTX/PDF deck")
    parser.add_argument("--audio", help="Optional pitch recording (video/audio)")
    parser.add_argument("--data", help="Optional Excel with underlying chart data")
    parser.add_argument("--out", required=True, help="Output directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return asyncio.run(run_cli(args))


if __name__ == "__main__":
    sys.exit(main())
