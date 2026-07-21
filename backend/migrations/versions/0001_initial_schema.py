"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("plan", sa.String(length=16), nullable=False),
        sa.Column("free_reviews_left", sa.Integer(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("has_audio", sa.Boolean(), nullable=False),
        sa.Column("has_data", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reviews_user_id_created_at",
        "reviews",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_name_created_at", "events", ["name", "created_at"], unique=False)

    op.create_table(
        "file_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_file_assets_expires_at", "file_assets", ["expires_at"], unique=False)
    op.create_index("ix_file_assets_review_id", "file_assets", ["review_id"], unique=False)

    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("slide_num", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("fix_suggestion", sa.Text(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("screenshot_asset_id", sa.Uuid(), nullable=True),
        sa.Column("auto_fixable", sa.Boolean(), nullable=False),
        sa.Column("auto_fixed", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("user_flag", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["screenshot_asset_id"],
            ["file_assets.id"],
            name="fk_findings_screenshot_asset_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_review_id", "findings", ["review_id"], unique=False)

    op.create_table(
        "rehearsals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("audio_path", sa.String(length=1024), nullable=True),
        sa.Column("slide_timings", sa.JSON(), nullable=True),
        sa.Column("delivery_metrics", sa.JSON(), nullable=True),
        sa.Column("attempt_num", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id"),
    )


def downgrade() -> None:
    op.drop_table("rehearsals")
    op.drop_index("ix_findings_review_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_file_assets_review_id", table_name="file_assets")
    op.drop_index("ix_file_assets_expires_at", table_name="file_assets")
    op.drop_table("file_assets")
    op.drop_index("ix_events_name_created_at", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_reviews_user_id_created_at", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
