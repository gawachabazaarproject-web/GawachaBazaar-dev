"""add_payment_gateway_reference_and_webhook_events

Revision ID: 7b8bd4525a83
Revises: 37bbdf459894
Create Date: 2026-09-12 01:04:28.629675

Phase 14 (Payments: PNB UPI + COD):
- Adds a gateway-level order/session reference to `payments`
  (`gateway_name`, `gateway_order_id`), created once per payment obligation
  on first UPI initiation and reused across retry attempts against that
  same obligation. Both columns are nullable (always NULL for COD) and
  jointly unique.
- Creates `payment_webhook_events` for durable webhook idempotency -
  `UNIQUE(gateway_name, event_id)` is what makes duplicate/concurrent
  webhook delivery safe at the database level, not application memory.
  Raw webhook payloads are not stored; only a SHA-256 hash for
  tamper-evidence/debugging correlation.

Purely additive: no existing payments/payment_transactions data is
touched, no existing column is altered or dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b8bd4525a83"
down_revision: str | None = "37bbdf459894"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("gateway_name", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("gateway_order_id", sa.String(length=150), nullable=True),
    )
    op.create_unique_constraint(
        "uq_payments_gateway_name_order_id",
        "payments",
        ["gateway_name", "gateway_order_id"],
    )

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("gateway_name", sa.String(length=50), nullable=False),
        sa.Column("event_id", sa.String(length=150), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payment_transaction_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'PROCESSED', 'FAILED')",
            name="ck_payment_webhook_events_status",
        ),
        sa.ForeignKeyConstraint(
            ["payment_transaction_id"],
            ["payment_transactions.id"],
            name="fk_payment_webhook_events_payment_transaction_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payment_webhook_events"),
        sa.UniqueConstraint(
            "gateway_name",
            "event_id",
            name="uq_payment_webhook_events_gateway_event",
        ),
    )
    op.create_index(
        "ix_payment_webhook_events_payment_transaction_id",
        "payment_webhook_events",
        ["payment_transaction_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_webhook_events_status",
        "payment_webhook_events",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_webhook_events_status", table_name="payment_webhook_events"
    )
    op.drop_index(
        "ix_payment_webhook_events_payment_transaction_id",
        table_name="payment_webhook_events",
    )
    op.drop_table("payment_webhook_events")

    op.drop_constraint(
        "uq_payments_gateway_name_order_id", "payments", type_="unique"
    )
    op.drop_column("payments", "gateway_order_id")
    op.drop_column("payments", "gateway_name")
