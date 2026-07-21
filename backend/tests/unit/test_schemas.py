"""Unit tests for ``core.schemas`` validation contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.schemas import (
    BBox,
    Category,
    Finding,
    Severity,
)


def test_category_has_exactly_eight_values() -> None:
    assert {c.value for c in Category} == {
        "TYPOGRAPHY",
        "HIERARCHY",
        "READABILITY",
        "CONSISTENCY",
        "CHART",
        "NARRATIVE",
        "SPEECH_MISMATCH",
        "DELIVERY",
    }
    assert len(Category) == 8


def test_severity_has_exactly_three_values() -> None:
    assert {s.value for s in Severity} == {"CRITICAL", "MAJOR", "MINOR"}
    assert len(Severity) == 3


def test_bbox_in_range_accepted() -> None:
    box = BBox(x=0.0, y=0.5, w=1.0, h=0.25)
    assert box.w == 1.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("x", -0.01),
        ("y", 1.01),
        ("w", -0.1),
        ("h", 1.5),
    ],
)
def test_bbox_out_of_range_rejected(field: str, value: float) -> None:
    data = {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1, field: value}
    with pytest.raises(ValidationError):
        BBox.model_validate(data)


def test_finding_title_within_limit() -> None:
    finding = Finding(
        category=Category.TYPOGRAPHY,
        severity=Severity.MINOR,
        title="x" * 80,
        description="d",
        fix_suggestion="f",
    )
    assert len(finding.title) == 80


def test_finding_title_too_long_rejected() -> None:
    with pytest.raises(ValidationError):
        Finding(
            category=Category.TYPOGRAPHY,
            severity=Severity.MINOR,
            title="x" * 81,
            description="d",
            fix_suggestion="f",
        )


def test_invalid_category_rejected() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(
            {
                "category": "NOT_A_CATEGORY",
                "severity": "MINOR",
                "title": "t",
                "description": "d",
                "fix_suggestion": "f",
            }
        )


def test_finding_json_schema_exportable() -> None:
    schema = Finding.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema or "$defs" in schema or "title" in schema
