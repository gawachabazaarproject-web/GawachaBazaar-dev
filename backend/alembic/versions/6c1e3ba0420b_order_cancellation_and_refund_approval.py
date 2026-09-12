"""order_cancellation_and_refund_approval

Revision ID: 6c1e3ba0420b
Revises: c683dfa20681
Create Date: 2026-09-12 18:04:22.011887

Phase 18 (Order Cancellation & Refund Approval):
- Adds `orders.cancelled_at` / `cancelled_by_user_id` / `cancellation_reason`
  (all nullable) - `orders.status` already included 'CANCELLED' since
  Phase 1's original CHECK constraint, so no CHECK change is needed there;
  this phase is simply the first to actually use it, via a deliberate
  state transition (app/services/order_state.py), never a boolean flag.
- Creates `refunds` (one per order, UNIQUE(order_id)) - the refund
  approval-workflow entity: PENDING_APPROVAL -> APPROVED/REJECTED ->
  PROCESSING -> REFUNDED/FAILED. `amount`/`currency` are copied from the
  order's Payment at creation time, never recomputed.
- Widens `payment_transactions.ck_payment_transactions_transaction_type`
  to add 'REFUND' (was only 'PAYMENT') and adds a nullable
  `payment_transactions.refund_id` FK -> refunds.id, so a refund's gateway
  attempts are recorded exactly the way a payment's attempts already are -
  an old PAYMENT transaction row is never edited into a REFUND one.

Purely additive: no existing table is dropped, no existing column is
altered or removed, no existing data is rewritten.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6c1e3ba0420b'
down_revision: str | None = 'c683dfa20681'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # orders: cancellation audit trail
    # ------------------------------------------------------------------
    op.add_column(
        "orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("cancelled_by_user_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("cancellation_reason", sa.String(length=500), nullable=True)
    )
    op.create_foreign_key(
        "fk_orders_cancelled_by_user_id",
        "orders",
        "users",
        ["cancelled_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # ------------------------------------------------------------------
    # refunds
    # ------------------------------------------------------------------
    op.create_table(
        "refunds",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT", name="fk_refunds_order_id"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT", name="fk_refunds_payment_id"),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"], ["users.id"], ondelete="RESTRICT", name="fk_refunds_approved_by_user_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refunds"),
        sa.UniqueConstraint("order_id", name="uq_refunds_order_id"),
        sa.CheckConstraint(
            "status IN ('PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'PROCESSING', 'REFUNDED', 'FAILED')",
            name="ck_refunds_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_refunds_amount"),
    )
    op.create_index("ix_refunds_status", "refunds", ["status"], unique=False)
    op.create_index("ix_refunds_payment_id", "refunds", ["payment_id"], unique=False)

    # ------------------------------------------------------------------
    # payment_transactions: REFUND transaction type + refund_id link
    # ------------------------------------------------------------------
    op.drop_constraint(
        "ck_payment_transactions_transaction_type", "payment_transactions", type_="check"
    )
    op.create_check_constraint(
        "ck_payment_transactions_transaction_type",
        "payment_transactions",
        "transaction_type IN ('PAYMENT', 'REFUND')",
    )
    op.add_column(
        "payment_transactions", sa.Column("refund_id", sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        "fk_payment_transactions_refund_id",
        "payment_transactions",
        "refunds",
        ["refund_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_payment_transactions_refund_id", "payment_transactions", ["refund_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_refund_id", table_name="payment_transactions")
    op.drop_constraint(
        "fk_payment_transactions_refund_id", "payment_transactions", type_="foreignkey"
    )
    op.drop_column("payment_transactions", "refund_id")
    op.drop_constraint(
        "ck_payment_transactions_transaction_type", "payment_transactions", type_="check"
    )
    op.create_check_constraint(
        "ck_payment_transactions_transaction_type",
        "payment_transactions",
        "transaction_type IN ('PAYMENT')",
    )

    op.drop_index("ix_refunds_payment_id", table_name="refunds")
    op.drop_index("ix_refunds_status", table_name="refunds")
    op.drop_table("refunds")

    op.drop_constraint("fk_orders_cancelled_by_user_id", "orders", type_="foreignkey")
    op.drop_column("orders", "cancellation_reason")
    op.drop_column("orders", "cancelled_by_user_id")
    op.drop_column("orders", "cancelled_at")
