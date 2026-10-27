"""delivery otps (COD proof of delivery)

Revision ID: d3e4f5a60712
Revises: c2d3e4f5a601
Create Date: 2026-10-27 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a60712'
down_revision: str | None = 'c2d3e4f5a601'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('delivery_otps',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('order_id', sa.BigInteger(), nullable=False),
    sa.Column('assignment_id', sa.BigInteger(), nullable=False),
    sa.Column('otp_hash', sa.String(length=64), nullable=False),
    sa.Column('otp_encrypted', sa.LargeBinary(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('invalidated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('invalidated_reason', sa.String(length=30), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('attempts >= 0 AND attempts <= max_attempts', name='ck_delivery_otps_attempts'),
    sa.CheckConstraint('max_attempts >= 1', name='ck_delivery_otps_max_attempts'),
    sa.ForeignKeyConstraint(['assignment_id'], ['delivery_assignments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_delivery_otps_order_created', 'delivery_otps', ['order_id', 'created_at'], unique=False)
    op.create_index('uq_delivery_otps_one_active_per_order', 'delivery_otps', ['order_id'], unique=True,
                    postgresql_where=sa.text('verified_at IS NULL AND invalidated_at IS NULL'))


def downgrade() -> None:
    op.drop_index('uq_delivery_otps_one_active_per_order', table_name='delivery_otps',
                  postgresql_where=sa.text('verified_at IS NULL AND invalidated_at IS NULL'))
    op.drop_index('ix_delivery_otps_order_created', table_name='delivery_otps')
    op.drop_table('delivery_otps')
