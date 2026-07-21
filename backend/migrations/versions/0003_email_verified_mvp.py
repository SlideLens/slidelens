"""users: mark existing accounts email_verified for MVP (no verify flow)

Revision ID: 0003_email_verified_default
Revises: 0002_deck_filename
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_email_verified_default"
down_revision: str | None = "0002_deck_filename"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE users SET email_verified = true WHERE email_verified = false"))


def downgrade() -> None:
    # Irreversible: we cannot know who was unverified before.
    pass
