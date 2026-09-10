"""add_orders_cart_id_and_remove_redundant_order_address_index

Revision ID: a4738979ac7c
Revises: 68d13edaa6f2
Create Date: 2026-09-10 06:03:01.676669

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4738979ac7c'
down_revision: str | None = '68d13edaa6f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add nullable cart_id column to orders
    op.add_column('orders', sa.Column('cart_id', sa.BigInteger(), nullable=True))

    # 2. Add foreign key orders.cart_id -> carts.id ON DELETE RESTRICT
    op.create_foreign_key(
        'fk_orders_cart_id_carts',
        'orders',
        'carts',
        ['cart_id'],
        ['id'],
        ondelete='RESTRICT',
    )

    # 3. Add unique constraint on orders.cart_id
    op.create_unique_constraint('uq_orders_cart_id', 'orders', ['cart_id'])

    # 4. Drop redundant ix_order_addresses_order_id if it exists
    op.drop_index('ix_order_addresses_order_id', table_name='order_addresses', if_exists=True)


def downgrade() -> None:
    # 1. Recreate redundant index ix_order_addresses_order_id
    op.create_index('ix_order_addresses_order_id', 'order_addresses', ['order_id'], unique=False)

    # 2. Drop unique constraint uq_orders_cart_id
    op.drop_constraint('uq_orders_cart_id', 'orders', type_='unique')

    # 3. Drop foreign key fk_orders_cart_id_carts
    op.drop_constraint('fk_orders_cart_id_carts', 'orders', type_='foreignkey')

    # 4. Drop cart_id column from orders
    op.drop_column('orders', 'cart_id')
