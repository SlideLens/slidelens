"""users: add is_admin (unlimited Разборы, bypasses free_reviews_left)

Backfills is_admin=true for admin@demo.com so an already-registered dev
account picks it up immediately; app/auth.py additionally self-heals this
on every login against Settings.admin_email_set (ADMIN_EMAILS).

Revision ID: 0007_user_is_admin
Revises: 0006_file_asset_version
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_user_is_admin"
down_revision: str | None = "0006_file_asset_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.alter_column("users", "is_admin", server_default=None)
    op.execute(sa.text("UPDATE users SET is_admin = true WHERE lower(email) = 'admin@demo.com'"))


def downgrade() -> None:
    op.drop_column("users", "is_admin")
