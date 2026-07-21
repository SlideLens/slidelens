"""findings: add user_like for 👍 feedback

Revision ID: 0004_finding_user_like
Revises: 0003_email_verified_default
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_finding_user_like"
down_revision: str | None = "0003_email_verified_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("user_like", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("findings", "user_like", server_default=None)


def downgrade() -> None:
    op.drop_column("findings", "user_like")
