"""create_phase_5_packaging_and_labeling

Revision ID: e204d99696f6
Revises: ff073dad9cfc
Create Date: 2026-09-09 00:51:20.861189

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e204d99696f6"
down_revision: str | None = "ff073dad9cfc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. packaging_operations
    op.create_table(
        "packaging_operations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("packaging_code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performed_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "packaging_code", name="uq_packaging_operations_packaging_code"
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["inventory_locations.id"],
            name="fk_packaging_operations_location_id_inventory_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["performed_by_user_id"],
            ["users.id"],
            name="fk_packaging_operations_performed_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name="ck_packaging_operations_status",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_packaging_operations_completed_at",
        ),
    )
    op.create_index(
        "ix_packaging_operations_location_id",
        "packaging_operations",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        "ix_packaging_operations_status",
        "packaging_operations",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_packaging_operations_started_at",
        "packaging_operations",
        ["started_at"],
        unique=False,
    )

    # 2. packaging_inputs
    op.create_table(
        "packaging_inputs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("packaging_operation_id", sa.BigInteger(), nullable=False),
        sa.Column("inventory_lot_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["packaging_operation_id"],
            ["packaging_operations.id"],
            name="fk_packaging_inputs_operation_id_packaging_operations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_lot_id"],
            ["inventory_lots.id"],
            name="fk_packaging_inputs_inventory_lot_id_inventory_lots",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_packaging_inputs_quantity",
        ),
    )
    op.create_index(
        "ix_packaging_inputs_packaging_operation_id",
        "packaging_inputs",
        ["packaging_operation_id"],
        unique=False,
    )
    op.create_index(
        "ix_packaging_inputs_inventory_lot_id",
        "packaging_inputs",
        ["inventory_lot_id"],
        unique=False,
    )

    # 3. packaging_outputs
    op.create_table(
        "packaging_outputs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("packaging_operation_id", sa.BigInteger(), nullable=False),
        sa.Column("inventory_lot_id", sa.BigInteger(), nullable=False),
        sa.Column("package_count", sa.Integer(), nullable=False),
        sa.Column("total_quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["packaging_operation_id"],
            ["packaging_operations.id"],
            name="fk_packaging_outputs_operation_id_packaging_operations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_lot_id"],
            ["inventory_lots.id"],
            name="fk_packaging_outputs_inventory_lot_id_inventory_lots",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "package_count > 0",
            name="ck_packaging_outputs_package_count",
        ),
        sa.CheckConstraint(
            "total_quantity > 0",
            name="ck_packaging_outputs_total_quantity",
        ),
    )
    op.create_index(
        "ix_packaging_outputs_packaging_operation_id",
        "packaging_outputs",
        ["packaging_operation_id"],
        unique=False,
    )
    op.create_index(
        "ix_packaging_outputs_inventory_lot_id",
        "packaging_outputs",
        ["inventory_lot_id"],
        unique=False,
    )


def downgrade() -> None:
    # 1. Reverse packaging_outputs
    op.drop_index(
        "ix_packaging_outputs_inventory_lot_id", table_name="packaging_outputs"
    )
    op.drop_index(
        "ix_packaging_outputs_packaging_operation_id", table_name="packaging_outputs"
    )
    op.drop_table("packaging_outputs")

    # 2. Reverse packaging_inputs
    op.drop_index(
        "ix_packaging_inputs_inventory_lot_id", table_name="packaging_inputs"
    )
    op.drop_index(
        "ix_packaging_inputs_packaging_operation_id", table_name="packaging_inputs"
    )
    op.drop_table("packaging_inputs")

    # 3. Reverse packaging_operations
    op.drop_index(
        "ix_packaging_operations_started_at", table_name="packaging_operations"
    )
    op.drop_index("ix_packaging_operations_status", table_name="packaging_operations")
    op.drop_index(
        "ix_packaging_operations_location_id", table_name="packaging_operations"
    )
    op.drop_table("packaging_operations")
