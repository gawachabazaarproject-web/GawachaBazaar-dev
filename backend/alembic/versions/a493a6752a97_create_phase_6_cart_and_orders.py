"""create_phase_6_cart_and_orders

Revision ID: a493a6752a97
Revises: e204d99696f6
Create Date: 2026-09-09 01:26:42.908324

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a493a6752a97'
down_revision: str | None = 'e204d99696f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. carts
    op.create_table(
        'carts',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CHECKED_OUT', 'ABANDONED')",
            name='ck_carts_status',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name='fk_carts_user_id_users',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_carts'),
    )
    op.create_index('ix_carts_user_id', 'carts', ['user_id'], unique=False)
    op.create_index('ix_carts_status', 'carts', ['status'], unique=False)
    op.create_index(
        'uq_carts_user_active',
        'carts',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    # 2. cart_items
    op.create_table(
        'cart_items',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('cart_id', sa.BigInteger(), nullable=False),
        sa.Column('variant_id', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('quantity > 0', name='ck_cart_items_quantity'),
        sa.ForeignKeyConstraint(
            ['cart_id'],
            ['carts.id'],
            name='fk_cart_items_cart_id_carts',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['variant_id'],
            ['product_variants.id'],
            name='fk_cart_items_variant_id_product_variants',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_cart_items'),
        sa.UniqueConstraint('cart_id', 'variant_id', name='uq_cart_items_cart_id_variant_id'),
    )
    op.create_index('ix_cart_items_cart_id', 'cart_items', ['cart_id'], unique=False)
    op.create_index('ix_cart_items_variant_id', 'cart_items', ['variant_id'], unique=False)

    # 3. orders
    op.create_table(
        'orders',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('order_number', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('placed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED')",
            name='ck_orders_status',
        ),
        sa.CheckConstraint('total_amount >= 0', name='ck_orders_total_amount'),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name='fk_orders_user_id_users',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_orders'),
        sa.UniqueConstraint('order_number', name='uq_orders_order_number'),
    )
    op.create_index('ix_orders_user_id', 'orders', ['user_id'], unique=False)
    op.create_index('ix_orders_status', 'orders', ['status'], unique=False)
    op.create_index('ix_orders_placed_at', 'orders', ['placed_at'], unique=False)

    # 4. order_items
    op.create_table(
        'order_items',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('variant_id', sa.BigInteger(), nullable=False),
        sa.Column('product_name', sa.String(length=150), nullable=False),
        sa.Column('variant_name', sa.String(length=100), nullable=False),
        sa.Column('sku', sa.String(length=100), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('total_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('quantity > 0', name='ck_order_items_quantity'),
        sa.CheckConstraint('unit_price > 0', name='ck_order_items_unit_price'),
        sa.CheckConstraint('total_price >= 0', name='ck_order_items_total_price'),
        sa.ForeignKeyConstraint(
            ['order_id'],
            ['orders.id'],
            name='fk_order_items_order_id_orders',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['variant_id'],
            ['product_variants.id'],
            name='fk_order_items_variant_id_product_variants',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_order_items'),
    )
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'], unique=False)
    op.create_index('ix_order_items_variant_id', 'order_items', ['variant_id'], unique=False)

    # 5. order_addresses
    op.create_table(
        'order_addresses',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column('order_id', sa.BigInteger(), nullable=False),
        sa.Column('address_line_1', sa.String(length=255), nullable=False),
        sa.Column('address_line_2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('postal_code', sa.String(length=20), nullable=False),
        sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['order_id'],
            ['orders.id'],
            name='fk_order_addresses_order_id_orders',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_order_addresses'),
        sa.UniqueConstraint('order_id', name='uq_order_addresses_order_id'),
    )
    op.create_index('ix_order_addresses_order_id', 'order_addresses', ['order_id'], unique=False)


def downgrade() -> None:
    # Drop in exact reverse dependency order
    op.drop_index('ix_order_addresses_order_id', table_name='order_addresses')
    op.drop_table('order_addresses')

    op.drop_index('ix_order_items_variant_id', table_name='order_items')
    op.drop_index('ix_order_items_order_id', table_name='order_items')
    op.drop_table('order_items')

    op.drop_index('ix_orders_placed_at', table_name='orders')
    op.drop_index('ix_orders_status', table_name='orders')
    op.drop_index('ix_orders_user_id', table_name='orders')
    op.drop_table('orders')

    op.drop_index('ix_cart_items_variant_id', table_name='cart_items')
    op.drop_index('ix_cart_items_cart_id', table_name='cart_items')
    op.drop_table('cart_items')

    op.drop_index('uq_carts_user_active', table_name='carts', postgresql_where=sa.text("status = 'ACTIVE'"))
    op.drop_index('ix_carts_status', table_name='carts')
    op.drop_index('ix_carts_user_id', table_name='carts')
    op.drop_table('carts')
