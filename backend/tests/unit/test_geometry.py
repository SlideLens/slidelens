"""Unit tests for ``core.geometry`` — конвертация рамок и перенос между системами координат."""

from __future__ import annotations

import pytest

from core.geometry import box_2d_to_bbox, iou, project_into
from core.schemas import BBox


def test_box_2d_converts_from_gemini_order_and_scale() -> None:
    # [ymin, xmin, ymax, xmax] в шкале 0..1000 — не x/y/w/h и не 0..1.
    bbox = box_2d_to_bbox([640, 70, 730, 480])

    assert bbox is not None
    assert (bbox.x, bbox.y, bbox.w, bbox.h) == pytest.approx((0.07, 0.64, 0.41, 0.09))


def test_box_2d_full_frame_maps_to_whole_slide() -> None:
    bbox = box_2d_to_bbox([0, 0, 1000, 1000])

    assert bbox == BBox(x=0.0, y=0.0, w=1.0, h=1.0)


def test_box_2d_swapped_edges_are_normalized() -> None:
    """Модель иногда меняет края местами — это чинится, а не превращается в мусор."""
    swapped = box_2d_to_bbox([730, 480, 640, 70])

    assert swapped == box_2d_to_bbox([640, 70, 730, 480])


def test_box_2d_out_of_range_is_clamped_to_the_slide() -> None:
    bbox = box_2d_to_bbox([-50, 900, 400, 1400])

    assert bbox is not None
    assert (bbox.x, bbox.y) == pytest.approx((0.9, 0.0))
    # Правый край подрезан по границе слайда: 1.0 - 0.9.
    assert bbox.w == pytest.approx(0.1)


@pytest.mark.parametrize(
    "box",
    [
        None,
        [],
        [1, 2, 3],
        [1, 2, 3, 4, 5],
        [500, 500, 500, 500],  # нулевая площадь
        [400, 700, 800, 700],  # нулевая ширина
    ],
)
def test_unusable_box_2d_yields_no_frame(box: list[int] | None) -> None:
    """Находка без рамки — нормальный исход; выдумывать координаты нельзя."""
    assert box_2d_to_bbox(box) is None


def test_project_into_moves_crop_coordinates_onto_the_slide() -> None:
    crop = BBox(x=0.5, y=0.4, w=0.4, h=0.2)
    inner = BBox(x=0.5, y=0.5, w=0.5, h=0.5)

    projected = project_into(crop, inner)

    assert (projected.x, projected.y) == pytest.approx((0.7, 0.5))
    assert (projected.w, projected.h) == pytest.approx((0.2, 0.1))


def test_project_into_whole_crop_is_identity() -> None:
    crop = BBox(x=0.2, y=0.3, w=0.5, h=0.4)

    assert project_into(crop, BBox(x=0.0, y=0.0, w=1.0, h=1.0)) == crop


def test_project_into_clips_to_the_slide() -> None:
    crop = BBox(x=0.8, y=0.8, w=0.4, h=0.4)

    projected = project_into(crop, BBox(x=0.5, y=0.5, w=1.0, h=1.0))

    assert projected.x + projected.w <= 1.0
    assert projected.y + projected.h <= 1.0


def test_iou_of_identical_boxes_is_one() -> None:
    box = BBox(x=0.1, y=0.1, w=0.2, h=0.2)

    assert iou(box, box) == pytest.approx(1.0)


def test_iou_of_disjoint_boxes_is_zero() -> None:
    assert iou(BBox(x=0.0, y=0.0, w=0.1, h=0.1), BBox(x=0.5, y=0.5, w=0.1, h=0.1)) == 0.0
