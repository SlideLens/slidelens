"""users.balance_reviews + reviews.credit_source — предоплаченные пакеты Разборов

До этого платный план вообще не тарифицировался (``plan == 'paid'`` проходил
мимо учёта), поэтому один подписчик мог сжечь любую сумму. Теперь купленные
Разборы лежат на ``users.balance_reviews``, а ``reviews.credit_source``
запоминает кошелёк списания, чтобы возврат при провале шёл туда же.

Revision ID: 0008_review_credits
Revises: 0007_user_is_admin
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_review_credits"
down_revision: str | None = "0007_user_is_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("balance_reviews", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("users", "balance_reviews", server_default=None)
    op.add_column("reviews", sa.Column("credit_source", sa.String(length=16), nullable=True))
    # Уже существующие Разборы были списаны с бесплатного счётчика (иного не было).
    op.execute(sa.text("UPDATE reviews SET credit_source = 'free'"))


def downgrade() -> None:
    op.drop_column("reviews", "credit_source")
    op.drop_column("users", "balance_reviews")
