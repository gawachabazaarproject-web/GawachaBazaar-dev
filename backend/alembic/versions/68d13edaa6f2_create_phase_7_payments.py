"""create_phase_7_payments

Revision ID: 68d13edaa6f2
Revises: a493a6752a97
Create Date: 2026-09-09 02:48:11.009216

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '68d13edaa6f2'
down_revision: str | None = 'a493a6752a97'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. payments
    op.create_table(
        'payments',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('payment_method', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "payment_method IN ('UPI', 'COD')",
            name='ck_payments_payment_method',
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PAID', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name='ck_payments_status',
        ),
        sa.CheckConstraint('amount > 0', name='ck_payments_amount'),
        sa.ForeignKeyConstraint(
            ['order_id'],
            ['orders.id'],
            name='fk_payments_order_id_orders',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_payments'),
        sa.UniqueConstraint('order_id', name='uq_payments_order_id'),
    )
    op.create_index('ix_payments_status', 'payments', ['status'], unique=False)
    op.create_index('ix_payments_payment_method', 'payments', ['payment_method'], unique=False)

    # 2. payment_transactions
    op.create_table(
        'payment_transactions',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('payment_id', sa.BigInteger(), nullable=False),
        sa.Column('transaction_type', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('gateway_name', sa.String(length=50), nullable=True),
        sa.Column('gateway_transaction_id', sa.String(length=150), nullable=True),
        sa.Column('idempotency_key', sa.String(length=150), nullable=True),
        sa.Column('gateway_response', sa.Text(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('initiated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "transaction_type IN ('PAYMENT')",
            name='ck_payment_transactions_transaction_type',
        ),
        sa.CheckConstraint(
            "status IN ('INITIATED', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name='ck_payment_transactions_status',
        ),
        sa.CheckConstraint('amount > 0', name='ck_payment_transactions_amount'),
        sa.ForeignKeyConstraint(
            ['payment_id'],
            ['payments.id'],
            name='fk_payment_transactions_payment_id_payments',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_payment_transactions'),
        sa.UniqueConstraint('idempotency_key', name='uq_payment_transactions_idempotency_key'),
    )
    op.create_index('ix_payment_transactions_payment_id', 'payment_transactions', ['payment_id'], unique=False)
    op.create_index('ix_payment_transactions_status', 'payment_transactions', ['status'], unique=False)
    op.create_index('ix_payment_transactions_gateway_transaction_id', 'payment_transactions', ['gateway_transaction_id'], unique=False)


def downgrade() -> None:
    # Drop in exact reverse dependency order
    op.drop_index('ix_payment_transactions_gateway_transaction_id', table_name='payment_transactions')
    op.drop_index('ix_payment_transactions_status', table_name='payment_transactions')
    op.drop_index('ix_payment_transactions_payment_id', table_name='payment_transactions')
    op.drop_table('payment_transactions')

    op.drop_index('ix_payments_payment_method', table_name='payments')
    op.drop_index('ix_payments_status', table_name='payments')
    op.drop_table('payments')
