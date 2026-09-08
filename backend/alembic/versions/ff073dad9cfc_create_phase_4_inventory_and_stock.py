"""create_phase_4_inventory_and_stock

Revision ID: ff073dad9cfc
Revises: 9fb24ab99384
Create Date: 2026-09-09 00:03:21.704712

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ff073dad9cfc"
down_revision: str | None = "9fb24ab99384"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. inventory_locations
    op.create_table(
        "inventory_locations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("address_line_1", sa.String(length=255), nullable=False),
        sa.Column("address_line_2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_inventory_locations_code"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_inventory_locations_status",
        ),
    )
    op.create_index(
        "ix_inventory_locations_type",
        "inventory_locations",
        ["type"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_locations_status",
        "inventory_locations",
        ["status"],
        unique=False,
    )

    # 2. inventory_lots
    op.create_table(
        "inventory_lots",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["batches.id"],
            name="fk_inventory_lots_batch_id_batches",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name="fk_inventory_lots_variant_id_product_variants",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["inventory_locations.id"],
            name="fk_inventory_lots_location_id_inventory_locations",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "variant_id",
            "location_id",
            name="uq_inventory_lots_batch_variant_location",
        ),
        sa.CheckConstraint(
            "quantity >= 0",
            name="ck_inventory_lots_quantity",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'DEPLETED')",
            name="ck_inventory_lots_status",
        ),
    )
    op.create_index(
        "ix_inventory_lots_batch_id",
        "inventory_lots",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_lots_variant_id",
        "inventory_lots",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_lots_location_id",
        "inventory_lots",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        "ix_inventory_lots_status",
        "inventory_lots",
        ["status"],
        unique=False,
    )

    # 3. stock_movements
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("inventory_lot_id", sa.BigInteger(), nullable=False),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.BigInteger(), nullable=True),
        sa.Column("performed_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["inventory_lot_id"],
            ["inventory_lots.id"],
            name="fk_stock_movements_inventory_lot_id_inventory_lots",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"],
            ["users.id"],
            name="fk_stock_movements_performed_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "movement_type IN ('RECEIPT', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', "
            "'DAMAGE', 'WASTE', 'TRANSFER_IN', 'TRANSFER_OUT', 'DISPATCH')",
            name="ck_stock_movements_movement_type",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_stock_movements_quantity",
        ),
    )
    op.create_index(
        "ix_stock_movements_inventory_lot_id",
        "stock_movements",
        ["inventory_lot_id"],
        unique=False,
    )
    op.create_index(
        "ix_stock_movements_performed_by_user_id",
        "stock_movements",
        ["performed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_stock_movements_movement_type",
        "stock_movements",
        ["movement_type"],
        unique=False,
    )
    op.create_index(
        "ix_stock_movements_occurred_at",
        "stock_movements",
        ["occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    # 1. Reverse stock_movements
    op.drop_index("ix_stock_movements_occurred_at", table_name="stock_movements")
    op.drop_index("ix_stock_movements_movement_type", table_name="stock_movements")
    op.drop_index(
        "ix_stock_movements_performed_by_user_id", table_name="stock_movements"
    )
    op.drop_index("ix_stock_movements_inventory_lot_id", table_name="stock_movements")
    op.drop_table("stock_movements")

    # 2. Reverse inventory_lots
    op.drop_index("ix_inventory_lots_status", table_name="inventory_lots")
    op.drop_index("ix_inventory_lots_location_id", table_name="inventory_lots")
    op.drop_index("ix_inventory_lots_variant_id", table_name="inventory_lots")
    op.drop_index("ix_inventory_lots_batch_id", table_name="inventory_lots")
    op.drop_table("inventory_lots")

    # 3. Reverse inventory_locations
    op.drop_index("ix_inventory_locations_status", table_name="inventory_locations")
    op.drop_index("ix_inventory_locations_type", table_name="inventory_locations")
    op.drop_table("inventory_locations")
