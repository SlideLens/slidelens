"""Finding ↔ FindingRow round-trip and enum/schema smoke tests."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models import (
    Base,
    FileAssetKind,
    ReviewStatus,
    UserPlan,
)
from app.services.finding_mapper import finding_to_row, row_to_finding
from core.schemas import BBox, Category, Finding, Severity


def test_enum_values_match_context() -> None:
    assert {s.value for s in ReviewStatus} == {"queued", "processing", "done", "failed"}
    assert {p.value for p in UserPlan} == {"free", "paid"}
    assert {k.value for k in FileAssetKind} == {
        "deck_original",
        "slide_png",
        "annotated_png",
        "fixed_pptx",
        "audio",
        "data_xlsx",
        "report_pdf",
    }
    assert len(Category) == 8
    assert len(Severity) == 3


def test_finding_row_round_trip() -> None:
    finding = Finding(
        category=Category.HIERARCHY,
        severity=Severity.MAJOR,
        title="Слабая иерархия заголовка",
        description="Заголовок визуально не доминирует.",
        fix_suggestion="Увеличьте кегль заголовка.",
        slide_num=3,
        bbox=BBox(x=0.1, y=0.2, w=0.5, h=0.1),
        auto_fixable=True,
        auto_fixed=False,
        source="SlideAnalyzer",
    )
    review_id = uuid4()
    row = finding_to_row(finding, review_id=review_id)
    back = row_to_finding(row)
    assert back.model_dump() == finding.model_dump()
    assert row.review_id == review_id
    assert row.user_flag is False
    assert row.user_like is False


def test_metadata_create_all_sqlite() -> None:
    """Schema smoke without Postgres: create all tables on SQLite."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    names = set(inspect(engine).get_table_names())
    assert {
        "users",
        "reviews",
        "findings",
        "file_assets",
        "events",
        "rehearsals",
    } <= names
    idx_names = {ix["name"] for ix in inspect(engine).get_indexes("reviews")}
    assert "ix_reviews_user_id_created_at" in idx_names
    with Session(engine) as session:
        assert session is not None
