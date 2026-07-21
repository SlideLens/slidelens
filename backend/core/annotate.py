"""Annotate slide PNGs with severity-colored bbox overlays (Pillow).

Colors match ``DESIGN.md``'s severity palette (red/orange/gray), shared with
the report UI's badges.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageDraw

from core.constants import SLIDE_WIDE_BBOX_AREA
from core.context import ReviewContext
from core.schemas import Finding, Severity

SEVERITY_COLORS: dict[Severity, tuple[int, int, int]] = {
    Severity.CRITICAL: (220, 38, 38),  # Tailwind red-600
    Severity.MAJOR: (249, 115, 22),  # Tailwind orange-500
    Severity.MINOR: (107, 114, 128),  # Tailwind gray-500
}


class Annotator:
    """One output PNG per slide, one frame per bbox'd finding on it."""

    def __init__(self, *, line_width: int = 4) -> None:
        self._line_width = line_width

    def annotate(self, ctx: ReviewContext) -> dict[UUID, Path]:
        by_slide: dict[int, list[Finding]] = defaultdict(list)
        for finding in ctx.findings:
            if finding.slide_num is not None and finding.bbox is not None:
                by_slide[finding.slide_num].append(finding)

        result: dict[UUID, Path] = {}
        for slide_num, findings in by_slide.items():
            png = ctx.slide_png(slide_num)
            out_path = ctx.workdir / f"slide_{slide_num:03d}_annotated.png"
            self._draw(png, findings, out_path)
            for finding in findings:
                result[finding.id] = out_path
        return result

    def _draw(self, png: Path, findings: list[Finding], out_path: Path) -> None:
        with Image.open(png) as image:
            canvas = image.convert("RGB")
            width, height = canvas.size
            draw = ImageDraw.Draw(canvas)
            for index, finding in enumerate(findings, start=1):
                bbox = finding.bbox
                # Рамка «во весь слайд» ни на что не указывает и перекрывает
                # настоящие области — находка остаётся, рамка не рисуется.
                if bbox.w * bbox.h >= SLIDE_WIDE_BBOX_AREA:
                    continue
                x0, y0 = bbox.x * width, bbox.y * height
                x1, y1 = (bbox.x + bbox.w) * width, (bbox.y + bbox.h) * height
                color = SEVERITY_COLORS[finding.severity]
                draw.rectangle([x0, y0, x1, y1], outline=color, width=self._line_width)
                draw.text((x0 + 2, max(0, y0 - 14)), str(index), fill=color)
            canvas.save(out_path, "PNG")
