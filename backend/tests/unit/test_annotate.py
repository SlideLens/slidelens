"""Unit tests for ``core.annotate.Annotator``."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from core.annotate import SEVERITY_COLORS, Annotator
from core.context import ReviewContext
from core.schemas import BBox, Category, Finding, Severity


def _ctx_with_slide(tmp_path: Path, size: tuple[int, int] = (100, 100)) -> ReviewContext:
    ctx = ReviewContext(workdir=tmp_path)
    png = tmp_path / "slide_001.png"
    Image.new("RGB", size, "white").save(png, "PNG")
    ctx.slide_pngs[1] = png
    return ctx


def _finding(**overrides: object) -> Finding:
    payload: dict[str, object] = {
        "slide_num": 1,
        "category": Category.READABILITY,
        "severity": Severity.CRITICAL,
        "title": "t",
        "description": "d",
        "fix_suggestion": "f",
        "bbox": BBox(x=0.2, y=0.2, w=0.3, h=0.3),
    }
    payload.update(overrides)
    return Finding(**payload)


def test_multiple_findings_on_one_slide_share_one_image(tmp_path: Path) -> None:
    ctx = _ctx_with_slide(tmp_path)
    findings = [
        _finding(severity=Severity.CRITICAL),
        _finding(severity=Severity.MAJOR, bbox=BBox(x=0.5, y=0.5, w=0.2, h=0.2)),
        _finding(severity=Severity.MINOR, bbox=BBox(x=0.0, y=0.0, w=0.1, h=0.1)),
    ]
    ctx.add_findings(findings, source="test")

    result = Annotator().annotate(ctx)

    assert len(result) == 3
    paths = set(result.values())
    assert len(paths) == 1
    assert next(iter(paths)).is_file()


def test_findings_without_bbox_produce_no_frame_or_entry(tmp_path: Path) -> None:
    ctx = _ctx_with_slide(tmp_path)
    ctx.add_findings([_finding(bbox=None)], source="test")

    result = Annotator().annotate(ctx)

    assert result == {}


def test_frame_color_matches_severity(tmp_path: Path) -> None:
    ctx = _ctx_with_slide(tmp_path, size=(100, 100))
    finding = _finding(
        severity=Severity.CRITICAL, bbox=BBox(x=0.2, y=0.2, w=0.3, h=0.3)
    )
    ctx.add_findings([finding], source="test")

    result = Annotator(line_width=2).annotate(ctx)
    out_path = result[finding.id]

    with Image.open(out_path) as img:
        # Top edge of the frame: x in [20,50], y=20.
        pixel = img.getpixel((35, 20))
    assert pixel == SEVERITY_COLORS[Severity.CRITICAL]


def test_slide_wide_bbox_keeps_the_finding_but_draws_no_frame(tmp_path: Path) -> None:
    ctx = _ctx_with_slide(tmp_path, size=(100, 100))
    finding = _finding(bbox=BBox(x=0.0, y=0.0, w=1.0, h=1.0))
    ctx.add_findings([finding], source="test")

    result = Annotator(line_width=2).annotate(ctx)

    # Находка по-прежнему ссылается на скриншот слайда...
    assert finding.id in result
    with Image.open(result[finding.id]) as img:
        # ...но рамки во весь слайд на нём нет.
        assert img.getpixel((50, 0)) == (255, 255, 255)
        assert img.getpixel((0, 50)) == (255, 255, 255)


def test_frame_position_matches_bbox_fraction(tmp_path: Path) -> None:
    ctx = _ctx_with_slide(tmp_path, size=(200, 100))
    finding = _finding(
        severity=Severity.MAJOR, bbox=BBox(x=0.25, y=0.5, w=0.25, h=0.25)
    )
    ctx.add_findings([finding], source="test")

    result = Annotator(line_width=2).annotate(ctx)
    out_path = result[finding.id]

    # bbox in pixels: x0=50, y0=50, x1=100, y1=75.
    with Image.open(out_path) as img:
        left_edge = img.getpixel((50, 60))
        outside = img.getpixel((10, 10))

    assert left_edge == SEVERITY_COLORS[Severity.MAJOR]
    assert outside == (255, 255, 255)
