"""product_variants.dedicated_stock: a size that sells only its own stock

Revision ID: e8f3b1d5c7a2
Revises: d7e2a9c4b6f1
Create Date: 2026-10-20 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8f3b1d5c7a2"
down_revision: str | None = "d7e2a9c4b6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column("dedicated_stock", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("product_variants", "dedicated_stock")
