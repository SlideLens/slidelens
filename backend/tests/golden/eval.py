"""Golden-set eval: run the pipeline against annotated decks, compute recall/junk/cost.

See ``README.md`` in this directory for the ``expected/*.yaml`` format.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from core.aggregate import SAME_ISSUE_PROMPT_NAME
from core.aggregate_schemas import SameIssueResponse
from core.context import ReviewContext
from core.ingest import DeckIngestor
from core.llm import LLMClient, default_registry
from core.run import PipelineOrchestrator, _llm_config_from_env, default_steps
from core.schemas import Category, Finding

_QUALITY_LOG_HEADER = (
    "| date | prompt_version | recall | junk_rate | avg_cost_usd |\n"
    "|---|---|---|---|---|\n"
)


class GoldenExpectedFinding(BaseModel):
    slide_num: int | None = None
    category: Category
    description: str


class GoldenDeck(BaseModel):
    name: str
    deck_path: Path
    expected: list[GoldenExpectedFinding] = Field(default_factory=list)


def load_golden_set(golden_dir: Path) -> list[GoldenDeck]:
    decks_dir = golden_dir / "decks"
    expected_dir = golden_dir / "expected"
    golden_decks: list[GoldenDeck] = []
    for deck_path in sorted(decks_dir.glob("*.pptx")):
        expected_path = expected_dir / f"{deck_path.stem}.yaml"
        expected: list[GoldenExpectedFinding] = []
        if expected_path.is_file():
            raw = yaml.safe_load(expected_path.read_text(encoding="utf-8")) or []
            expected = [GoldenExpectedFinding.model_validate(item) for item in raw]
        golden_decks.append(
            GoldenDeck(name=deck_path.stem, deck_path=deck_path, expected=expected)
        )
    return golden_decks


async def judge_same_issue(
    llm: LLMClient, expected: GoldenExpectedFinding, actual: Finding
) -> bool:
    system_prompt = default_registry().get(SAME_ISSUE_PROMPT_NAME).body
    prompt = (
        f"Эталонное описание: {expected.description}\n"
        f"Описание от анализатора: {actual.description}"
    )
    response = await llm.complete_structured(
        prompt, SameIssueResponse, system=system_prompt, tier="screening"
    )
    return response.same_issue


async def match_findings(
    llm: LLMClient, expected: list[GoldenExpectedFinding], actual: list[Finding]
) -> tuple[int, int]:
    claimed_ids: set[object] = set()
    matched = 0
    for exp in expected:
        candidates = [
            f
            for f in actual
            if f.id not in claimed_ids
            and f.slide_num == exp.slide_num
            and f.category == exp.category
        ]
        for candidate in candidates:
            if await judge_same_issue(llm, exp, candidate):
                claimed_ids.add(candidate.id)
                matched += 1
                break
    junk = len(actual) - len(claimed_ids)
    return matched, junk


@dataclass
class DeckEvalResult:
    name: str
    n_expected: int
    n_matched: int
    n_actual: int
    n_junk: int
    cost_usd: float


async def evaluate_deck(deck: GoldenDeck, llm: LLMClient, workdir: Path) -> DeckEvalResult:
    deck_workdir = workdir / deck.name
    ctx = ReviewContext(workdir=deck_workdir, deck_path=deck.deck_path)
    await DeckIngestor().ingest(deck.deck_path, deck_workdir, ctx)
    await PipelineOrchestrator(default_steps(llm)).run(ctx)
    n_matched, n_junk = await match_findings(llm, deck.expected, ctx.findings)
    return DeckEvalResult(
        name=deck.name,
        n_expected=len(deck.expected),
        n_matched=n_matched,
        n_actual=len(ctx.findings),
        n_junk=n_junk,
        cost_usd=ctx.total_cost_usd,
    )


@dataclass
class EvalSummary:
    recall: float
    junk_rate: float
    total_cost_usd: float
    avg_cost_usd: float
    n_decks: int


def summarize(results: list[DeckEvalResult]) -> EvalSummary:
    total_expected = sum(r.n_expected for r in results)
    total_matched = sum(r.n_matched for r in results)
    total_actual = sum(r.n_actual for r in results)
    total_junk = sum(r.n_junk for r in results)
    total_cost = sum(r.cost_usd for r in results)
    return EvalSummary(
        recall=total_matched / total_expected if total_expected else 0.0,
        junk_rate=total_junk / total_actual if total_actual else 0.0,
        total_cost_usd=total_cost,
        avg_cost_usd=total_cost / len(results) if results else 0.0,
        n_decks=len(results),
    )


def append_quality_log(
    path: Path,
    *,
    prompt_version: str,
    summary: EvalSummary,
    today: date | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = (
        f"| {(today or date.today()).isoformat()} | {prompt_version} | "
        f"{summary.recall:.0%} | {summary.junk_rate:.0%} | ${summary.avg_cost_usd:.4f} |\n"
    )
    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "| date |" not in content:
        if content and not content.endswith("\n"):
            content += "\n"
        content += _QUALITY_LOG_HEADER
    content += row
    path.write_text(content, encoding="utf-8")


def _default_quality_log_path() -> Path:
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "achitecture" / "docs" / "quality-log.md"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tests.golden.eval")
    parser.add_argument(
        "--golden-dir", default=str(Path(__file__).resolve().parent), help="Golden set root"
    )
    parser.add_argument("--out", required=True, help="Working directory for pipeline runs")
    parser.add_argument(
        "--quality-log", help="Path to quality-log.md (defaults to achitecture/docs/)"
    )
    parser.add_argument(
        "--prompt-version", required=True, help="Label recorded in quality-log.md"
    )
    return parser


async def run_eval(args: argparse.Namespace) -> EvalSummary:
    golden_dir = Path(args.golden_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    golden_decks = load_golden_set(golden_dir)
    llm = LLMClient(_llm_config_from_env())
    try:
        results = [await evaluate_deck(deck, llm, out_dir) for deck in golden_decks]
    finally:
        await llm.aclose()

    summary = summarize(results)
    quality_log_path = Path(args.quality_log) if args.quality_log else _default_quality_log_path()
    append_quality_log(quality_log_path, prompt_version=args.prompt_version, summary=summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = asyncio.run(run_eval(args))
    print(
        f"decks={summary.n_decks} recall={summary.recall:.0%} "
        f"junk_rate={summary.junk_rate:.0%} avg_cost_usd={summary.avg_cost_usd:.4f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
