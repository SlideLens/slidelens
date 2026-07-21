"""``ReportBuilder`` + ``PdfExporter`` — assemble and export ``ReportOut``.

See ``core.report_schemas`` for the ``ReportOut`` view-model itself.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.aggregate import DeckScorer
from core.context import ReviewContext
from core.report_schemas import ReportOut
from core.schemas import Finding

DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "report_pdf"


class ReportBuilder:
    """Assembles ``ReportOut`` from an already-aggregated ``ReviewContext``."""

    def __init__(self, *, scorer: DeckScorer | None = None) -> None:
        self._scorer = scorer or DeckScorer()

    def build(self, ctx: ReviewContext) -> ReportOut:
        n_slides = len(ctx.slide_pngs)
        score = self._scorer.score(ctx.findings, n_slides)
        auto_fixed_count = sum(1 for f in ctx.findings if f.auto_fixed)
        delivery = ctx.step_results.get("delivery")
        return ReportOut(
            review_id=ctx.review_id or uuid4(),
            score=score,
            n_slides=n_slides,
            findings=list(ctx.findings),
            delivery=delivery,
            auto_fixed_count=auto_fixed_count,
        )


def _weasyprint_html_to_pdf(html: str) -> bytes:
    import weasyprint

    return weasyprint.HTML(string=html).write_pdf()


class PdfExporter:
    """``ReportOut`` → HTML (Jinja2) → PDF bytes (injectable backend)."""

    def __init__(
        self,
        *,
        template_dir: Path | None = None,
        render_pdf: Callable[[str], bytes] | None = None,
    ) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir or DEFAULT_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "jinja"]),
        )
        self._render_pdf = render_pdf or _weasyprint_html_to_pdf

    def render_html(
        self,
        report: ReportOut,
        *,
        annotations: dict[UUID, Path] | None = None,
    ) -> str:
        template = self._env.get_template("report.html.jinja")
        by_slide: dict[int | None, list[Finding]] = {}
        for finding in report.findings:
            by_slide.setdefault(finding.slide_num, []).append(finding)
        return template.render(
            report=report,
            findings_by_slide=by_slide,
            annotations=annotations or {},
        )

    def export_pdf(self, html: str) -> bytes:
        return self._render_pdf(html)

    def export(
        self,
        report: ReportOut,
        *,
        annotations: dict[UUID, Path] | None = None,
    ) -> tuple[str, bytes]:
        html = self.render_html(report, annotations=annotations)
        return html, self.export_pdf(html)
