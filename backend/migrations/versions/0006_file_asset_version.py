"""file_assets: add version (regenerated fixed.pptx naming, П7/П-followup)

Revision ID: 0006_file_asset_version
Revises: 0005_rehearsal_multi_attempt
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_file_asset_version"
down_revision: str | None = "0005_rehearsal_multi_attempt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "file_assets",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("file_assets", "version", server_default=None)


def downgrade() -> None:
    op.drop_column("file_assets", "version")
