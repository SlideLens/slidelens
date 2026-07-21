"""Unit tests for ``core.report`` (ReportBuilder, PdfExporter, ReportOut)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import yaml

from core.aggregate import DeckScorer
from core.context import ReviewContext
from core.report import PdfExporter, ReportBuilder
from core.schemas import Category, DeliveryMetrics, Finding, Severity

_OPENAPI_PATH = (
    Path(__file__).resolve().parents[4] / "achitecture" / "api" / "openapi.yaml"
)


def _finding(**overrides: object) -> Finding:
    payload: dict[str, object] = {
        "slide_num": 1,
        "category": Category.TYPOGRAPHY,
        "severity": Severity.MINOR,
        "title": "t",
        "description": "d",
        "fix_suggestion": "f",
    }
    payload.update(overrides)
    return Finding(**payload)


def _ctx_with_slides(tmp_path: Path, n: int) -> ReviewContext:
    ctx = ReviewContext(workdir=tmp_path)
    for i in range(1, n + 1):
        ctx.slide_pngs[i] = tmp_path / f"slide_{i:03d}.png"
    return ctx


def test_score_matches_deck_scorer(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 5)
    ctx.add_findings([_finding(severity=Severity.CRITICAL)], source="test")

    report = ReportBuilder().build(ctx)

    assert report.score == DeckScorer().score(ctx.findings, 5)


def test_auto_fixed_count_reflects_findings(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 2)
    ctx.add_findings(
        [
            _finding(title="a", auto_fixed=True),
            _finding(title="b", auto_fixed=False),
            _finding(title="c", auto_fixed=True),
        ],
        source="test",
    )

    report = ReportBuilder().build(ctx)

    assert report.auto_fixed_count == 2


def test_delivery_none_without_step_results(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 1)
    report = ReportBuilder().build(ctx)
    assert report.delivery is None


def test_delivery_present_from_step_results(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 1)
    delivery = DeliveryMetrics(words_per_minute=140.0, filler_words={}, long_pauses=[])
    ctx.step_results["delivery"] = delivery

    report = ReportBuilder().build(ctx)

    assert report.delivery == delivery


def test_review_id_fallback_generates_uuid(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 1)
    assert ctx.review_id is None

    report = ReportBuilder().build(ctx)

    assert report.review_id is not None


def test_review_id_uses_ctx_value_when_set(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 1)
    ctx.review_id = uuid4()

    report = ReportBuilder().build(ctx)

    assert report.review_id == ctx.review_id


def test_report_out_has_every_openapi_required_field(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 3)
    ctx.add_findings([_finding()], source="test")
    report = ReportBuilder().build(ctx)
    dumped = report.model_dump(mode="json")

    spec = yaml.safe_load(_OPENAPI_PATH.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    for field in schemas["ReportOut"]["required"]:
        assert field in dumped, f"ReportOut missing required field: {field}"

    for finding_dict in dumped["findings"]:
        for field in schemas["Finding"]["required"]:
            assert field in finding_dict, f"Finding missing required field: {field}"


def test_render_html_contains_score_and_finding_titles(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 1)
    ctx.add_findings([_finding(title="Мелкий шрифт")], source="test")
    report = ReportBuilder().build(ctx)

    html = PdfExporter().render_html(report)

    assert str(report.score) in html
    assert "Мелкий шрифт" in html


def test_render_html_declares_utf8_charset(tmp_path: Path) -> None:
    ctx = _ctx_with_slides(tmp_path, 1)
    report = ReportBuilder().build(ctx)

    html = PdfExporter().render_html(report)

    assert 'charset="utf-8"' in html.lower()


def test_export_pdf_delegates_to_injected_backend(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_render_pdf(html: str) -> bytes:
        calls.append(html)
        return b"%PDF-fake%"

    exporter = PdfExporter(render_pdf=fake_render_pdf)
    result = exporter.export_pdf("<html>hi</html>")

    assert result == b"%PDF-fake%"
    assert calls == ["<html>hi</html>"]
