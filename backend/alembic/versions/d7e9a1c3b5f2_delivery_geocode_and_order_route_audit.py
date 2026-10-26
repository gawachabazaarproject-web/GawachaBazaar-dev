"""address geocode metadata + order delivery route audit columns

Revision ID: d7e9a1c3b5f2
Revises: b4c7d9e1f2a8
Create Date: 2026-10-26 10:00:00.000000

Additive and nullable only: no backfill, no table rewrite, safe to run on a
live database. addresses.latitude/longitude already exist.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e9a1c3b5f2"
down_revision: str | None = "b4c7d9e1f2a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("addresses", sa.Column("geocode_provider", sa.String(30), nullable=True))
    op.add_column("addresses", sa.Column("geocode_provider_id", sa.String(100), nullable=True))
    op.add_column("addresses", sa.Column("geocoded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("delivery_distance_meters", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("routing_provider", sa.String(30), nullable=True))
    op.add_column("orders", sa.Column("warehouse_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_orders_warehouse_id_inventory_locations",
        "orders",
        "inventory_locations",
        ["warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_warehouse_id_inventory_locations", "orders", type_="foreignkey")
    op.drop_column("orders", "warehouse_id")
    op.drop_column("orders", "routing_provider")
    op.drop_column("orders", "delivery_distance_meters")
    op.drop_column("addresses", "geocoded_at")
    op.drop_column("addresses", "geocode_provider_id")
    op.drop_column("addresses", "geocode_provider")
