"""SQLAlchemy 2.0 entity definitions matching the C4 ERD."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from core.schemas import Category, Severity


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class UserPlan(StrEnum):
    FREE = "free"
    PAID = "paid"


class ReviewStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class FileAssetKind(StrEnum):
    DECK_ORIGINAL = "deck_original"
    SLIDE_PNG = "slide_png"
    ANNOTATED_PNG = "annotated_png"
    FIXED_PPTX = "fixed_pptx"
    AUDIO = "audio"
    DATA_XLSX = "data_xlsx"
    REPORT_PDF = "report_pdf"


# Use JSONB on Postgres; JSON works for SQLite tests.
JsonType = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(16), nullable=False, default=UserPlan.FREE.value)
    free_reviews_left: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # Купленные Разборы. Списываются после того, как исчерпаны бесплатные; на нуле
    # запуск блокируется 402-м с предложением пополнить баланс.
    balance_reviews: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    reviews: Mapped[list[Review]] = relationship(back_populates="user")
    events: Mapped[list[Event]] = relationship(back_populates="user")


class RehearsalStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (Index("ix_reviews_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ReviewStatus.QUEUED.value,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deck_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    n_slides: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_metrics: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    has_audio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Из какого кошелька списан этот Разбор — чтобы при провале вернуть туда же,
    # а не подарить бесплатный вместо купленного (или наоборот).
    credit_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="reviews")
    findings: Mapped[list[FindingRow]] = relationship(back_populates="review")
    file_assets: Mapped[list[FileAsset]] = relationship(back_populates="review")
    rehearsals: Mapped[list[Rehearsal]] = relationship(
        back_populates="review", order_by="Rehearsal.attempt_num"
    )


class FindingRow(Base):
    """ORM mirror of pydantic ``Finding`` plus review/API fields."""

    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slide_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    fix_suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    screenshot_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "file_assets.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_findings_screenshot_asset_id",
        ),
        nullable=True,
    )
    auto_fixable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_fixed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_like: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    review: Mapped[Review] = relationship(back_populates="findings")


class FileAsset(Base):
    __tablename__ = "file_assets"
    __table_args__ = (Index("ix_file_assets_expires_at", "expires_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    review: Mapped[Review] = relationship(back_populates="file_assets")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_name_created_at", "name", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User | None] = relationship(back_populates="events")


class Rehearsal(Base):
    """A recorded rehearsal attempt against a Review's deck (phase 4, П2-П4)."""

    __tablename__ = "rehearsals"
    __table_args__ = (Index("ix_rehearsals_review_id_attempt_num", "review_id", "attempt_num"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RehearsalStatus.QUEUED.value
    )
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    slide_timings: Mapped[list[Any] | None] = mapped_column(JsonType, nullable=True)
    delivery_metrics: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    findings: Mapped[list[Any] | None] = mapped_column(JsonType, nullable=True)
    attempt_num: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    review: Mapped[Review] = relationship(back_populates="rehearsals")


# Re-export taxonomy enums for callers that import from models
__all_enums__ = (Category, Severity, UserPlan, ReviewStatus, FileAssetKind, RehearsalStatus)
