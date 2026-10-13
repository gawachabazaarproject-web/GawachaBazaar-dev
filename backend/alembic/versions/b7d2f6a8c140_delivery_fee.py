"""delivery fee on orders (also merges the two open heads)

Revision ID: b7d2f6a8c140
Revises: a1c9e3d7b520, c5f1a7e3d9b2
Create Date: 2026-10-13 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7d2f6a8c140"
down_revision: str | Sequence[str] | None = ("a1c9e3d7b520", "c5f1a7e3d9b2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_fee", sa.Numeric(12, 2), server_default="0", nullable=False))
    op.add_column("orders", sa.Column("delivery_distance_km", sa.Numeric(8, 1), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "delivery_distance_km")
    op.drop_column("orders", "delivery_fee")
