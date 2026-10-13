"""order delivery_fee

Revision ID: b9d4e6f8a012
Revises: a8c3d5e7f901
Create Date: 2026-10-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9d4e6f8a012"
down_revision: str | None = "a8c3d5e7f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Every existing order was placed when delivery was free for everyone,
    # so 0 is the true historical value.
    op.add_column(
        "orders",
        sa.Column("delivery_fee", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.create_check_constraint("ck_orders_delivery_fee", "orders", "delivery_fee >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_orders_delivery_fee", "orders", type_="check")
    op.drop_column("orders", "delivery_fee")
