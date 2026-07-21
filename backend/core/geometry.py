"""Shared bbox geometry helpers (normalized 0..1 coordinates)."""

from __future__ import annotations

from core.constants import BOX_2D_SCALE
from core.schemas import BBox


def box_2d_to_bbox(box: list[int] | None) -> BBox | None:
    """``[ymin, xmin, ymax, xmax]`` в шкале 0..1000 → наш ``BBox`` (0..1, x/y/w/h).

    Это родной формат рамок Gemini: модели специально обучены выдавать координаты
    именно так, и на нём они попадают в цель заметно точнее, чем на произвольном
    ``{x, y, w, h}`` во float. Внутри проекта формат один — ``BBox``; конвертация
    живёт только здесь.

    Возвращает ``None`` на всём, что нельзя считать рамкой (не 4 числа, нулевая
    площадь), — Находка при этом остаётся, просто без рамки.
    """
    if box is None or len(box) != 4:
        return None

    y_min, x_min, y_max, x_max = (v / BOX_2D_SCALE for v in box)
    # Модель иногда путает порядок краёв — берём min/max, а не доверяем позиции.
    x0, x1 = sorted((x_min, x_max))
    y0, y1 = sorted((y_min, y_max))
    x0, y0 = max(x0, 0.0), max(y0, 0.0)
    x1, y1 = min(x1, 1.0), min(y1, 1.0)
    if x1 <= x0 or y1 <= y0:
        return None
    return BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0)


def project_into(outer: BBox, inner: BBox) -> BBox:
    """Переносит ``inner`` из системы координат кропа ``outer`` в координаты слайда.

    Анализатор, которому показали вырезанный фрагмент, нумерует его от собственного
    левого верхнего угла (``0..1`` внутри кропа). Без этого переноса рамка уезжает
    в другое место слайда — тем сильнее, чем дальше кроп от начала координат.
    """
    x = outer.x + inner.x * outer.w
    y = outer.y + inner.y * outer.h
    w = inner.w * outer.w
    h = inner.h * outer.h
    # Округления при вырезании могут вытолкнуть край за слайд — подрезаем.
    x = min(max(x, 0.0), 1.0)
    y = min(max(y, 0.0), 1.0)
    return BBox(x=x, y=y, w=min(w, 1.0 - x), h=min(h, 1.0 - y))


def iou(a: BBox, b: BBox) -> float:
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx2, by2 = b.x + b.w, b.y + b.h
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    if intersection <= 0:
        return 0.0
    union = (a.w * a.h) + (b.w * b.h) - intersection
    return intersection / union if union > 0 else 0.0
