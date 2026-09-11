"""inventory_reservation_and_fulfillment

Revision ID: 2603b7a0587e
Revises: 7b8bd4525a83
Create Date: 2026-09-12 02:19:08.405096

Phase 15 (Inventory Reservation & Order Expiry & Fulfillment Foundation):
- Adds `inventory_lots.reserved_quantity` (default 0 for all existing
  rows - no historical reservations are invented) with
  CHECK(0 <= reserved_quantity <= quantity). Physical `quantity` is
  untouched by this migration; reservation never decrements it.
- Adds a composite index on inventory_lots(variant_id, status,
  created_at, id) supporting the new FIFO reservation-allocation query.
- Widens `orders.ck_orders_status` to additionally allow 'EXPIRED' -
  purely additive, no existing status value is removed, no existing row
  needs updating.
- Creates `inventory_reservations` (one per order, UNIQUE(order_id)) and
  `inventory_reservation_items` (the FIFO order_item -> lot allocation
  join) to track the reserve -> commit/release/expire lifecycle.
- Creates `fulfillments` (one per order, UNIQUE(order_id)) for the
  PENDING -> ... -> DELIVERED pipeline; only DELIVERED consumes physical
  inventory.

Purely additive: no existing table is dropped, no existing column is
altered or removed, no existing data is rewritten.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2603b7a0587e"
down_revision: str | None = "7b8bd4525a83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # inventory_lots.reserved_quantity
    # ------------------------------------------------------------------
    op.add_column(
        "inventory_lots",
        sa.Column(
            "reserved_quantity",
            sa.Numeric(12, 3),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_inventory_lots_reserved_quantity",
        "inventory_lots",
        "reserved_quantity >= 0 AND reserved_quantity <= quantity",
    )
    op.create_index(
        "ix_inventory_lots_variant_status_fifo",
        "inventory_lots",
        ["variant_id", "status", "created_at", "id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # orders.status: add EXPIRED (additive)
    # ------------------------------------------------------------------
    op.drop_constraint("ck_orders_status", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_status",
        "orders",
        "status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'EXPIRED')",
    )

    # ------------------------------------------------------------------
    # inventory_reservations
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_reservations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'COMMITTED', 'RELEASED', 'EXPIRED')",
            name="ck_inventory_reservations_status",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_inventory_reservations_order_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_reservations"),
        sa.UniqueConstraint("order_id", name="uq_inventory_reservations_order_id"),
    )
    op.create_index(
        "ix_inventory_reservations_status",
        "inventory_reservations",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_reservations_expires_at",
        "inventory_reservations",
        ["expires_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # inventory_reservation_items
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_reservation_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("reservation_id", sa.BigInteger(), nullable=False),
        sa.Column("order_item_id", sa.BigInteger(), nullable=False),
        sa.Column("inventory_lot_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_inventory_reservation_items_quantity"
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["inventory_reservations.id"],
            name="fk_inventory_reservation_items_reservation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name="fk_inventory_reservation_items_order_item_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_lot_id"],
            ["inventory_lots.id"],
            name="fk_inventory_reservation_items_inventory_lot_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_reservation_items"),
    )
    op.create_index(
        "ix_inventory_reservation_items_reservation_id",
        "inventory_reservation_items",
        ["reservation_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_reservation_items_order_item_id",
        "inventory_reservation_items",
        ["order_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_reservation_items_inventory_lot_id",
        "inventory_reservation_items",
        ["inventory_lot_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # fulfillments
    # ------------------------------------------------------------------
    op.create_table(
        "fulfillments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PICKING', 'PACKED', 'READY_FOR_DELIVERY', "
            "'OUT_FOR_DELIVERY', 'DELIVERED')",
            name="ck_fulfillments_status",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_fulfillments_order_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fulfillments"),
        sa.UniqueConstraint("order_id", name="uq_fulfillments_order_id"),
    )
    op.create_index(
        "ix_fulfillments_status", "fulfillments", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_fulfillments_status", table_name="fulfillments")
    op.drop_table("fulfillments")

    op.drop_index(
        "ix_inventory_reservation_items_inventory_lot_id",
        table_name="inventory_reservation_items",
    )
    op.drop_index(
        "ix_inventory_reservation_items_order_item_id",
        table_name="inventory_reservation_items",
    )
    op.drop_index(
        "ix_inventory_reservation_items_reservation_id",
        table_name="inventory_reservation_items",
    )
    op.drop_table("inventory_reservation_items")

    op.drop_index(
        "ix_inventory_reservations_expires_at", table_name="inventory_reservations"
    )
    op.drop_index(
        "ix_inventory_reservations_status", table_name="inventory_reservations"
    )
    op.drop_table("inventory_reservations")

    op.drop_constraint("ck_orders_status", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_status",
        "orders",
        "status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED')",
    )

    op.drop_index(
        "ix_inventory_lots_variant_status_fifo", table_name="inventory_lots"
    )
    op.drop_constraint(
        "ck_inventory_lots_reserved_quantity", "inventory_lots", type_="check"
    )
    op.drop_column("inventory_lots", "reserved_quantity")
