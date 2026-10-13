"""inventory location coordinates and packing point

Revision ID: c2a8e4f6b013
Revises: b9d4e6f8a012
Create Date: 2026-10-10 00:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c2a8e4f6b013"
down_revision: str | None = "b9d4e6f8a012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("inventory_locations", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("inventory_locations", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column(
        "inventory_locations",
        sa.Column("is_packing_point", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "uq_inventory_locations_one_packing_point",
        "inventory_locations",
        ["is_packing_point"],
        unique=True,
        postgresql_where=sa.text("is_packing_point"),
    )


def downgrade() -> None:
    op.drop_index("uq_inventory_locations_one_packing_point", table_name="inventory_locations")
    op.drop_column("inventory_locations", "is_packing_point")
    op.drop_column("inventory_locations", "longitude")
    op.drop_column("inventory_locations", "latitude")
