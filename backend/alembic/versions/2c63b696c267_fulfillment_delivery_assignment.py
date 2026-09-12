"""fulfillment_delivery_assignment

Revision ID: 2c63b696c267
Revises: 2603b7a0587e
Create Date: 2026-09-12 05:29:53.074889

Phase 16 (Fulfillment & Delivery Operations):
- Widens `fulfillments.ck_fulfillments_status` to add 'ASSIGNED' between
  READY_FOR_DELIVERY and OUT_FOR_DELIVERY - purely additive, no existing
  status value is removed, no existing row needs updating.
- Adds `fulfillments.delivery_partner_user_id` (nullable FK -> users.id,
  RESTRICT) - the delivery partner assigned to this fulfillment. A
  delivery partner is a User holding the DELIVERY_PARTNER role, not a
  dedicated table, consistent with the existing Wholesaler model
  (Phase 8.1).
- Adds `fulfillments.inventory_location_id` (nullable FK ->
  inventory_locations.id, RESTRICT) - the single location the reservation
  actually allocated from, when unambiguous. Reservations pool inventory
  lots across ALL locations for a variant (Phase 15 design - no
  location-selection concept exists anywhere in this codebase), so a
  reservation CAN legitimately span multiple locations; this column is
  populated by application logic only when every allocated lot shares one
  location, and left NULL otherwise rather than recording a misleading
  single location.
- Adds `fulfillments.assigned_at` (nullable timestamptz) - set once, at
  assignment time, server-side.

Purely additive: no existing table is dropped, no existing column is
altered or removed, no existing data is rewritten.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c63b696c267"
down_revision: str | None = "2603b7a0587e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fulfillments",
        sa.Column("delivery_partner_user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "fulfillments",
        sa.Column("inventory_location_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "fulfillments",
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_foreign_key(
        "fk_fulfillments_delivery_partner_user_id",
        "fulfillments",
        "users",
        ["delivery_partner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_fulfillments_inventory_location_id",
        "fulfillments",
        "inventory_locations",
        ["inventory_location_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_fulfillments_delivery_partner_user_id",
        "fulfillments",
        ["delivery_partner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_fulfillments_inventory_location_id",
        "fulfillments",
        ["inventory_location_id"],
        unique=False,
    )

    op.drop_constraint("ck_fulfillments_status", "fulfillments", type_="check")
    op.create_check_constraint(
        "ck_fulfillments_status",
        "fulfillments",
        "status IN ('PENDING', 'PICKING', 'PACKED', 'READY_FOR_DELIVERY', "
        "'ASSIGNED', 'OUT_FOR_DELIVERY', 'DELIVERED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_fulfillments_status", "fulfillments", type_="check")
    op.create_check_constraint(
        "ck_fulfillments_status",
        "fulfillments",
        "status IN ('PENDING', 'PICKING', 'PACKED', 'READY_FOR_DELIVERY', "
        "'OUT_FOR_DELIVERY', 'DELIVERED')",
    )

    op.drop_index(
        "ix_fulfillments_inventory_location_id", table_name="fulfillments"
    )
    op.drop_index(
        "ix_fulfillments_delivery_partner_user_id", table_name="fulfillments"
    )

    op.drop_constraint(
        "fk_fulfillments_inventory_location_id", "fulfillments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_fulfillments_delivery_partner_user_id", "fulfillments", type_="foreignkey"
    )

    op.drop_column("fulfillments", "assigned_at")
    op.drop_column("fulfillments", "inventory_location_id")
    op.drop_column("fulfillments", "delivery_partner_user_id")
