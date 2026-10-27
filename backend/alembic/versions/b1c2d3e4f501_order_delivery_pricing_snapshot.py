"""order delivery pricing snapshot

Revision ID: b1c2d3e4f501
Revises: a8d2f4b6c0e1
Create Date: 2026-10-27

Adds the pricing snapshot (rule version, base fee, per-km, billable km) next to
the existing delivery audit columns on `orders`. All columns are nullable and
additive: orders placed before this revision simply have no snapshot, and the
installed mobile apps do not read these columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1c2d3e4f501"
down_revision: str | None = "a8d2f4b6c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_pricing_version", sa.String(30), nullable=True))
    op.add_column("orders", sa.Column("delivery_base_fee", sa.Numeric(12, 2), nullable=True))
    op.add_column("orders", sa.Column("delivery_per_km", sa.Numeric(12, 2), nullable=True))
    op.add_column("orders", sa.Column("delivery_billable_km", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_orders_delivery_billable_km", "orders", "delivery_billable_km IS NULL OR delivery_billable_km >= 1"
    )


def downgrade() -> None:
    op.drop_constraint("ck_orders_delivery_billable_km", "orders", type_="check")
    op.drop_column("orders", "delivery_billable_km")
    op.drop_column("orders", "delivery_per_km")
    op.drop_column("orders", "delivery_base_fee")
    op.drop_column("orders", "delivery_pricing_version")
