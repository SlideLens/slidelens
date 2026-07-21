"""Convert between pydantic ``Finding`` and ORM ``FindingRow``."""

from __future__ import annotations

from uuid import UUID

from app.models.entities import FindingRow
from core.schemas import BBox, Category, Finding, Severity


def finding_to_row(finding: Finding, *, review_id: UUID) -> FindingRow:
    """Map a pipeline Finding into an ORM row (shared fields)."""
    return FindingRow(
        id=finding.id,
        review_id=review_id,
        slide_num=finding.slide_num,
        category=finding.category.value,
        severity=finding.severity.value,
        title=finding.title,
        description=finding.description,
        fix_suggestion=finding.fix_suggestion,
        bbox=finding.bbox.model_dump() if finding.bbox else None,
        auto_fixable=finding.auto_fixable,
        auto_fixed=finding.auto_fixed,
        source=finding.source,
        user_flag=False,
        user_like=False,
    )


def row_to_finding(row: FindingRow) -> Finding:
    """Map an ORM row back to a pipeline Finding."""
    bbox = BBox.model_validate(row.bbox) if row.bbox is not None else None
    return Finding(
        id=row.id,
        slide_num=row.slide_num,
        category=Category(row.category),
        severity=Severity(row.severity),
        title=row.title,
        description=row.description,
        fix_suggestion=row.fix_suggestion,
        bbox=bbox,
        auto_fixable=row.auto_fixable,
        auto_fixed=row.auto_fixed,
        source=row.source,
    )
