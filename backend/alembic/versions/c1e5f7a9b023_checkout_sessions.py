"""checkout_sessions

Revision ID: c1e5f7a9b023
Revises: c2a8e4f6b013
Create Date: 2026-10-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1e5f7a9b023"
down_revision: str | None = "c2a8e4f6b013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checkout_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("cart_id", sa.BigInteger(), nullable=False),
        sa.Column("address_id", sa.BigInteger(), nullable=False),
        sa.Column("promo_code", sa.String(length=50), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("gateway_name", sa.String(length=30), nullable=False),
        sa.Column("gateway_order_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'REFUNDED', 'REFUND_FAILED')",
            name="ck_checkout_sessions_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_checkout_sessions_amount"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway_name", "gateway_order_id", name="uq_checkout_sessions_gateway_order"),
    )
    op.create_index("ix_checkout_sessions_user_status", "checkout_sessions", ["user_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_checkout_sessions_user_status", table_name="checkout_sessions")
    op.drop_table("checkout_sessions")
