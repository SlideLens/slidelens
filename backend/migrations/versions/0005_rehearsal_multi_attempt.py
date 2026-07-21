"""rehearsals: multi-attempt (drop unique review_id) + status/fail_reason/findings/finished_at

Revision ID: 0005_rehearsal_multi_attempt
Revises: 0004_finding_user_like
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_rehearsal_multi_attempt"
down_revision: str | None = "0004_finding_user_like"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("rehearsals_review_id_key", "rehearsals", type_="unique")
    op.add_column(
        "rehearsals",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="done"),
    )
    op.alter_column("rehearsals", "status", server_default=None)
    op.add_column("rehearsals", sa.Column("fail_reason", sa.Text(), nullable=True))
    op.add_column("rehearsals", sa.Column("findings", sa.JSON(), nullable=True))
    op.add_column(
        "rehearsals", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_rehearsals_review_id_attempt_num",
        "rehearsals",
        ["review_id", "attempt_num"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rehearsals_review_id_attempt_num", table_name="rehearsals")
    op.drop_column("rehearsals", "finished_at")
    op.drop_column("rehearsals", "findings")
    op.drop_column("rehearsals", "fail_reason")
    op.drop_column("rehearsals", "status")
    op.create_unique_constraint("rehearsals_review_id_key", "rehearsals", ["review_id"])
