"""reviews: add deck_filename, n_slides, delivery_metrics

Revision ID: 0002_deck_filename
Revises: 0001_initial
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_deck_filename"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("deck_filename", sa.String(length=255), nullable=False, server_default=""),
    )
    op.alter_column("reviews", "deck_filename", server_default=None)
    op.add_column("reviews", sa.Column("n_slides", sa.Integer(), nullable=True))
    op.add_column("reviews", sa.Column("delivery_metrics", _json_type, nullable=True))


def downgrade() -> None:
    op.drop_column("reviews", "delivery_metrics")
    op.drop_column("reviews", "n_slides")
    op.drop_column("reviews", "deck_filename")
